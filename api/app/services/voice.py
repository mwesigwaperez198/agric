"""Localized speech-to-speech pipeline with multi-language support.

- STT: OpenAI Whisper with auto-language detection (no forced English).
- Language detection: GPT-4o identifies the spoken language.
- Translation: GPT-4o translates between user's language and English.
- TTS: ElevenLabs when ELEVENLABS_API_KEY is set, else browser fallback.
"""

import json
import re
import urllib.parse

from api.app.config import settings

WHISPER_LANG_MAP = {
    "en": "en",
    "lg": "lg",   # Luganda
    "sw": "sw",   # Swahili
    "ach": "ach",  # Acholi
    "nyn": "nyn",  # Runyankore
    "rn": "rn",   # Kirundi
    "sa": "sa",   # Soga
    "xog": "xog",  # Soga
}

ELEVENLABS_VOICE_MAP = {
    "en": "21m00Tcm4TlvDq8ikWAM",  # Rachel
    "lg": "21m00Tcm4TlvDq8ikWAM",
    "sw": "21m00Tcm4TlvDq8ikWAM",
}


def validate_audio(data: bytes) -> None:
    if len(data) < 32:
        raise ValueError("Audio upload is empty")
    if len(data) > settings.max_upload_bytes:
        raise ValueError("Audio exceeds maximum allowed size")
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        channels = int.from_bytes(data[22:24], "little") if len(data) > 23 else 1
        if channels == 0:
            raise ValueError("Audio has no channels")


def whisper_transcribe(data: bytes) -> dict:
    """Transcribe with auto language detection. Returns {text, language}."""
    import httpx

    resp = httpx.post(
        "https://api.openai.com/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
        data={"model": "whisper-1", "response_format": "verbose_json"},
        files={"file": ("voice.webm", data, "audio/webm")},
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()
    return {
        "text": result.get("text", "").strip(),
        "language": result.get("language", "en"),
    }


def detect_and_translate(text: str, detected_lang: str) -> dict:
    """Use GPT-4o to detect intent language and translate to English if needed.
    Returns {english_text, original_lang, needs_translation}."""
    import httpx

    if not settings.whisper_api_key:
        return {"english_text": text, "original_lang": detected_lang, "needs_translation": False}

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
        json={
            "model": "gpt-4o-mini",
            "max_tokens": 200,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a language detection and translation engine. "
                        "Analyze the user's text and return JSON with:\n"
                        '- "language": ISO 639-1 code of the user\'s language\n'
                        '- "english": the text translated to English (if already English, return as-is)\n'
                        '- "is_english": true/false\n\n'
                        "Supported languages: English, Luganda, Swahili, Acholi, Runyankore, Soga, Kirundi. "
                        "These are East African agricultural contexts."
                    ),
                },
                {"role": "user", "content": text},
            ],
        },
        timeout=15,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        data = json.loads(content[start:end])
        return {
            "english_text": data.get("english", text),
            "original_lang": data.get("language", detected_lang),
            "needs_translation": not data.get("is_english", detected_lang == "en"),
        }
    return {"english_text": text, "original_lang": detected_lang, "needs_translation": False}


def translate_response(text: str, target_lang: str) -> str:
    """Translate English response back to user's language using GPT-4o."""
    import httpx

    if target_lang == "en" or not settings.whisper_api_key:
        return text

    lang_names = {"lg": "Luganda", "sw": "Swahili", "ach": "Acholi", "nyn": "Runyankore", "rn": "Kirundi", "sa": "Soga"}
    lang_name = lang_names.get(target_lang, target_lang)

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
        json={
            "model": "gpt-4o-mini",
            "max_tokens": 1500,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"You are a professional agricultural translator for East Africa. "
                        f"Translate the following English text into {lang_name}. "
                        "Keep technical/agricultural terms accurate. "
                        "Use natural, conversational {lang_name} that a farmer would understand. "
                        "Do NOT add explanations — just return the translation."
                    ),
                },
                {"role": "user", "content": text},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def mock_transcribe(data: bytes) -> dict:
    blob = data or b""
    probe = len(blob) % 3
    if probe == 0:
        return {"text": "What is the best time to spray for coffee leaf rust?", "language": "en"}
    if probe == 1:
        return {"text": "How is the price of maize this week?", "language": "en"}
    return {"text": "Tell me about moisture levels for coffee.", "language": "en"}


def transcribe(data: bytes) -> dict:
    validate_audio(data)
    if settings.whisper_api_key:
        return whisper_transcribe(data)
    return mock_transcribe(data)


def synthesize(text: str, dialect: str = "en") -> dict:
    if settings.elevenlabs_api_key:
        url = _elevenlabs_url(text, dialect)
        return {"audio_url": url, "provider": "elevenlabs"}
    return {"audio_url": None, "provider": "mock"}


def _elevenlabs_url(text: str, dialect: str) -> str:
    voice = ELEVENLABS_VOICE_MAP.get(dialect, "21m00Tcm4TlvDq8ikWAM")
    return f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?text={urllib.parse.quote(text)}"
