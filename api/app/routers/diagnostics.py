from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.app.deps import CurrentUser, DbSession
from api.app.models import Diagnostic
from api.app.schemas.diagnostics import DiagnosticOut, VoiceQueryOut, VoiceQueryRequest
from api.app.services import diagnostics as diag
from api.app.services.translation import translate

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
    """Legacy voice query endpoint — routes to the full AI chat pipeline."""
    from api.app.routers.voice import voice_chat
    from fastapi import BackgroundTasks

    return voice_chat(body, user, db, BackgroundTasks())
