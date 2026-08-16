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
        _store_message(db, user.id, user_text, "user", "en")
        _store_message(db, user.id, answer_en, "assistant", "en")
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


def _store_message(db: DbSession, user_id: int, content: str, role: str, lang: str = "en"):
    msg = ChatMessage(user_id=user_id, role=role, content=content, language=lang)
    db.add(msg)
    db.commit()


def _store_messages_bg(db, user_id, user_text, answer_en, user_lang):
    try:
        _store_message(db, user_id, user_text, "user", user_lang)
        _store_message(db, user_id, answer_en, "assistant", user_lang)
    except Exception:
        pass


def _reason(text: str, crop_type: str, history: list[dict], user_name: str) -> str:
    """GPT-4o reasoning engine with conversation memory."""
    from api.app.config import settings

    if not settings.whisper_api_key:
        return _fallback_reason(text, crop_type)

    import httpx

    system_prompt = f"""You are NOVA — a smart, conversational AI assistant for Ugandan farmers.

THINK LIKE A HUMAN, NOT A TEXTBOOK. When someone asks a question, figure out what they REALLY want to know, even if they misspell words, use wrong vocabulary, or ask in a confusing way.

YOU ARE LIKE GOOGLE ASSISTANT:
- If someone says "how to grow beans am not getting good yeilds" — understand they want to improve bean yields
- If someone says "my kafifi is dying" — understand kafifi means coffee and help with that
- If someone says "when do I put the seed in the ground for maize" — understand they mean planting season
- If someone says "the insects are eating my plants" — help identify and treat pest problems
- If someone types in Luganda, Swahili, or any local language — answer in English (translation happens later)
- Handle misspellings, broken English, and informal speech naturally

STYLE:
- Talk like a knowledgeable friend, not a textbook
- Be warm and encouraging — farming is hard work
- Use simple, everyday language
- Give practical steps they can follow TODAY
- Mention specific products, shops, and prices in UGX when relevant
- If you're not sure about something, say so honestly — don't make things up
- Keep it concise: short paragraphs, not walls of text
- End with ONE actionable thing they can do right now

UGANDAN AGRICULTURE:
- Coffee: Ruiru 11, NARO 1; spray copper for rust; pick only red cherries
- Maize: Longe 5, KH 600-23A; plant March & September; NPK at planting, CAN at 6 weeks
- Beans: NARO Bean 1, K131; intercrop with maize; 25kg/ha seed rate
- Banana: Matooke, Beer bananas; mulch with banana leaves
- Livestock: deworm every 3 months, vaccinate against FMD
- Seasons: Bimodal — Mar-May (first), Sept-Nov (second)
- Key orgs: NARO, UCDA, NAADS, UCA, Makerere University

USER: {user_name}
CROP CONTEXT: {crop_type}
"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "assistant" if msg["role"] == "assistant" else "user"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": text})

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
        json={"model": "gpt-4o", "max_tokens": 1500, "temperature": 0.7, "messages": messages},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _fallback_reason(text: str, crop_type: str) -> str:
    lowered = text.lower()

    if "maize" in lowered or "corn" in lowered or "simb" in lowered or "posho" in lowered:
        return (
            "To grow maize in Uganda, here's what works:\n\n"
            "Plant Longe 5 or KH 600-23A seeds during the March or September rains. "
            "Prepare your land well — plough twice, make ridges 90cm apart. "
            "Put 2 seeds per hole, 30cm apart, 5cm deep. Use NPK at planting and CAN at 6 weeks.\n\n"
            "Weed at 3 and 6 weeks. Harvest in 3-4 months when leaves turn brown.\n\n"
            "Start now: buy seed from an NAADS stockist and prepare your land this week."
        )

    if "coffee" in lowered or "kawa" in lowered or "kafifi" in lowered:
        if "rust" in lowered or "leaf" in lowered or "yellow" in lowered or "spot" in lowered:
            return (
                "Those yellow spots on your coffee leaves sound like coffee leaf rust. "
                "It's common during the rainy seasons.\n\n"
                "What to do right now:\n"
                "1. Spray Blue Shield (copper hydroxide) at 3g/L water — today if possible\n"
                "2. Remove and burn leaves with many spots\n"
                "3. Prune low branches to about 50cm above ground\n\n"
                "For next season, plant Ruiru 11 or NARO 1 — they resist rust. "
                "Apply 100g N/tree split across both rain seasons.\n\n"
                "Find Blue Shield at NAADS, UCA shops, or any agro-dealer."
            )
        return (
            "For coffee in Uganda, here's the basics:\n\n"
            "Use Bugisu Arabica (if you're above 1200m) or Robusta (below 1200m). "
            "Plant 3m x 3m apart, with shade trees like Erythrina. "
            "Mulch with grass, apply 100g N/tree per year.\n\n"
            "Spray copper fungicide every 6 weeks for rust. "
            "Pick only red cherries and process within 24 hours.\n\n"
            "Walk through your garden today and check for orange spots on leaf undersides — "
            "that's the first sign of rust."
        )

    if "bean" in lowered or "njugu" in lowered or "nkwology" in lowered:
        return (
            "For beans in Uganda, NARO Bean 1 or K131 work well. "
            "Plant in March or August, about 2 seeds per hole, 20cm apart.\n\n"
            "Use DAP at planting (about 100kg/ha). "
            "Inoculate seed with Rhizobium for better yields. "
            "Interrow with maize for better land use.\n\n"
            "Harvest in 2-3 months. Dry to 13% moisture before storing."
        )

    if "chicken" in lowered or "poultry" in lowered or "nkoko" in lowered:
        return (
            "For poultry in Uganda, start with 50 chicks from a certified hatchery like Inamas. "
            "Give them starter feed for 8 weeks, then grower feed.\n\n"
            "House them in a chicken run with wire mesh floor. "
            "Vaccinate for Mareks (day 1), Newcastle (weeks 2, 6, 12), and deworm monthly.\n\n"
            "One layer gives about 250 eggs/year — that's UGX 250,000-300,000 revenue."
        )

    if "weather" in lowered or "rain" in lowered or "season" in lowered:
        return (
            "Uganda has two planting seasons:\n\n"
            "First season: March to May — best for most crops\n"
            "Second season: September to November — good for beans and maize\n\n"
            "Always plant at the start of rains, not during heavy rain. "
            "Check NAADS forecasts before you plant."
        )

    if "price" in lowered or "market" in lowered or "sell" in lowered or "how much" in lowered:
        return (
            "To get the best prices for your produce:\n\n"
            "Sell directly at local markets — you cut out middlemen. "
            "Join a cooperative like UCA for coffee or UNFI for beans. "
            "Add value by drying, roasting, or making flour.\n\n"
            "Store in hermetic bags (PICS) and sell 2-3 months after harvest when supply drops."
        )

    if "soil" in lowered or "fertiliz" in lowered or "compost" in lowered or "manure" in lowered:
        return (
            "For healthy soil in Uganda:\n\n"
            "Get your soil tested at Makerere University (about UGX 50,000). "
            "Use NPK 17:17:17 for most crops at planting, CAN for top-dressing.\n\n"
            "Make compost from farm waste — it takes about 2 months. "
            "Rotate crops: maize, then beans, then groundnuts.\n\n"
            "Start composting today — it's free fertilizer."
        )

    return (
        f"I understand you're asking about: {text[:100]}\n\n"
        "I can help with farming in Uganda — crops, livestock, soil, weather, "
        "market prices, pest control, and more.\n\n"
        "Tell me more about what you need help with, and I'll give you practical advice."
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
        _store_message(db, user.id, user_text, "user", body.locale)
        _store_message(db, user.id, blocked, "assistant", body.locale)
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
        _store_message(db, user.id, user_text, "user", "en")
        _store_message(db, user.id, answer_en, "assistant", "en")
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
