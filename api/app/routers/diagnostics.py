from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.app.deps import CurrentUser, DbSession
from api.app.models import Diagnostic
from api.app.schemas.diagnostics import DiagnosticOut, VoiceQueryOut, VoiceQueryRequest
from api.app.services import diagnostics as diag
from api.app.services.guardrails import guard_query
from api.app.services.translation import translate
from api.app.services.voice import synthesize

router = APIRouter(tags=["diagnostics"])


def _out(d: Diagnostic) -> DiagnosticOut:
    return DiagnosticOut.model_validate(d)


@router.post("/diagnostics/analyze", response_model=DiagnosticOut)
async def analyze_image(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    crop_type: str = Form(default="coffee"),
    note: str | None = Form(default=None),
    locale: str = Form(default="en"),
):
    """Multimodal plant diagnostics: upload a leaf/animal photo for disease detection."""
    data = await file.read()
    try:
        prediction, model = diag.diagnose(data, crop_type, note)
    except diag.ImageValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    advice = prediction.get("advice", "")
    diagnostic = Diagnostic(
        user_id=user.id,
        crop_type=crop_type,
        image_url=None,
        prompt=note,
        prediction=prediction,
        confidence=prediction.get("confidence", 0.0),
        model=model,
        guardrail_passed=True,
        advice=translate(advice, locale) if advice else None,
    )
    db.add(diagnostic)
    db.commit()
    db.refresh(diagnostic)
    return _out(diagnostic)


@router.get("/diagnostics", response_model=list[DiagnosticOut])
def list_diagnostics(user: CurrentUser, db: DbSession, limit: int = 20):
    rows = (
        db.query(Diagnostic)
        .filter(Diagnostic.user_id == user.id)
        .order_by(Diagnostic.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_out(d) for d in rows]


@router.post("/voice/query", response_model=VoiceQueryOut)
def voice_query(body: VoiceQueryRequest, user: CurrentUser, db: DbSession):
    """Localized speech-to-speech agent: text in, guarded dialect answer + TTS out."""
    passed, blocked_response = guard_query(body.text)
    if not passed:
        return VoiceQueryOut(answer=blocked_response, guardrail=False, dialect=body.locale)

    context = body.context or []
    answer = _answer_question(body.text, body.crop_type, context)
    translated = translate(answer, body.locale)
    tts = synthesize(translated, body.locale)
    return VoiceQueryOut(
        answer=answer,
        translated=translated if body.locale != "en" else None,
        tts_audio_url=tts["audio_url"],
        guardrail=True,
        dialect=body.locale,
    )


def _answer_question(text: str, crop_type: str, context: list[dict] | None = None) -> str:
    """Use GPT-4o for detailed, contextual agricultural responses."""
    from api.app.config import settings

    if settings.whisper_api_key:
        return _openai_answer(text, crop_type, context)
    return _fallback_answer(text, crop_type)


def _openai_answer(text: str, crop_type: str, context: list[dict] | None = None) -> str:
    import json

    import httpx

    messages = [
        {
            "role": "system",
            "content": (
                "You are NOVA, an expert agricultural AI assistant for Ugandan farmers. "
                "You provide detailed, practical, evidence-based answers about farming in Uganda. "
                "Key principles:\n"
                "- Be SPECIFIC to Uganda: mention local varieties, institutions (NARO, UCDA, NaCORRI), "
                "and products available in Ugandan markets\n"
                "- Be DETAILED: explain the 'why' behind every recommendation\n"
                "- Be PRACTICAL: include specific dosages, timing, and costs in UGX where relevant\n"
                "- Be CONTEXTUAL: reference the conversation history to build on previous answers\n"
                "- Cite research: reference NARO bulletins, UCDA guidelines, or peer-reviewed papers\n"
                "- Cover: coffee (Arabica/Robusta), maize, beans, banana, vanilla, livestock, poultry\n"
                "- Ugandan context: bimodal rainfall, altitude zones (1200-2000m for Arabica), "
                "smallholder farms (0.5-2 acres), cooperatives, NAADS extension system\n"
                "\n"
                "Format: Provide a well-structured response with clear sections. "
                "Use bullet points for recommendations. Include a 'Quick Action' summary at the end."
            ),
        }
    ]

    if context:
        for exchange in context[-6:]:
            messages.append({"role": "user", "content": exchange.get("user", "")})
            messages.append({"role": "assistant", "content": exchange.get("assistant", "")})

    messages.append({
        "role": "user",
        "content": f"[Crop context: {crop_type}] {text}",
    })

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
        json={
            "model": "gpt-4o",
            "max_tokens": 1500,
            "messages": messages,
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _fallback_answer(text: str, crop_type: str) -> str:
    """Offline fallback with keyword matching."""
    lowered = text.lower()
    if "rust" in lowered or ("leaf" in lowered and "coffee" in lowered):
        return (
            "Coffee leaf rust (Hemileia vastatrix) is the most devastating coffee disease in Uganda, "
            "especially in Bugisu and Rwenzori regions.\n\n"
            "ROOT CAUSE: The fungus thrives in warm, humid conditions (22-28°C, >80% humidity). "
            "Spores spread through wind and rain splash during the rainy seasons (March-May, September-November).\n\n"
            "IMMEDIATE ACTIONS:\n"
            "1. Apply copper-based fungicide — Blue Shield or Kocide 2000 at 3g/L water. "
            "Spray within 48 hours of first symptoms.\n"
            "2. Remove and burn heavily infected leaves to reduce spore load.\n"
            "3. Prune lower branches to improve airflow — maintain 50cm clearance from ground.\n\n"
            "LONG-TERM MANAGEMENT:\n"
            "- Plant resistant varieties: Ruiru 11, NARO 1 (for Arabica zones)\n"
            "- Maintain shade canopy at 30-40% — use Erythrina or Grevillea shade trees\n"
            "- Apply nitrogen fertilizer split: 50g N/tree during first rains\n"
            "- Scout twice weekly during wet months\n\n"
            "QUICK ACTION: Spray Blue Shield today, prune infected branches this week, "
            "and schedule regular scouting.\n\n"
            "Reference: NARO Coffee Research Station, Mukono."
        )
    if "price" in lowered or "market" in lowered:
        return (
            "UGANDA COFFEE MARKET UPDATE:\n\n"
            "The Uganda Coffee Development Authority (UCDA) publishes monthly price indicators. "
            "Key factors affecting prices:\n\n"
            "- Global arabica futures (ICE/ICE Futures) — check Bloomberg COMmodity\n"
            "- Local auction prices at Uganda Coffee Trade auction (UCX)\n"
            "- Quality premiums: Grade AA (screen 17+) fetches 15-20% premium\n"
            "- Fair Trade certified: additional $0.20/lb premium\n\n"
            "RECOMMENDATIONS:\n"
            "1. Join a cooperative for better bargaining power (e.g., Bukonzo Joint, Rwenzori Farmers)\n"
            "2. Invest in quality: proper pulping, fermentation (12-18hrs), and drying to 11% moisture\n"
            "3. Get certification: Fair Trade, Organic, or Rainforest Alliance\n"
            "4. Use UCDA price alerts: register at ucda.co.ug\n\n"
            "Current indicative prices (check UCDA for latest):\n"
            "- Robusta: UGX 8,000-12,000/kg (clean)\n"
            "- Arabica: UGX 15,000-25,000/kg (clean)\n\n"
            "Reference: UCDA Monthly Statistical Bulletin."
        )
    if "moisture" in lowered or "biosensor" in lowered:
        return (
            "COFFEE MOISTURE MANAGEMENT:\n\n"
            "Optimal moisture levels for Ugandan coffee:\n"
            "- Cherry at harvest: 65-75% moisture\n"
            "- Parchment after pulping: 45-50%\n"
            "- Dried coffee (ready for sale): 10-12% (UCDA standard is ≤12.5%)\n"
            "- Storage: maintain 10-11% — above 12.5% risks ochratoxin A contamination\n\n"
            "BIOSENSOR MONITORING:\n"
            "1. Place sensors at drying beds — check every 2 hours during drying\n"
            "2. Alert threshold: >12% moisture triggers drying acceleration\n"
            "3. Use raised drying beds (African beds) for even airflow\n"
            "4. Turn cherries every 2 hours during sun drying\n"
            "5. Target drying time: 5-7 days for washed, 14-21 days for natural\n\n"
            "COMMON MISTAKES:\n"
            "- Over-fermentation (>24hrs) increases moisture retention\n"
            "- Drying on ground (not beds) causes uneven moisture\n"
            "- Storing in jute bags without lining in humid areas\n\n"
            "QUICK ACTION: Invest in a moisture meter (UGX 50,000-150,000), "
            "check every batch before sale.\n\n"
            "Reference: NARO Post-Harvest Guidelines, UCDA Quality Standards."
        )
    if "soil" in lowered or "fertiliz" in lowered:
        return (
            "SOIL MANAGEMENT FOR UGANDAN COFFEE:\n\n"
            "Soil testing is essential — contact NAADS for free testing in your district.\n\n"
            "KEY SOIL TYPES IN COFFEE ZONES:\n"
            "- Ferralsols (Bugisu, Rwenzori): acidic (pH 4.5-5.5), low P, high Al\n"
            "- Nitisols (Western highlands): deeper, more fertile, pH 5.5-6.5\n"
            "- Volcanic soils (Mt. Elgon): rich but prone to erosion\n\n"
            "FERTILIZER RECOMMENDATIONS (per tree/year):\n"
            "1. Nitrogen: 100-150g urea (46-0-0) split into 2 applications\n"
            "2. Phosphorus: 50-100g TSP (0-46-0) at planting/drainage\n"
            "3. Potassium: 50-100g MOP (0-0-60) during fruit development\n"
            "4. Compost: 5-10kg per tree annually — best ROI for smallholders\n\n"
            "ORGANIC OPTIONS (available in Uganda):\n"
            "- Tithonia diversifolia (sunflower) — nitrogen-rich mulch\n"
            "- Calliandra calothyrsus — nitrogen-fixing shade tree\n"
            "- Coffee husk compost — 3-month preparation\n\n"
            "TIMING: Apply fertilizers at start of rains (March, September)\n\n"
            "Reference: NARO Soil Fertility Guidelines for Coffee."
        )
    return (
        f"As your agricultural AI assistant, I can help with {crop_type} farming in Uganda. "
        "Please ask about:\n"
        "- Disease identification and treatment\n"
        "- Soil management and fertilization\n"
        "- Market prices and selling strategies\n"
        "- Post-harvest handling and quality\n"
        "- Water management and irrigation\n"
        "- Pest control (organic and chemical)\n"
        "- Farm planning and record keeping\n\n"
        "I provide evidence-based advice referencing NARO, UCDA, and local research."
    )
