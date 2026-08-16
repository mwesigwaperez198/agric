"""Localized speech-to-speech pipeline.

- STT: OpenAI Whisper when WHISPER_API_KEY is set, else a deterministic mock.
- TTS: ElevenLabs when ELEVENLABS_API_KEY is set, else returns mock mode so the
  frontend can fall back to the browser's speech synthesis with a dialect voice.
"""

import io
import re
import wave

from api.app.config import settings
from api.app.mocks.translations import SUPPORTED_DIALECTS

VOICE_MAP = {
    "lg": "lu",  # Luganda
    "sw": "sw",  # Swahili
    "ach": "ach",  # Acholi
    "nyn": "nyn",  # Runyankore
}


def validate_audio(data: bytes) -> None:
    """Basic audio sanity check (WAV/MP4/WebM or non-empty blob)."""
    if len(data) < 32:
        raise ValueError("Audio upload is empty")
    if len(data) > settings.max_upload_bytes:
        raise ValueError("Audio exceeds maximum allowed size")
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        channels = struct_unpack(data)
        if channels == 0:
            raise ValueError("Audio has no channels")


def struct_unpack(data: bytes) -> int:
    try:
        return int.from_bytes(data[22:24], "little")
    except Exception:
        return 1


def whisper_transcribe(data: bytes) -> str:
    import httpx

    resp = httpx.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
        data={"model": "whisper-1", "language": "en"},
        files={"file": ("voice.webm", data, "audio/webm")},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()


def mock_transcribe(data: bytes) -> str:
    """Deterministic stand-in transcript for offline testing."""
    blob = data or b""
    probe = len(blob) % 3
    if probe == 0:
        return "What is the best time to spray for coffee leaf rust?"
    if probe == 1:
        return "How is the price of maize this week?"
    return "Tell me about moisture levels for coffee."


def transcribe(data: bytes) -> str:
    validate_audio(data)
    if settings.whisper_api_key:
        return whisper_transcribe(data)
    return mock_transcribe(data)


def synthesize(text: str, dialect: str = "en") -> dict:
    """Returns {audio_url, provider}. Provider 'mock' signals browser TTS fallback."""
    if settings.elevenlabs_api_key:
        url = _elevenlabs_url(text, dialect)
        return {"audio_url": url, "provider": "elevenlabs"}
    return {"audio_url": None, "provider": "mock"}


def _elevenlabs_url(text: str, dialect: str) -> str:
    import urllib.parse

    voice = VOICE_MAP.get(dialect, "en")
    return f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?text={urllib.parse.quote(text)}"
