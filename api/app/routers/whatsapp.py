"""WhatsApp Cloud API webhook endpoints.

Handles incoming messages from WhatsApp and routes them through the NOVA AI pipeline.
No authentication required — Meta validates webhook signatures.
"""

import hashlib
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response

from api.app.config import settings
from api.app.services.whatsapp import (
    download_media,
    parse_webhook_entry,
    send_text_message,
    verify_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


def _get_or_create_user(db, phone: str):
    """Get or create a Farm-to-Fork user by phone number."""
    from api.app.models.user import User

    user = db.query(User).filter(User.email == f"{phone}@whatsapp.farm2fork").first()
    if user:
        return user

    user = User(
        email=f"{phone}@whatsapp.farm2fork",
        full_name=f"WhatsApp Farmer {phone[-4:]}",
        hashed_password=hashlib.sha256(phone.encode()).hexdigest(),
        role="consumer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created WhatsApp user: %s (phone=%s)", user.id, phone)
    return user


def _handle_text_message(db, phone: str, text: str) -> str:
    """Process a text message through the AI pipeline and return a response."""
    from api.app.routers.voice import _build_live_context, _fallback_reason, _normalize, _reason
    from api.app.services.guardrails import guard_query

    passed, blocked = guard_query(text)
    if not passed:
        return blocked

    user = _get_or_create_user(db, phone)
    normalized = _normalize(text)

    if not settings.gemini_api_key:
        return _fallback_reason(normalized, text)

    live_ctx = _build_live_context(db, user.id, "general")
    return _reason(text, "general", [], user.full_name, live_context=live_ctx)


def _handle_image_message(db, phone: str, image_id: str) -> str:
    """Download and diagnose an image, return diagnostic advice."""
    from api.app.services.diagnostics import diagnose

    if not settings.whatsapp_token:
        return "Image diagnostics is not available right now. Please try again later."

    image_data = download_media(image_id, settings.whatsapp_token)
    if not image_data:
        return "I couldn't download the image. Please try sending it again."

    try:
        prediction, model = diagnose(image_data, "auto")
        return prediction.get("advice", "I analyzed your photo. Please consult a local extension worker for detailed advice.")
    except Exception as e:
        logger.error("WhatsApp image diagnosis failed: %s", e)
        return "I had trouble analyzing the photo. Please describe the symptoms in text and I'll do my best to help."


@router.get("/webhook")
async def webhook_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Meta webhook verification endpoint."""
    challenge = verify_webhook(hub_mode, hub_token, hub_challenge, settings.whatsapp_verify_token)
    if challenge:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def webhook_handler(request: Request):
    """Handle incoming WhatsApp messages."""
    from api.app.database import SessionLocal

    body = await request.json()

    if body.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    db = SessionLocal()
    try:
        for entry in body.get("entry", []):
            messages = parse_webhook_entry(entry)
            for msg in messages:
                phone = msg.get("from", "")
                if not phone:
                    continue

                response_text = None

                if msg.get("type") == "text":
                    text = msg.get("text", "")
                    if text:
                        response_text = _handle_text_message(db, phone, text)

                elif msg.get("type") == "image":
                    image_id = msg.get("image_id", "")
                    if image_id:
                        response_text = _handle_image_message(db, phone, image_id)

                if response_text and settings.whatsapp_token and settings.whatsapp_phone_number_id:
                    send_text_message(
                        settings.whatsapp_phone_number_id,
                        settings.whatsapp_token,
                        phone,
                        response_text,
                    )
    except Exception as e:
        logger.error("WhatsApp webhook error: %s", e)
    finally:
        db.close()

    return {"status": "ok"}
