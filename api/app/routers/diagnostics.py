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

    answer = _answer_question(body.text, body.crop_type)
    translated = translate(answer, body.locale)
    tts = synthesize(translated, body.locale)
    return VoiceQueryOut(
        answer=answer,
        translated=translated if body.locale != "en" else None,
        tts_audio_url=tts["audio_url"],
        guardrail=True,
        dialect=body.locale,
    )


def _answer_question(text: str, crop_type: str) -> str:
    lowered = text.lower()
    if "rust" in lowered or "leaf" in lowered and "coffee" in lowered:
        return (
            "Coffee leaf rust spreads fastest in wet, warm conditions. Scout twice weekly, "
            "prune for airflow, and apply a copper-based fungicide during the rainy season."
        )
    if "price" in lowered or "market" in lowered:
        return "Check the Insights tab for live price trends and a 7-day forecast for your crop."
    if "moisture" in lowered or "biosensor" in lowered:
        return "Keep coffee moisture near 11% during storage. Readings above 12.5% increase ochratoxin risk."
    return (
        f"For {crop_type}, scout regularly, maintain soil fertility, and keep your biosensor "
        "batch records up to date to avoid contamination flags."
    )
