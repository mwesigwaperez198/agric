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
import logging
import os
import struct
from typing import BinaryIO

logger = logging.getLogger(__name__)

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
        "plant_identification": f"{crop_type} sample",
        "condition_summary": advice,
        "rootCauseAnalysis": "Connect to a vision model (set VISION_PROVIDER=openai) for detailed root cause analysis.",
        "severity": "medium" if not healthy else "low",
        "affectedParts": ["leaves"],
        "spreadRisk": "Moderate — consult an agronomist for field-level assessment.",
        "immediateActions": [advice] if advice else ["Upload a clear photo for AI-powered analysis."],
        "longTermManagement": ["Regular scouting and soil testing recommended."],
        "localProducts": ["Contact your nearest NAADS extension worker for product recommendations."],
        "references": ["NARO Uganda — https://www.naro.go.ug"],
    }


def openai_diagnose(data: bytes, crop_type: str, note: str | None = None) -> dict:
    import base64

    import httpx

    b64 = base64.b64encode(data).decode("ascii")
    prompt = f"""You are an expert agricultural diagnostics AI for Ugandan farmers. Analyze this {crop_type} photo.

Provide a COMPREHENSIVE diagnosis. Return strict JSON with these keys:
{{
  "label": "disease_or_condition_name",
  "healthy": true/false,
  "confidence": 0.0-1.0,
  "plant_identification": "species and variety if identifiable",
  "condition_summary": "2-3 sentence overview of what you observe",
  "root_cause_analysis": "detailed explanation of why this condition occurs — environmental factors, soil conditions, pathogen biology, management practices",
  "severity": "low/medium/high/critical",
  "affected_parts": ["list of plant parts affected"],
  "spread_risk": "how likely it is to spread to other plants and why",
  "immediate_actions": [
    "Step 1: specific action with product names and dosages where applicable",
    "Step 2: ...",
    "Step 3: ..."
  ],
  "long_term_management": [
    "Seasonal practice recommendation 1",
    "Seasonal practice recommendation 2"
  ],
  "local_products": ["specific fungicide/insecticide products available in Uganda with approximate costs"],
  "references": ["research institution or publication reference"],
  "advice": "concise 1-2 sentence summary for quick action"
}}

Context about Ugandan agriculture:
- Common coffee varieties: Bugisu Arabica, Robusta (Nganda, Erecta)
- Key institutions: NARO (National Agricultural Research Organisation), UCDA (Uganda Coffee Development Authority), NaCORRI
- Local fungicides: Copper-based (Blue Shield, Kocide), Ridomil Gold, Topas
- Biopesticides available: Beauveria bassiana, Trichoderma harzianum
- Climate zones: Lake Victoria basin, Western highlands, Mt. Elgon region
- Soil types: Ferralsols (coffee zones), Nitisols (highlands)

{f"Farmer's observation: {note}" if note else ""}
Analyze the image carefully. If healthy, still provide monitoring advice."""

    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
        json={
            "model": "gpt-4o",
            "response_format": {"type": "json_object"},
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert agricultural diagnostics system for Ugandan farmers. "
                        "You provide detailed, evidence-based analysis with specific product recommendations "
                        "available in Uganda. Always cite NARO or UCDA research where applicable. "
                        "Be thorough but practical — farmers need actionable steps they can take today."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                },
            ],
        },
        timeout=60,
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


def gemini_diagnose(data: bytes, crop_type: str, note: str | None = None) -> dict:
    import base64

    import httpx

    b64 = base64.b64encode(data).decode("ascii")
    prompt = f"""You are an expert agricultural diagnostics AI for Ugandan farmers. Analyze this {crop_type} photo.

Provide a COMPREHENSIVE diagnosis. Return strict JSON with these keys:
{{
  "label": "disease_or_condition_name",
  "healthy": true/false,
  "confidence": 0.0-1.0,
  "plant_identification": "species and variety if identifiable",
  "condition_summary": "2-3 sentence overview of what you observe",
  "root_cause_analysis": "detailed explanation of why this condition occurs",
  "severity": "low/medium/high/critical",
  "affected_parts": ["list of plant parts affected"],
  "spread_risk": "how likely it is to spread to other plants",
  "immediate_actions": [
    "Step 1: specific action with product names and dosages",
    "Step 2: ..."
  ],
  "long_term_management": ["Seasonal practice 1", "Seasonal practice 2"],
  "local_products": ["products available in Uganda with costs"],
  "references": ["research institution reference"],
  "advice": "concise 1-2 sentence summary for quick action"
}}

Context: Ugandan agriculture — NARO, UCDA, copper fungicides, bimodal rainfall.
{f"Farmer observation: {note}" if note else ""}
Analyze carefully. If healthy, still provide monitoring advice."""

    resp = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
        json={
            "model": "gemini-3.5-flash",
            "input": [
                {"type": "text", "text": prompt},
                {"type": "image", "data": b64, "mime_type": "image/jpeg"},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    steps = data.get("steps", [])
    for step in steps:
        for content in step.get("content", []):
            if content.get("type") == "text" and content.get("text"):
                text = content["text"]
                start, end = text.find("{"), text.rfind("}")
                if start != -1 and end != -1:
                    return json.loads(text[start:end + 1])
    raise ValueError("Gemini vision returned no text")


def diagnose(data: bytes, crop_type: str, note: str | None = None) -> tuple[dict, str]:
    """Runs the configured provider. Returns (prediction, model_name)."""
    validate_image(data)
    provider = settings.vision_provider.lower()

    if provider in ("gemini", "auto") and settings.gemini_api_key:
        try:
            return gemini_diagnose(data, crop_type, note), "gemini-3.5-flash"
        except Exception as e:
            logger.error("Gemini vision failed: %s — falling back", e)
    if provider in ("openai", "auto") and settings.whisper_api_key:
        try:
            return openai_diagnose(data, crop_type, note), "gpt-4o-vision"
        except Exception as e:
            logger.error("OpenAI vision failed: %s — falling back", e)
    if provider == "anthropic" and settings.whisper_api_key:
        try:
            return anthropic_diagnose(data, crop_type, note), "claude-3-5-sonnet"
        except Exception as e:
            logger.error("Anthropic vision failed: %s — falling back", e)

    return mock_diagnose(data, crop_type), "mock-cnn"


def is_agri_question(text: str) -> tuple[bool, str]:
    passed, response = _domain_check(text)
    return passed, response


def _domain_check(text: str) -> tuple[bool, str]:
    """Alias for guardrails with a lighter import footprint for the router."""
    if not is_agri_query(text):
        return False, DEFAULT_RESPONSE
    return True, ""
