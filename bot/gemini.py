"""Gemini-backed responder that keeps per-user conversation context."""
import logging
import threading
import time

from google import genai
from google.genai import errors, types

from . import config

log = logging.getLogger(__name__)

_client = genai.Client(api_key=config.GEMINI_API_KEY)
_generation_config = types.GenerateContentConfig(
    system_instruction=config.SYSTEM_PROMPT,
)


class ConversationStore:
    """In-memory history per WhatsApp user, expiring after inactivity."""

    def __init__(self, timeout_seconds: int, max_turns: int):
        self._timeout = timeout_seconds
        self._max_contents = max_turns * 2  # one user + one model entry per turn
        self._history: dict[str, list[types.Content]] = {}
        self._last_seen: dict[str, float] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def lock_for(self, user_id: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(user_id, threading.Lock())

    def get(self, user_id: str) -> list[types.Content]:
        last = self._last_seen.get(user_id)
        if last is None or time.time() - last > self._timeout:
            self._history[user_id] = []
        return list(self._history[user_id])

    def save(self, user_id: str, history: list[types.Content]) -> None:
        self._history[user_id] = history[-self._max_contents :]
        self._last_seen[user_id] = time.time()

    def reset(self, user_id: str) -> None:
        self._history.pop(user_id, None)
        self._last_seen.pop(user_id, None)


store = ConversationStore(
    timeout_seconds=config.SESSION_TIMEOUT_MINUTES * 60,
    max_turns=config.MAX_HISTORY_TURNS,
)


def _send_with_retry(chat, text: str, attempts: int = 4):
    """Retry on Gemini overload (503) and rate limits (429) with backoff."""
    for attempt in range(attempts):
        try:
            return chat.send_message(text)
        except errors.APIError as exc:
            if exc.code not in (429, 500, 503) or attempt == attempts - 1:
                raise
            delay = 2**attempt
            log.warning("Gemini returned %s, retrying in %ss", exc.code, delay)
            time.sleep(delay)


def generate_reply(user_id: str, text: str) -> str:
    # Serialize per user so rapid-fire messages don't interleave history
    with store.lock_for(user_id):
        history = store.get(user_id)
        chat = _client.chats.create(
            model=config.GEMINI_MODEL,
            config=_generation_config,
            history=history,
        )
        try:
            response = _send_with_retry(chat, text)
            reply = (response.text or "").strip()
        except Exception:
            log.exception("Gemini request failed for %s", user_id)
            return "Sorry, I'm having trouble thinking right now. Please try again in a moment."

        if not reply:
            return "Sorry, I couldn't come up with a response to that."

        store.save(user_id, chat.get_history())
        return reply
