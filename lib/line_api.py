"""LINE Messaging API client — push and reply with HMAC signature verify."""
from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Optional

import requests

from .config import (
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_CHANNEL_SECRET,
    LINE_USER_ID,
)

_PUSH_URL = "https://api.line.me/v2/bot/message/push"
_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# LINE caps a text message at 5000 chars. Leave headroom for the truncation
# notice we append when over the limit.
_MAX_LEN = 4900


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _truncate(text: str) -> str:
    if len(text) <= _MAX_LEN:
        return text
    return text[:_MAX_LEN] + "\n\n…(訊息過長已截斷)"


def verify_signature(body: bytes, signature: str) -> bool:
    """Validate that an incoming webhook payload was signed by our channel."""
    if not signature or not LINE_CHANNEL_SECRET:
        return False
    digest = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def push_text(text: str, to: Optional[str] = None) -> None:
    """Send an unsolicited push message. Used by the cron handler."""
    target = to or LINE_USER_ID
    if not target:
        raise RuntimeError("LINE_USER_ID is not configured")
    payload = {
        "to": target,
        "messages": [{"type": "text", "text": _truncate(text)}],
    }
    r = requests.post(_PUSH_URL, headers=_headers(), json=payload, timeout=10)
    r.raise_for_status()


def reply_text(reply_token: str, text: str) -> None:
    """Reply to an incoming message. Must be called within 30s of the event."""
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": _truncate(text)}],
    }
    r = requests.post(_REPLY_URL, headers=_headers(), json=payload, timeout=10)
    r.raise_for_status()
