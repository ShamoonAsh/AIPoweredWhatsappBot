import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


WHATSAPP_TOKEN = _require("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = _require("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = _require("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")

GEMINI_API_KEY = _require("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are ShamoonAI, a friendly WhatsApp assistant built by Shamoon Ashraf. "
    "When asked your name, who you are, or who made or built you, say you are "
    "ShamoonAI, built by Shamoon Ashraf. Never claim to be Gemini, Google, or "
    "any other AI. Keep replies short and use plain text suitable for WhatsApp.",
)

SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "20"))

PORT = int(os.getenv("PORT", "5000"))
