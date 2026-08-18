"""WhatsApp Cloud API webhook endpoints.

Handles incoming messages from WhatsApp and routes them through the NOVA AI pipeline.
No authentication required — Meta validates webhook signatures.
"""

import hashlib
import logging
import secrets

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


def _generate_pin() -> str:
    """Generate a random 4-digit PIN (never starts with 0)."""
    first = str(secrets.randbelow(9) + 1)
    rest = "".join(str(secrets.randbelow(10)) for _ in range(3))
    return first + rest


def _get_or_create_user(db, phone: str):
    """Get or create a Farm-to-Fork user by phone number.

    On first contact, generates a 4-digit PIN, hashes it as the password,
    and sends it back via WhatsApp so the farmer can log into the web app.
    """
    from api.app.models.user import User
    from api.app.security import hash_password

    user = db.query(User).filter(User.phone == phone).first()
    if user:
        return user, False

    pin = _generate_pin()
    user = User(
        email=f"{phone}@whatsapp.farm2fork",
        phone=phone,
        full_name=f"Farmer {phone[-4:]}",
        password_hash=hash_password(pin),
        role="consumer",
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created WhatsApp user: %s (phone=%s)", user.id, phone)

    if settings.whatsapp_token and settings.whatsapp_phone_number_id:
        welcome = (
            f"Welcome to NOVA Farm-to-Fork! Your account is ready.\n\n"
            f"Login details:\n"
            f"Phone: {phone}\n"
            f"PIN: {pin}\n\n"
            f"Use these to log in at:\nhttps://12d2e267.agric-b35.pages.dev/login\n\n"
            f"Ask me anything about farming — send text or a photo of your crops!"
        )
        send_text_message(settings.whatsapp_phone_number_id, settings.whatsapp_token, phone, welcome)

    return user, True


def _handle_text_message(db, phone: str, text: str) -> str:
    """Process a text message through the AI pipeline and return a response."""
    from api.app.routers.voice import _build_live_context, _fallback_reason, _normalize, _reason
    from api.app.services.guardrails import guard_query

    passed, blocked = guard_query(text)
    if not passed:
        return blocked

    user, is_new = _get_or_create_user(db, phone)
    normalized = _normalize(text)

    if is_new:
        return (
            "Your account is set up! Use the PIN I just sent you to log in to the web app.\n\n"
            "Now — how can I help with your farming today? Send me a question or a photo of your crops."
        )

    if not settings.gemini_api_key:
        return _fallback_reason(normalized, text)

    live_ctx = _build_live_context(db, user.id, "general")
    return _reason(text, "general", [], user.full_name, live_context=live_ctx)


def _handle_image_message(db, phone: str, image_id: str, caption: str = "") -> str:
    """Download an image, run full Gemini pipeline (diagnosis + market + weather), return advice."""
    from api.app.routers.voice import _build_live_context
    from api.app.services.diagnostics import diagnose

    if not settings.whatsapp_token:
        return "Image diagnostics is not available right now. Please try again later."

    user, _ = _get_or_create_user(db, phone)
    image_data = download_media(image_id, settings.whatsapp_token)
    if not image_data:
        return "I couldn't download the image. Please try sending it again."

    try:
        prediction, model = diagnose(image_data, "auto", note=caption or None)
        diagnosis = prediction.get("advice", "I analyzed your photo.")

        live_ctx = _build_live_context(db, user.id, prediction.get("label", "general"))

        if live_ctx and settings.gemini_api_key:
            import httpx
            followup_prompt = (
                f"A farmer sent a crop photo and I diagnosed it as: {prediction.get('label', 'unknown')} "
                f"(confidence: {prediction.get('confidence', 0)}). "
                f"Condition summary: {prediction.get('condition_summary', 'N/A')}. "
                f"Immediate actions: {prediction.get('immediate_actions', [])}. "
                f"Based on this diagnosis AND the live context below, provide a comprehensive "
                f"personalized recommendation covering: market implications, treatment plan with "
                f"UGX costs, and weather-adjusted timing.\n\n{live_ctx}"
            )
            try:
                resp = httpx.post(
                    "https://generativelanguage.googleapis.com/v1beta/interactions",
                    headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
                    json={"model": "gemini-3.5-flash", "input": followup_prompt},
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for step in data.get("steps", []):
                        for content in step.get("content", []):
                            if content.get("type") == "text" and content.get("text"):
                                return f"*Crop Diagnosis*\n{diagnosis}\n\n*Personalized Advice*\n{content['text'].strip()}"
            except Exception as e:
                logger.warning("Gemini follow-up failed: %s", e)

        return diagnosis
    except Exception as e:
        logger.error("WhatsApp image diagnosis failed: %s", e)
        return "I had trouble analyzing the photo. Please describe the symptoms in text and I'll do my best to help."


def _handle_audio_message(db, phone: str, audio_id: str) -> str:
    """Download audio, transcribe with Whisper, route through text pipeline."""
    if not settings.whatsapp_token:
        return "Voice messages are not available right now. Please type your question."

    audio_data = download_media(audio_id, settings.whatsapp_token)
    if not audio_data:
        return "I couldn't download the audio. Please try again or type your question."

    if not settings.whisper_api_key:
        return "Voice transcription is not configured. Please type your question and I'll help!"

    try:
        from api.app.services.voice import transcribe
        result = transcribe(audio_data)
        text = result.get("text", "")
        if not text:
            return "I couldn't understand the audio. Please try speaking clearly or type your question."
        logger.info("WhatsApp audio transcribed: %s", text[:100])
        return _handle_text_message(db, phone, text)
    except Exception as e:
        logger.error("WhatsApp audio transcription failed: %s", e)
        return "I had trouble understanding the audio. Please type your question."


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------


@router.get("/webhook")
async def webhook_verify(request: Request):
    """Meta webhook verification endpoint."""
    hub_mode = request.query_params.get("hub.mode", "")
    hub_token = request.query_params.get("hub.verify_token", "")
    hub_challenge = request.query_params.get("hub.challenge", "")
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
                        caption = msg.get("caption", "")
                        response_text = _handle_image_message(db, phone, image_id, caption)

                elif msg.get("type") == "audio":
                    audio_id = msg.get("audio_id", "")
                    if audio_id:
                        response_text = _handle_audio_message(db, phone, audio_id)

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
