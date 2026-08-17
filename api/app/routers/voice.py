import json
import logging
import re
import unicodedata

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from api.app.deps import CurrentUser, DbSession
from api.app.models.biosensor import BiosensorReading
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
    from api.app.services.guardrails import guard_query

    user_text = body.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Empty message")

    user_lang = body.detected_language or body.locale or "en"
    english_text = body.english_text or user_text

    passed, blocked = guard_query(english_text)
    if not passed:
        _store_message(db, user.id, user_text, "user", user_lang)
        _store_message(db, user.id, blocked, "assistant", user_lang)
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


@router.post("/text-chat", response_model=VoiceQueryOut)
def text_chat(body: TextChatRequest, user: CurrentUser, db: DbSession, background_tasks: BackgroundTasks):
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
    live_ctx = _build_live_context(db, user.id, body.crop_type)
    answer_en = _reason(user_text, body.crop_type, history, user.full_name, live_context=live_ctx)

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


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_live_context(db: DbSession, user_id: int, crop_type: str) -> str:
    """Build a live data context block from biosensor readings and weather."""
    try:
        from datetime import UTC, datetime

        from api.app.models.user import Farm
        from api.app.services.climate import format_weather_context

        farm_ids = [f.id for f in db.query(Farm.id).filter(Farm.owner_id == user_id).all()]

        weather_ctx = ""

        if farm_ids:
            farm = db.query(Farm).filter(Farm.id.in_(farm_ids)).first()
            if farm and farm.latitude and farm.longitude:
                location_name = farm.region or farm.name or ""
                weather_ctx = format_weather_context(farm.latitude, farm.longitude, location_name)

        if not farm_ids:
            reading = (
                db.query(BiosensorReading)
                .order_by(BiosensorReading.received_at.desc())
                .first()
            )
        else:
            reading = (
                db.query(BiosensorReading)
                .filter(BiosensorReading.farm_id.in_(farm_ids))
                .order_by(BiosensorReading.received_at.desc())
                .first()
            )
            if not reading:
                reading = (
                    db.query(BiosensorReading)
                    .order_by(BiosensorReading.received_at.desc())
                    .first()
                )

        sensor_ctx = ""
        if reading:
            payload = reading.payload or {}
            parts = ["[LIVE SENSOR DATA]"]
            parts.append(f"Device: {reading.device_id}")
            parts.append(f"Crop: {reading.crop_name or crop_type}")
            parts.append(f"Threat Level: {reading.threat_level} (risk score: {reading.risk_score})")
            if reading.threats:
                parts.append(f"Active Threats: {', '.join(str(t) for t in reading.threats)}")

            for key in ["soil_moisture", "soil_temp", "soil_ph", "nitrogen", "phosphorus", "potassium",
                         "air_temp", "humidity", "light_lux", "co2_ppm", "rainfall_mm"]:
                if key in payload and payload[key] is not None:
                    label = key.replace("_", " ").title()
                    unit = {"soil_moisture": "%", "soil_temp": "°C", "soil_ph": "", "nitrogen": "ppm",
                             "phosphorus": "ppm", "potassium": "ppm", "air_temp": "°C", "humidity": "%",
                             "light_lux": " lux", "co2_ppm": " ppm", "rainfall_mm": " mm"}.get(key, "")
                    parts.append(f"{label}: {payload[key]}{unit}")

            if reading.read_at:
                age = datetime.now(UTC) - reading.read_at.replace(tzinfo=UTC)
                mins = int(age.total_seconds() / 60)
                if mins < 1440:
                    parts.append(f"Reading age: {mins} minutes ago")
                else:
                    parts.append(f"Reading age: {mins // 1440} days ago")

            parts.append("[/LIVE SENSOR DATA]")
            sensor_ctx = "\n".join(parts) + "\n\n"

        return weather_ctx + sensor_ctx
    except Exception as e:
        logger.warning("Failed to build live context: %s", e)
        return ""


def _reason(text: str, crop_type: str, history: list[dict], user_name: str, live_context: str = "") -> str:
    from api.app.config import settings

    normalized = _normalize(text)

    if not settings.gemini_api_key:
        logger.warning("No GEMINI_API_KEY configured — using fallback")
        return _fallback_reason(normalized, text)

    import httpx

    system_instruction = f"""You are NOVA, an expert AI farming assistant for Ugandan farmers. You are as knowledgeable as Google Assistant and as friendly as Meta AI.

PERSONALITY:
- Warm, encouraging, and patient — like a knowledgeable friend who is also an agronomist
- Use simple English that any farmer can understand
- You understand misspellings, broken English, and local language words (Luganda, Swahili, Acholi, Runyankore)
- Greet back warmly when greeted — say hi, use their name, ask how you can help

RESPONSE STYLE — comprehensive like Google Assistant or Meta AI:
- Give THOROUGH, well-structured answers — not one-liners
- Use bullet points and clear paragraphs for readability
- Include specific details: UGX prices, product names, exact dosages, variety names, step-by-step instructions
- When you know current market prices or weather, share them (use Google Search)
- Cover the topic fully: what it is, why it matters, what to do, what products to use, where to buy them, how much they cost
- Include both immediate actions AND long-term strategies
- Mention specific Ugandan institutions when relevant (NAADS, NARO, UCDA, district agricultural offices, Makerere University)
- End with a clear, actionable next step

UGANDA AGRICULTURE QUICK FACTS:
- Two rain seasons: March-May (first), September-November (second)
- Key crops: coffee (Arabica above 1200m, Robusta below), maize, beans, bananas (matooke), cassava, tea, vanilla
- Common varieties: Ruiru 11, NARO 1 (coffee), Longe 5, KH 600-23A (maize), NARO Bean 1, K131 (beans), NAROCASS 1 (cassava)
- Prices in UGX: coffee cherry 1,000-3,000/kg, maize grain 800-1,500/kg, beans 2,500-4,000/kg
- Key products: Blue Shield (copper fungicide), NPK 17:17:17, CAN, DAP, Ridomil Gold, Albendazole (dewormer)
- Institutions: NAADS (extension), NARO (research), UCDA (coffee), district agricultural offices

User: {user_name}
Primary crop: {crop_type}

Answer the question thoroughly and comprehensively. Be as helpful and detailed as Google Assistant."""

    full_input = f"{live_context}{system_instruction}\n\nUser question: {text}" if live_context else f"{system_instruction}\n\nUser question: {text}"

    try:
        resp = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
            json={
                "model": "gemini-3.5-flash",
                "input": full_input,
            },
            timeout=45,
        )
        if resp.status_code != 200:
            logger.error("Gemini API error %d: %s", resp.status_code, resp.text[:500])
            return _fallback_reason(normalized, text)

        data = resp.json()
        steps = data.get("steps", [])
        text_parts = []
        for step in steps:
            for content in step.get("content", []):
                if content.get("type") == "text" and content.get("text"):
                    text_parts.append(content["text"])

        if text_parts:
            return "\n".join(text_parts).strip()

        logger.warning("Gemini returned no text steps: %s", json.dumps(data)[:500])
        return _fallback_reason(normalized, text)

    except httpx.TimeoutException:
        logger.error("Gemini API timeout for query: %s", text[:100])
        return _fallback_reason(normalized, text)
    except Exception as e:
        logger.error("Gemini API exception: %s", e)
        return _fallback_reason(normalized, text)


def _fallback_reason(normalized: str, original: str) -> str:
    # Greetings
    if any(w in normalized for w in ["hello", "hi ", "hi!", "hey", "good morning", "good evening", "good afternoon", "nambye", "webale", "jambo"]):
        return (
            "Hello! I'm NOVA, your farming assistant. "
            "I can help you with crops, livestock, soil, weather, market prices — anything about farming in Uganda. "
            "What would you like to know?"
        )

    # Pruning
    if "prun" in normalized or "cut" in normalized and ("branch" in normalized or "tree" in normalized):
        return (
            "Pruning depends on what you're growing. Here's a quick guide:\n\n"
            "Coffee: Remove suckers below 50cm. Keep 2-3 main stems. Cut horizontal branches. "
            "Best time: right after harvest.\n\n"
            "Fruit trees (mango, avocado): Remove dead or crossing branches. "
            "Cut at a 45-degree angle just above a bud. Open the center for light and air.\n\n"
            "General rule: Use a sharp, clean knife or secateurs. Cut just above a bud or joint. "
            "Remove dead, diseased, or crossing branches first. Don't remove more than 1/3 of the tree at once.\n\n"
            "Start by walking through your garden and identifying any dead or diseased branches to remove today."
        )

    # Banana/plantain
    if "banana" in normalized or "matooke" in normalized or "banna" in normalized or "banas" in normalized or "plantain" in normalized:
        if "prun" in normalized or "cut" in normalized or "remove" in normalized:
            return (
                "For banana pruning:\n\n"
                "Remove dead or yellow leaves first — they harbour pests. "
                "Keep only 6-8 healthy leaves per mat. Remove excess suckers — keep one main stem and one follower. "
                "Cut old stems after they finish fruiting.\n\n"
                "Do this monthly. It improves airflow and reduces disease.\n\n"
                "Go to your banana garden today and remove any completely dead leaves."
            )
        return (
            "To grow bananas (matooke) in Uganda:\n\n"
            "Plant disease-free suckers (15-20kg weight) during the rains. "
            "Space 3m x 3m apart. Dig holes 60cm deep, mix with compost and topsoil.\n\n"
            "Mulch heavily with banana leaves or grass — bananas love moisture. "
            "Remove excess suckers regularly. Apply NPK at planting and top-dress every 3 months.\n\n"
            "Harvest in 9-12 months when the fruit ridges fill out. "
            "Popular varieties: Bogoya (sweet), Nakitembe (cooking), Beer bananas.\n\n"
            "Start by getting good suckers from NAADS or a neighboring healthy plantation."
        )

    # Maize/corn
    if any(w in normalized for w in ["maize", "corn", "posho", "simb", "wolimawo"]):
        if "prun" in normalized or "thin" in normalized:
            return (
                "For maize, you don't prune — you thin. If seeds are too close, remove weaker seedlings "
                "to leave one strong plant every 30cm. Do this at 2 weeks after emergence.\n\n"
                "Also remove any suckers from the base if they appear."
            )
        if "harvest" in normalized or "pick" in normalized or "ready" in normalized:
            return (
                "Maize is ready to harvest when leaves turn brown and dry, about 3-4 months after planting. "
                "Break a kernel — if it's hard and dents when pressed, it's ready.\n\n"
                "Harvest in the morning, husk immediately, and dry on a raised platform for 5-7 days "
                "until moisture is below 13%. Store in hermetic bags (PICS) to prevent weevils."
            )
        return (
            "To grow maize in Uganda:\n\n"
            "Plant Longe 5 or KH 600-23A during March or September rains. "
            "Plough twice, make ridges 90cm apart. "
            "Put 2 seeds per hole, 30cm apart, 5cm deep.\n\n"
            "Use NPK 17:17:17 at planting (about 4g per hole). "
            "Side-dress with CAN at 6 weeks after emergence. Weed at 3 and 6 weeks.\n\n"
            "Harvest in 3-4 months when leaves turn brown.\n\n"
            "Prepare your land and buy seed from an NAADS stockist this week."
        )

    # Coffee
    if any(w in normalized for w in ["coffee", "kawa", "kafifi", "cafe"]):
        if "rust" in normalized or "yellow" in normalized or "spot" in normalized or "disease" in normalized:
            return (
                "Those yellow/orange spots are coffee leaf rust. It's very common in Uganda's rainy seasons.\n\n"
                "What to do now:\n"
                "1. Spray Blue Shield (copper hydroxide) at 3g/L water — today\n"
                "2. Remove and burn badly infected leaves\n"
                "3. Prune low branches to 50cm above ground\n\n"
                "For next season, plant Ruiru 11 or NARO 1 — they resist rust. "
                "Apply 100g N/tree split across both rain seasons.\n\n"
                "Get Blue Shield at NAADS, UCA shops, or any agro-dealer."
            )
        if "prun" in normalized or "cut" in normalized:
            return (
                "Coffee pruning tips:\n\n"
                "Remove water shoots (vertical growing suckers) from the main stem. "
                "Keep 2-3 main stems per tree. Remove branches below 50cm from the ground.\n\n"
                "Cut at a 45-degree angle. Remove dead or crossing branches. "
                "Best time: right after the main harvest.\n\n"
                "Good pruning increases yield by 30-50% and makes spraying easier.\n\n"
                "Walk through your coffee garden today and remove any water shoots you see."
            )
        return (
            "For coffee in Uganda:\n\n"
            "Use Bugisu Arabica above 1200m or Robusta below 1200m. "
            "Plant 3m x 3m apart with shade trees (Erythrina, Calliandra). "
            "Mulch with grass, apply 100g N/tree per year.\n\n"
            "Spray copper fungicide every 6 weeks for rust. "
            "Pick only red cherries and process within 24 hours.\n\n"
            "Walk through your garden today and check leaf undersides for orange spots."
        )

    # Beans
    if any(w in normalized for w in ["bean", "njugu", "nkwology", "lentil"]):
        if "prun" in normalized or "thin" in normalized:
            return (
                "You don't prune beans. If they're too crowded, thin to 2 plants per station "
                "when they're 2 weeks old. This gives each plant room to grow."
            )
        return (
            "For beans in Uganda, use NARO Bean 1 or K131. "
            "Plant in March or August — 2 seeds per hole, 20cm apart, rows 50cm apart.\n\n"
            "Use DAP at planting (about 100kg/ha). Inoculate seed with Rhizobium for better yields. "
            "Interrow with maize for better land use.\n\n"
            "Harvest in 2-3 months. Dry to 13% moisture before storing."
        )

    # Chicken/poultry
    if any(w in normalized for w in ["chicken", "poultry", "nkoko", "egg", "hen", "cock"]):
        if "how much" in normalized or "price" in normalized or "cost" in normalized:
            return (
                "Chicken costs in Uganda:\n\n"
                "Day-old chicks: UGX 3,000-5,000 each (Inamas, Uzima)\n"
                "Grower feed: UGX 120,000-150,000 per 50kg bag\n"
                "Layer mash: UGX 140,000-170,000 per 50kg bag\n"
                "A full-grown local chicken: UGX 25,000-40,000\n"
                "One layer produces 250-300 eggs/year at UGX 500-800 each\n\n"
                "You can start with 50 chicks for about UGX 500,000 total investment."
            )
        return (
            "For poultry in Uganda, start with 50 chicks from a certified hatchery like Inamas. "
            "Give starter feed for 8 weeks, then grower feed.\n\n"
            "House them with wire mesh floor, clean water always available. "
            "Vaccinate: Mareks (day 1), Newcastle (weeks 2, 6, 12). Deworm monthly.\n\n"
            "One layer gives about 250 eggs/year — UGX 250,000-300,000 revenue."
        )

    # Goats/cattle/livestock
    if any(w in normalized for w in ["goat", "cattle", "cow", "cowp", "livestock", "animal", "farming animal"]):
        if "prun" in normalized or "castrat" in normalized:
            return (
                "For livestock management:\n\n"
                "Castrate male animals you don't want for breeding at 6 months. "
                "This makes them calmer and improves meat quality.\n\n"
                "Dehorn goats at 2-4 weeks using a hot iron or paste. "
                "Remove any extra teats from goats at birth."
            )
        return (
            "For livestock in Uganda:\n\n"
            "Deworm every 3 months using Albendazole or Ivermectin. "
            "Vaccinate against Foot and Mouth Disease (FMD) twice a year.\n\n"
            "For goats: Small East African breed is hardy. "
            "Give each goat 4-6 sq meters of shelter. Browse is their main feed.\n\n"
            "For cattle: Ankole longhorn is heat-tolerant. "
            "Supplement with Napier grass during dry season.\n\n"
            "Take a dewormer to your animals this week."
        )

    # Cassava
    if "cassava" in normalized or "muhogo" in normalized:
        return (
            "For cassava in Uganda:\n\n"
            "Plant NAROCASS 1 or local varieties. Use stem cuttings 20cm long, "
            "planted at 1m x 1m spacing.\n\n"
            "Cassava is drought-tolerant but needs good drainage. "
            "Harvest in 12-18 months. Test for Cassava Mosaic Disease — "
            "if leaves have yellow patterns, remove affected plants.\n\n"
            "Store roots in the ground until needed — they keep well for months."
        )

    # Fertilizer/soil/compost
    if any(w in normalized for w in ["fertiliz", "soil", "compost", "manure", "nutrient", "npk", "can "]):
        return (
            "For soil health in Uganda:\n\n"
            "Get your soil tested at Makerere University (about UGX 50,000). "
            "Use NPK 17:17:17 at planting for most crops. "
            "CAN for top-dressing maize and beans at 6 weeks.\n\n"
            "Make compost: pile farm waste, add ash and animal manure, water regularly. "
            "Ready in 2 months. Use 2-3 kg per planting hole.\n\n"
            "Rotate crops: maize, then beans, then groundnuts.\n\n"
            "Start a compost pile today — it's free fertilizer."
        )

    # Weather/season/rain
    if any(w in normalized for w in ["weather", "rain", "season", "drought", "flood"]):
        return (
            "Uganda has two planting seasons:\n\n"
            "First season: March to May — best for maize, beans, coffee\n"
            "Second season: September to November — good for beans, maize, groundnuts\n\n"
            "Plant at the start of rains, not during heavy downpour. "
            "Check NAADS forecasts. During dry season, irrigate and mulch to conserve moisture.\n\n"
            "Now is a good time to prepare your land for the next season."
        )

    # Harvest/storage
    if any(w in normalized for w in ["harvest", "stor", "dry", "post-harvest"]):
        return (
            "Post-harvest tips for Uganda:\n\n"
            "Dry crops to 13% moisture (maize: 5-7 days on raised platform). "
            "Use hermetic bags (PICS) — they prevent weevils without chemicals.\n\n"
            "Store in a cool, dry place off the ground. "
            "Check weekly for moisture or insects.\n\n"
            "Sell 2-3 months after harvest when market prices rise."
        )

    # Market/sell/price/money
    if any(w in normalized for w in ["price", "market", "sell", "money", "cost", "buy", "how much", "worth"]):
        return (
            "To get the best prices:\n\n"
            "Sell directly at local markets to cut out middlemen. "
            "Join a cooperative (UCA for coffee, district cooperatives for other crops). "
            "Add value — dry, roast, or mill your crops.\n\n"
            "Store in PICS bags and sell 2-3 months after harvest when supply drops.\n\n"
            "Visit your nearest market this week to compare prices."
        )

    # Water/irrigation
    if any(w in normalized for w in ["water", "irrigat", "drip", "sprinkle"]):
        return (
            "For irrigation in Uganda:\n\n"
            "Drip irrigation is most efficient — uses 60% less water than flood. "
            "Simple DIY: use plastic bottles with small holes buried near plant roots.\n\n"
            "Water early morning (6-8am) or evening (5-7pm). "
            "Mulch heavily to reduce evaporation.\n\n"
            "Rainwater harvesting: connect gutters to a tank. 1000L tank costs about UGX 800,000."
        )

    # Pest/insect/bug
    if any(w in normalized for w in ["pest", "insect", "bug", "worm", "aphid", "locust", "beetle"]):
        return (
            "For pest control in Uganda:\n\n"
            "Neem spray: crush 1kg neem leaves in 10L water, strain, spray on crops. "
            "Works against aphids, caterpillars, and beetles.\n\n"
            "Wood ash: sprinkle around plant bases for crawling insects. "
            "Copper fungicide (Blue Shield) for fungal diseases.\n\n"
            "Check your plants today for any signs of pest damage — look under leaves."
        )

    # Weed
    if any(w in normalized for w in ["weed", "grass", "herbicide"]):
        return (
            "Weed management in Uganda:\n\n"
            "Weed at 2-3 weeks and 6 weeks after planting. "
            "Hand-weeding is most common and cheapest. "
            "Mulching with grass or banana leaves suppresses weeds.\n\n"
            "For severe infestations, use recommended herbicides from NAADS. "
            "Always follow label rates — more is not better.\n\n"
            "Weed your garden this week before they compete with your crops."
        )

    # Greeting/who are you
    if any(w in normalized for w in ["who", "what are you", "your name", "about you", "help me"]):
        return (
            "I'm NOVA — your AI farming assistant built for Ugandan farmers. "
            "I can help with crops (coffee, maize, beans, bananas, cassava), "
            "livestock (chickens, goats, cattle), soil, weather, market prices, and pest control.\n\n"
            "Ask me anything — even in Luganda, Swahili, or broken English. I'll understand!"
        )

    # Thanks
    if any(w in normalized for w in ["thank", "thanks", "webale", "nice", "great", "good"]):
        return (
            "You're welcome! I'm here whenever you need farming advice. "
            "Feel free to ask about anything — crops, livestock, soil, or market prices."
        )

    # Default — try to be helpful with whatever they asked
    return (
        f"I'd be happy to help with that. Here's what I know:\n\n"
        f"Regarding: {original[:120]}\n\n"
        "I can help with: planting and growing crops (coffee, maize, beans, bananas, cassava), "
        "livestock care (chickens, goats, cattle), soil and fertilizer, pest control, "
        "weather and seasons, harvesting and storage, and market prices.\n\n"
        "Try asking something specific like 'How do I plant maize?' or "
        "'My coffee leaves have yellow spots' and I'll give you practical advice."
    )
