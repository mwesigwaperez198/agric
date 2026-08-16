"""Vision-capable plant diagnostics.

Pluggable provider chain:
1. mock       — deterministic rule-based CNN stand-in (no API key, works offline)
2. openai     — GPT-4o multimodal vision (WHISPER/vision key)
3. anthropic  — Claude vision

Provider selection is governed by `VISION_PROVIDER` + the relevant API key.
Input images are validated before reaching any model.
"""

import hashlib
import io
import json
import os
import struct
from typing import BinaryIO

from api.app.config import settings
from api.app.services.guardrails import DEFAULT_RESPONSE, is_agri_query

DISORDER_KNOWLEDGE = {
    "coffee": {
        "coffee_leaf_rust": "Hemileia vastatrix. Remove infected leaves, improve airflow, apply copper-based fungicide and shade management.",
        "coffee_berry_disease": "Colletotrichum kahawae. Harvest early, prune, and apply approved fungicide during wet season.",
        "leaf_miner": "Leucoptera coffeella. Introduce natural predators, remove infested leaves, monitor traps.",
        "healthy": "Plant appears healthy. Maintain balanced nutrition and regular scouting.",
    },
    "livestock": {
        "foot_and_mouth": "Notify the district veterinary officer. Isolate affected animals and restrict movement.",
        "nagana": "Trypanosomiasis spread by tsetse. Vet-confirmed treatment and vector control advised.",
        "healthy": "No clinical signs detected. Keep vaccination schedule current.",
    },
    "grains": {
        "fall_armyworm": "Scout early, apply recommended biopesticide or insecticide rotation, inter-crop to break the cycle.",
        "smut": "Use treated seed, practice crop rotation and remove infected plants.",
        "healthy": "No visible infestation. Monitor for pest pressure.",
    },
    "produce": {
        "late_blight": "Remove affected foliage, improve drainage, apply copper-based fungicide preventively.",
        "bacterial_wilt": "Rotate crops, remove infected plants, avoid overwatering.",
        "healthy": "No symptoms observed. Continue integrated pest management.",
    },
}


class ImageValidationError(ValueError):
    pass


def validate_image(data: bytes) -> str:
    """Rejects oversized or non-image uploads before ML processing."""
    if len(data) > settings.max_upload_bytes:
        raise ImageValidationError("Image exceeds maximum allowed size")
    if len(data) < 16:
        raise ImageValidationError("File is too small to be an image")
    header = data[:12]
    if not (
        header.startswith(b"\xff\xd8\xff")  # JPEG
        or header.startswith(b"\x89PNG\r\n\x1a\n")  # PNG
        or header.startswith(b"RIFF") and data[8:12] == b"WEBP"  # WEBP
        or header.startswith(b"GIF8")  # GIF
    ):
        raise ImageValidationError("Unsupported or invalid image format")
    return "image"


def _seeded_choices(data: bytes, options: list[str], salt: str) -> str:
    digest = hashlib.sha256(salt.encode() + data).digest()
    return options[int.from_bytes(digest[:4], "big") % len(options)]


def mock_diagnose(data: bytes, crop_type: str) -> dict:
    """Deterministic rule-based stand-in for a vision CNN."""
    disorders = list(DISORDER_KNOWLEDGE.get(crop_type, DISORDER_KNOWLEDGE["coffee"]).keys())
    label = _seeded_choices(data, disorders, f"{crop_type}:disorder")
    confidence = round(0.62 + int.from_bytes(hashlib.sha256(data).digest()[:2], "big") / 65535 * 0.30, 2)
    advice = DISORDER_KNOWLEDGE.get(crop_type, DISORDER_KNOWLEDGE["coffee"]).get(label, "")
    healthy = label == "healthy"
    return {
        "label": label,
        "healthy": healthy,
        "confidence": confidence,
        "advice": advice,
    }


def openai_diagnose(data: bytes, crop_type: str, note: str | None = None) -> dict:
    import base64

    import httpx

    b64 = base64.b64encode(data).decode("ascii")
    prompt = (
        f"Identify any disease, pest, or infestation in this {crop_type} photo. "
        "Return strict JSON with keys label, healthy, confidence (0-1), advice."
    )
    if note:
        prompt += f" Farmer note: {note}"
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
        json={
            "model": "gpt-4o",
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


def anthropic_diagnose(data: bytes, crop_type: str, note: str | None = None) -> dict:
    import base64

    import httpx

    b64 = base64.b64encode(data).decode("ascii")
    prompt = (
        f"Identify any disease, pest, or infestation in this {crop_type} photo. "
        'Respond with strict JSON: {"label": "...", "healthy": bool, "confidence": 0-1, "advice": "..."}.'
    )
    if note:
        prompt += f" Farmer note: {note}"
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.whisper_api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": "claude-3-5-sonnet-latest",
            "max_tokens": 500,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    ],
                }
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"]
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def diagnose(data: bytes, crop_type: str, note: str | None = None) -> tuple[dict, str]:
    """Runs the configured provider. Returns (prediction, model_name)."""
    validate_image(data)
    provider = settings.vision_provider.lower()

    if provider == "openai" and settings.whisper_api_key:
        return openai_diagnose(data, crop_type, note), "gpt-4o-vision"
    if provider == "anthropic" and settings.whisper_api_key:
        return anthropic_diagnose(data, crop_type, note), "claude-3-5-sonnet"
    return mock_diagnose(data, crop_type), "mock-cnn"


def is_agri_question(text: str) -> tuple[bool, str]:
    passed, response = _domain_check(text)
    return passed, response


def _domain_check(text: str) -> tuple[bool, str]:
    """Alias for guardrails with a lighter import footprint for the router."""
    if not is_agri_query(text):
        return False, DEFAULT_RESPONSE
    return True, ""
