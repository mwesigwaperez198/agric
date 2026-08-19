"""WhatsApp Cloud API integration for NOVA AI assistant.

Handles sending messages, downloading media, and webhook verification.
Uses the Meta Cloud API (hosted, no on-prem server needed).
"""

import hashlib
import hmac
import logging
import time

import httpx

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v19.0"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def verify_webhook(mode: str, token: str, challenge: str, verify_token: str) -> str | None:
    """Verify Meta webhook subscription. Returns challenge on success, None on failure."""
    mode = (mode or "").strip()
    token = (token or "").strip()
    verify_token = (verify_token or "").strip()
    logger.info("verify_webhook: mode=%r token=%r challenge=%r expected=%r match=%s",
                mode, token, challenge, verify_token, token == verify_token)
    if mode == "subscribe" and token == verify_token:
        logger.info("WhatsApp webhook verified")
        return challenge
    logger.warning("WhatsApp webhook verification failed: mode=%r token=%r expected=%r", mode, token, verify_token)
    return None


def send_text_message(phone_number_id: str, token: str, to: str, text: str) -> bool:
    """Send a text message via WhatsApp Cloud API."""
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text[:4000]},
    }
    try:
        resp = httpx.post(url, headers=_headers(token), json=payload, timeout=15)
        if resp.status_code != 200:
            logger.error("WhatsApp send failed %d: %s", resp.status_code, resp.text[:300])
            return False
        return True
    except Exception as e:
        logger.error("WhatsApp send error: %s", e)
        return False


def send_image_message(phone_number_id: str, token: str, to: str, image_id: str, caption: str = "") -> bool:
    """Send an image message via WhatsApp Cloud API (using media ID from upload)."""
    url = f"{GRAPH_API}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"id": image_id},
    }
    if caption:
        payload["image"]["caption"] = caption[:1024]
    try:
        resp = httpx.post(url, headers=_headers(token), json=payload, timeout=15)
        return resp.status_code == 200
    except Exception as e:
        logger.error("WhatsApp image send error: %s", e)
        return False


def download_media(media_id: str, token: str) -> bytes | None:
    """Download media from WhatsApp (images expire in 5 minutes)."""
    url = f"{GRAPH_API}/{media_id}"
    try:
        resp = httpx.get(url, headers=_headers(token), timeout=15)
        if resp.status_code != 200:
            logger.error("WhatsApp media download failed %d", resp.status_code)
            return None
        media_url = resp.json().get("url")
        if not media_url:
            return None
        media_resp = httpx.get(media_url, headers=_headers(token), timeout=30)
        if media_resp.status_code == 200:
            return media_resp.content
        return None
    except Exception as e:
        logger.error("WhatsApp media download error: %s", e)
        return None


def parse_webhook_entry(entry: dict) -> list[dict]:
    """Parse a single webhook entry into a list of simplified message dicts."""
    messages = []
    for change in entry.get("changes", []):
        value = change.get("value", {})
        for msg in value.get("messages", []):
            parsed = {
                "from": msg.get("from", ""),
                "id": msg.get("id", ""),
                "timestamp": msg.get("timestamp", ""),
                "type": msg.get("type", ""),
            }
            if msg.get("type") == "text":
                parsed["text"] = msg.get("text", {}).get("body", "")
            elif msg.get("type") == "image":
                parsed["image_id"] = msg.get("image", {}).get("id", "")
                parsed["caption"] = msg.get("image", {}).get("caption", "")
            elif msg.get("type") == "audio":
                parsed["audio_id"] = msg.get("audio", {}).get("id", "")
            messages.append(parsed)
    return messages
