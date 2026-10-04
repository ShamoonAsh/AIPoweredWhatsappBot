"""Thin client for the Meta WhatsApp Cloud API."""
import hashlib
import hmac
import logging

import requests

from . import config

log = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096  # WhatsApp text message limit

_session = requests.Session()
_session.headers.update(
    {
        "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
)


def _messages_url() -> str:
    return (
        f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/"
        f"{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )


def _post(payload: dict) -> None:
    resp = _session.post(_messages_url(), json=payload, timeout=15)
    if not resp.ok:
        log.error("WhatsApp API error %s: %s", resp.status_code, resp.text)
    resp.raise_for_status()


def _chunks(text: str, size: int = MAX_MESSAGE_LENGTH):
    """Split long text into WhatsApp-sized pieces, preferring newline breaks."""
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut <= 0:
            cut = size
        yield text[:cut]
        text = text[cut:].lstrip("\n")
    if text:
        yield text


def send_text(to: str, body: str, reply_to: str | None = None) -> None:
    for i, chunk in enumerate(_chunks(body)):
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": chunk},
        }
        if reply_to and i == 0:
            payload["context"] = {"message_id": reply_to}
        _post(payload)


def mark_as_read(message_id: str) -> None:
    try:
        _post(
            {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            }
        )
    except requests.RequestException:
        log.warning("Could not mark message %s as read", message_id)


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Validate X-Hub-Signature-256. Skipped when no app secret is configured."""
    if not config.WHATSAPP_APP_SECRET:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        config.WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))
