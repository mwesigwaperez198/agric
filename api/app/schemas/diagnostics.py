from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CROP_TYPES = ("coffee", "livestock", "grains", "produce")


class DiagnosticRequest(BaseModel):
    crop_type: str = Field(default="coffee", pattern="^(" + "|".join(CROP_TYPES) + ")$")
    note: str | None = Field(default=None, max_length=2000)
    locale: str = "en"


class DiagnosticOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    crop_type: str
    image_url: str | None
    prediction: dict[str, Any]
    confidence: float
    model: str
    guardrail_passed: bool
    advice: str | None
    created_at: datetime


class VoiceQueryRequest(BaseModel):
    """Transcribed text from the user's spoken question."""

    text: str = Field(min_length=1, max_length=2000)
    locale: str = "en"
    crop_type: str = "coffee"
    context: list[dict] | None = Field(default=None, description="Conversation history [{user, assistant}]")
    detected_language: str | None = Field(default=None, description="Language detected by Whisper")
    english_text: str | None = Field(default=None, description="English translation of the user text")


class VoiceQueryOut(BaseModel):
    answer: str
    translated: str | None = None
    tts_audio_url: str | None = None
    guardrail: bool = True
    dialect: str
