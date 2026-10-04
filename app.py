"""AI-powered WhatsApp bot: Meta WhatsApp Cloud API webhook + Google Gemini."""
import logging
import threading
from collections import OrderedDict

from flask import Flask, abort, request

from bot import config, gemini, whatsapp

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("bot")

app = Flask(__name__)

RESET_COMMANDS = {"/reset", "/new", "reset"}
HELP_TEXT = (
    "Hi! I'm ShamoonAI, an AI assistant built by Shamoon Ashraf. Just send me a message.\n\n"
    "Commands:\n/reset - start a new conversation\n/help - show this message"
)

# Meta may redeliver the same webhook; remember recent message IDs to skip duplicates
_seen_ids: OrderedDict[str, None] = OrderedDict()
_seen_lock = threading.Lock()


def _already_seen(message_id: str) -> bool:
    with _seen_lock:
        if message_id in _seen_ids:
            return True
        _seen_ids[message_id] = None
        if len(_seen_ids) > 1000:
            _seen_ids.popitem(last=False)
        return False


def handle_message(message: dict) -> None:
    sender = message["from"]
    message_id = message["id"]
    try:
        whatsapp.mark_as_read(message_id)

        if message.get("type") != "text":
            whatsapp.send_text(
                sender, "I can only read text messages for now.", reply_to=message_id
            )
            return

        text = message["text"]["body"].strip()
        log.info("Message from %s: %s", sender, text)

        command = text.lower()
        if command in RESET_COMMANDS:
            gemini.store.reset(sender)
            whatsapp.send_text(sender, "Conversation cleared. Let's start fresh!")
            return
        if command in {"/help", "/start"}:
            whatsapp.send_text(sender, HELP_TEXT)
            return

        reply = gemini.generate_reply(sender, text)
        whatsapp.send_text(sender, reply, reply_to=message_id)
        log.info("Replied to %s (%d chars)", sender, len(reply))
    except Exception:
        log.exception("Failed to handle message %s from %s", message_id, sender)


@app.get("/webhook")
def verify_webhook():
    """Meta calls this once when you register the webhook URL."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")
    if mode == "subscribe" and token == config.WHATSAPP_VERIFY_TOKEN:
        log.info("Webhook verified")
        return challenge, 200
    abort(403)


@app.post("/webhook")
def receive_webhook():
    if not whatsapp.verify_signature(
        request.get_data(), request.headers.get("X-Hub-Signature-256")
    ):
        log.warning("Rejected webhook with invalid signature")
        abort(401)

    data = request.get_json(silent=True) or {}
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            # "statuses" updates (sent/delivered/read) are ignored
            for message in value.get("messages", []):
                if _already_seen(message["id"]):
                    continue
                # Reply in the background: Meta retries if we don't answer within a few seconds
                threading.Thread(
                    target=handle_message, args=(message,), daemon=True
                ).start()

    return "OK", 200


PRIVACY_POLICY = """<!doctype html>
<html><head><meta charset="utf-8"><title>Privacy Policy</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6">
<h1>Privacy Policy</h1>
<p>This WhatsApp assistant replies to messages you send it using Google Gemini.</p>
<h2>What we collect</h2>
<p>Your WhatsApp phone number and the text of messages you send to the bot.</p>
<h2>How it is used</h2>
<p>Messages are sent to the Google Gemini API to generate a reply. Recent messages are kept
in server memory for up to 30 minutes so the bot can follow the conversation, and are never
written to disk, sold, or shared with anyone else.</p>
<h2>Deleting your data</h2>
<p>Send <b>/reset</b> to the bot to erase your conversation immediately. All conversation data
is also cleared whenever the server restarts.</p>
</body></html>"""


@app.get("/privacy")
def privacy_policy():
    return PRIVACY_POLICY, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/")
def health():
    return {"status": "running"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT)
