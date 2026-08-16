"""Mock payment provider adapter (Mobile Money / Flutterwave style).

Phase 1 uses an isolated webhook that logs notifications to a JSONL file so
commission logic can be validated without live payment infrastructure.
"""

import json
import secrets
import uuid
from datetime import UTC, datetime
from pathlib import Path

from api.app.config import settings

PAYMENT_STATUSES = ("pending", "success", "failed")


def initiate_payment(phone: str, amount: float, reference: str) -> dict:
    """Pretends to request a Mobile Money charge; returns a provider payload."""
    return {
        "provider": "mobile_money",
        "status": "pending",
        "amount": round(amount, 2),
        "currency": settings.currency,
        "reference": reference,
        "provider_reference": f"MM-{uuid.uuid4().hex[:12].upper()}",
        "phone": phone,
        "created_at": datetime.now(UTC).isoformat(),
    }


def confirm_payment(provider_reference: str) -> dict:
    """Simulates the provider's async callback result."""
    return {
        "provider": "mobile_money",
        "status": "success",
        "provider_reference": provider_reference,
        "confirmed_at": datetime.now(UTC).isoformat(),
    }


def log_webhook(provider: str, event: str, payload: dict) -> str:
    """Phase 1: persist incoming webhook notifications to a JSONL log file."""
    path = Path(settings.webhook_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "id": secrets.token_hex(8),
        "provider": provider,
        "event": event,
        "payload": payload,
        "received_at": datetime.now(UTC).isoformat(),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record["id"]
