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

    system_prompt = f"""You are NOVA — a friendly, simple agricultural assistant for Ugandan farmers.

You speak like a helpful neighbor who knows farming well. You give practical, easy-to-follow advice.

USER: {user_name}
CROP CONTEXT: {crop_type}

RULES:
- Answer ANY farming question directly — crops, animals, soil, weather, market, money, tools, anything
- Be specific to Uganda: local varieties, UGX prices, Ugandan institutions (NARO, UCDA, NAADS)
- Use simple language a farmer can understand — no jargon
- Give step-by-step actions they can do TODAY
- If the question is in a local language (Luganda, Swahili, etc.), answer in English — translation happens later
- Always be helpful. Never say "tell me more specifically" — just answer what they asked
- Keep answers concise: 3-6 sentences for simple questions, longer for complex ones

UGANDAN FARMING QUICK REFERENCE:
- Coffee: Ruiru 11, NARO 1 varieties; spray copper for rust
- Maize: Longe 5, KH 600-23A; plant March & September; NPK at planting, CAN at 6 weeks
- Beans: NARO Bean 1, K131; intercrop with maize; 25kg/ha seed rate
- Banana: Matooke, Beer bananas; mulch with banana leaves
- Livestock: deworm every 3 months, vaccinate against FMD
- Seasons: Bimodal — Mar-May (first), Sept-Nov (second)
- Key orgs: NARO, UCDA, NAADS, UCA, Makerere University
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

    if "maize" in lowered or "corn" in lowered or "simb" in lowered:
        return (
            "How to plant maize in Uganda:\n\n"
            "1. VARIETY: Use Longe 5 or KH 600-23A (available from NAADS or KADP)\n"
            "2. TIMING: Plant in March (first season) or September (second season)\n"
            "3. LAND PREP: Plough twice, harrow once, make ridges 90cm apart\n"
            "4. SEED RATE: 25 kg/ha (about 500g per 10m row)\n"
            "5. PLANTING: 2 seeds per hole, 30cm apart, 5cm deep\n"
            "6. FERTILIZER: Apply NPK 17:17:17 at 4g per hole at planting. "
            "Side-dress with CAN at 6 weeks after emergence\n"
            "7. WEEDING: Weed at 3 weeks and 6 weeks after planting\n"
            "8. HARVEST: 3-4 months after planting when leaves turn brown\n\n"
            "What you can do right now: If you haven't planted yet, prepare your land "
            "and buy seed from an NAADS stockist this week."
        )

    if "coffee" in lowered:
        if "rust" in lowered or "leaf" in lowered:
            return (
                "Coffee leaf rust treatment:\n\n"
                "1. Spray Blue Shield (copper hydroxide) at 3g/L water — do it today\n"
                "2. Remove and burn badly infected leaves\n"
                "3. Prune low branches to 50cm above ground\n"
                "4. Plant Ruiru 11 or NARO 1 next season (rust-resistant)\n"
                "5. Apply 100g N/tree split across both rain seasons\n\n"
                "Available at: NAADS, UCA cooperative shops, or any agro-dealer.\n"
                "Reference: NARO Coffee Research Station, Mukono."
            )
        return (
            "Coffee farming in Uganda:\n\n"
            "1. VARIETY: Bugisu Arabica (1200-2000m altitude) or Robusta (below 1200m)\n"
            "2. PLANTING: 3m x 3m spacing, 2 seeds per hole, mulch with grass\n"
            "3. SHADE: Plant with shade trees (Erythrina or Calliandra)\n"
            "4. FERTILIZER: 100g N/tree per year, split into two applications\n"
            "5. PEST CONTROL: Spray copper-based fungicide for rust every 6 weeks\n"
            "6. HARVEST: Pick only red cherries, process within 24 hours\n\n"
            "What you can do right now: Walk through your coffee garden and check "
            "for orange spots on the underside of leaves (sign of rust)."
        )

    if "bean" in lowered or "njugu" in lowered:
        return (
            "Bean farming in Uganda:\n\n"
            "1. VARIETY: NARO Bean 1, K131, or Masooma (available from NAADS)\n"
            "2. TIMING: Plant March or August\n"
            "3. SEED RATE: 80-100 kg/ha (about 2kg per 10m row)\n"
            "4. INOCULANT: Treat seed with Rhizobium inoculant before planting\n"
            "5. SPACING: 50cm between rows, 20cm between plants, 2 seeds per hole\n"
            "6. FERTILIZER: DAP at planting (100kg/ha)\n"
            "7. HARVEST: 2-3 months, dry to 13% moisture before storage\n\n"
            "Tip: Interrow with maize for better land use and higher income."
        )

    if "chicken" in lowered or "poultry" in lowered or "nkoko" in lowered:
        return (
            "Poultry farming in Uganda:\n\n"
            "1. START: Buy 50 chicks from a certified hatchery (Inamas, NAADS)\n"
            "2. HOUSING: Chicken run (4 sq ft per bird), wire mesh floor\n"
            "3. FEED: Starter feed (0-8 weeks), Grower (8-20 weeks), Layer mash (20+ weeks)\n"
            "4. WATER: Clean water always available, add electrolytes during heat\n"
            "5. VACCINATION: Mareks (day 1), Newcastle (week 2, 6, 12), Deworm monthly\n"
            "6. EGG COLLECTION: Twice daily, store in cool place\n\n"
            "Earnings: 1 layer = 250-300 eggs/year = UGX 250,000-300,000 revenue."
        )

    if "weather" in lowered or "rain" in lowered or "season" in lowered:
        return (
            "Uganda farming seasons:\n\n"
            "FIRST SEASON: March - May (long rains, best for planting)\n"
            "DRY SEASON: June - August (harvesting, land preparation)\n"
            "SECOND SEASON: September - November (short rains, second planting)\n"
            "HOT SEASON: December - February (harvesting, drying crops)\n\n"
            "Tip: Always plant at the start of rains, not during heavy rain. "
            "Check NAADS forecasts before planting."
        )

    if "price" in lowered or "market" in lowered or "sell" in lowered:
        return (
            "Selling your produce in Uganda:\n\n"
            "1. LOCAL MARKETS: Sell directly to LCI/parish markets for best price\n"
            "2. COOPERATIVES: Join UCA (coffee), UNFI (beans), or district cooperatives\n"
            "3. NAADS: Register for market linkage support\n"
            "4. CONVERSION: Add value — dry beans, roast coffee, make flour\n"
            "5. STORAGE: Use hermetic bags (PICS) to store and sell when prices rise\n\n"
            "Tip: Prices are highest 2-3 months after harvest when supply drops."
        )

    if "soil" in lowered or "fertiliz" in lowered or "compost" in lowered:
        return (
            "Soil management in Uganda:\n\n"
            "1. TEST: Get soil tested at Makerere University (UGX 50,000)\n"
            "2. ORGANIC: Make compost from farm waste (2 months to decompose)\n"
            "3. NPK: Use 17:17:17 for most crops, apply at planting\n"
            "4. CAN: Top-dress with CAN at 6 weeks for maize, beans\n"
            "5. ROTATION: Rotate crops — maize → beans → groundnuts\n"
            "6. MULCH: Cover soil with banana leaves, grass, or crop residues\n\n"
            "Tip: Healthy soil = healthy crops. Start composting today."
        )

    return (
        f"Here's what I know about {text[:80]}:\n\n"
        "I can help you with:\n"
        "- Crop farming (coffee, maize, beans, banana, cassava)\n"
        "- Livestock (chickens, goats, cattle)\n"
        "- Soil and fertilizer advice\n"
        "- Market prices and selling\n"
        "- Weather and seasons\n"
        "- Pest and disease control\n\n"
        "Ask me anything specific about farming in Uganda!"
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
