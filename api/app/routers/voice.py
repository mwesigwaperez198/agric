from fastapi import APIRouter, File, HTTPException, UploadFile

from api.app.deps import CurrentUser
from api.app.services.voice import transcribe

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/transcribe")
async def transcribe_audio(user: CurrentUser, file: UploadFile = File(...)):
    """Accepts an audio recording (webm/wav) and returns the transcribed text."""
    data = await file.read()
    try:
        return {"text": transcribe(data), "provider": "whisper" if data else "mock"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
