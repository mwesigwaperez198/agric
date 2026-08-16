from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.app.deps import CurrentUser, DbSession
from api.app.models.chat import ChatMessage
from api.app.schemas.diagnostics import VoiceQueryOut, VoiceQueryRequest
from api.app.services.voice import (
    detect_and_translate,
    synthesize,
    transcribe,
    translate_response,
)

router = APIRouter(prefix="/voice", tags=["voice"])


class TextChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    crop_type: str = "coffee"
    locale: str = "en"


@router.post("/transcribe")
async def transcribe_audio(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
):
    """Transcribe audio with auto language detection."""
    data = await file.read()
    try:
        result = transcribe(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    text = result.get("text", "")
    detected_lang = result.get("language", "en")

    if text:
        try:
            translation = detect_and_translate(text, detected_lang)
            return {
                "text": text,
                "detected_language": translation["original_lang"],
                "english_text": translation["english_text"],
                "needs_translation": translation["needs_translation"],
            }
        except Exception:
            pass

    return {
        "text": text,
        "detected_language": detected_lang,
        "english_text": text,
        "needs_translation": detected_lang != "en",
    }


@router.post("/chat", response_model=VoiceQueryOut)
def voice_chat(
    body: VoiceQueryRequest,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
):
    """Full AI chat: detect language → translate → reason → translate back → store."""
    from api.app.services.guardrails import guard_query

    user_text = body.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Empty message")

    user_lang = body.detected_language or body.locale or "en"
    english_text = body.english_text or user_text

    passed, blocked = guard_query(english_text)
    if not passed:
        _store_message(db, user.id, "user", user_text, user_lang)
        _store_message(db, user.id, "assistant", blocked, user_lang)
        return VoiceQueryOut(answer=blocked, guardrail=False, dialect=user_lang)

    history = _get_history(db, user.id, limit=10)
    answer_en = _reason(english_text, body.crop_type, history, user.full_name)

    if user_lang != "en":
        background_tasks.add_task(_store_messages_bg, db, user.id, user_text, answer_en, user_lang)
        try:
            answer_local = translate_response(answer_en, user_lang)
        except Exception:
            answer_local = answer_en
    else:
        _store_message(db, user.id, "user", user_text, "en")
        _store_message(db, user.id, "assistant", answer_en, "en")
        answer_local = None

    tts = synthesize(answer_local or answer_en, user_lang)
    return VoiceQueryOut(
        answer=answer_en,
        translated=answer_local,
        tts_audio_url=tts["audio_url"],
        guardrail=True,
        dialect=user_lang,
    )


def _get_history(db: DbSession, user_id: int, limit: int = 10) -> list[dict]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows]


def _store_message(db: DbSession, user_id: int, role: str, content: str, lang: str = "en"):
    msg = ChatMessage(user_id=user_id, role=role, content=content, language=lang)
    db.add(msg)
    db.commit()


def _store_messages_bg(db, user_id, user_text, answer_en, user_lang):
    try:
        _store_message(db, user_id, "user", user_text, user_lang)
        _store_message(db, user_id, "assistant", answer_en, user_lang)
    except Exception:
        pass


def _reason(text: str, crop_type: str, history: list[dict], user_name: str) -> str:
    """GPT-4o reasoning engine with conversation memory."""
    from api.app.config import settings

    if not settings.whisper_api_key:
        return _fallback_reason(text, crop_type)

    import httpx

    system_prompt = f"""You are NOVA — an advanced agricultural AI reasoning engine for East African farmers.

You THINK before responding. You ANALYZE the question, CONSIDER conversation history, RESEARCH your knowledge, and DELIVER precise, actionable answers.

USER: {user_name}
CROP CONTEXT: {crop_type}

REASONING PROCESS:
1. UNDERSTAND the real question behind the words
2. CONTEXTUALIZE with conversation history
3. ANALYZE agricultural factors (climate, soil, season, market, pests)
4. SYNTHESIZE Ugandan research (NARO, UCDA, NaCORRI, Makerere)
5. DELIVER specific, actionable steps for TODAY

STYLE:
- Structured: headings, bullets, numbered steps
- Uganda-specific: local varieties, institutions, UGX prices
- Context-aware: reference previous conversation when relevant
- Practical: every answer ends with "What you can do right now"
- Cite: NARO, UCDA, NaCORRI, Makerere University

UGANDAN AGRICULTURE:
- Coffee: Bugisu Arabica (1200-2000m), Robusta (<1200m), Ruiru 11, NARO 1
- Maize: Longe 5, KH 600-23A — plant March & September
- Beans: NARO Bean 1, K131 — intercrop with maize
- Banana: Matooke, Beer bananas, Bogoya
- Livestock: Ankole cattle, Small East African goat
- Climate: Bimodal rainfall (Mar-May, Sept-Nov)
- Key orgs: NARO, UCDA, NaCORRI, UCA, NAADS, Makerere
"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "assistant" if msg["role"] == "assistant" else "user"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": text})

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
        json={"model": "gpt-4o", "max_tokens": 2000, "temperature": 0.7, "messages": messages},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _fallback_reason(text: str, crop_type: str) -> str:
    lowered = text.lower()
    if "rust" in lowered or ("leaf" in lowered and "coffee" in lowered):
        return (
            "Coffee leaf rust (Hemileia vastatrix) — here's my analysis:\n\n"
            "IDENTIFICATION: Orange-yellow powdery lesions on the underside of leaves.\n\n"
            "ROOT CAUSE: Fungus thrives at 22-28°C with >80% humidity. Peak risk during "
            "March-May and September-November rains. Spores spread by wind (up to 3km).\n\n"
            "IMMEDIATE ACTIONS:\n"
            "1. Spray Blue Shield (copper hydroxide) at 3g/L water — TODAY\n"
            "2. Remove and burn leaves with >5 infection spots\n"
            "3. Prune lower branches to 50cm above ground\n\n"
            "LONG-TERM:\n"
            "- Plant Ruiru 11 or NARO 1 (rust-resistant)\n"
            "- Apply 100g N/tree split across both rain seasons\n"
            "- Scout twice weekly during wet months\n\n"
            "WHAT YOU CAN DO RIGHT NOW: Spray Blue Shield within 2 hours. "
            "It works best within 48 hours of symptom appearance.\n\n"
            "Reference: NARO Coffee Research Station, Mukono."
        )
    return (
        f"I understand you're asking about {crop_type} farming in Uganda. "
        "Please tell me more specifically — disease, soil, market prices, or post-harvest — "
        "so I can give you the most accurate, actionable advice."
    )


@router.post("/text-chat", response_model=VoiceQueryOut)
def text_chat(body: TextChatRequest, user: CurrentUser, db: DbSession, background_tasks: BackgroundTasks):
    """Text-based AI chat with full reasoning and conversation memory."""
    from api.app.services.guardrails import guard_query

    user_text = body.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Empty message")

    passed, blocked = guard_query(user_text)
    if not passed:
        _store_message(db, user.id, "user", user_text, body.locale)
        _store_message(db, user.id, "assistant", blocked, body.locale)
        return VoiceQueryOut(answer=blocked, guardrail=False, dialect=body.locale)

    history = _get_history(db, user.id, limit=10)
    answer_en = _reason(user_text, body.crop_type, history, user.full_name)

    if body.locale != "en":
        background_tasks.add_task(_store_messages_bg, db, user.id, user_text, answer_en, body.locale)
        try:
            answer_local = translate_response(answer_en, body.locale)
        except Exception:
            answer_local = answer_en
    else:
        _store_message(db, user.id, "user", user_text, "en")
        _store_message(db, user.id, "assistant", answer_en, "en")
        answer_local = None

    tts = synthesize(answer_local or answer_en, body.locale)
    return VoiceQueryOut(
        answer=answer_en,
        translated=answer_local,
        tts_audio_url=tts["audio_url"],
        guardrail=True,
        dialect=body.locale,
    )


@router.get("/history")
def get_chat_history(user: CurrentUser, db: DbSession, limit: int = 50):
    """Get conversation history for the current user."""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "language": m.language,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]
