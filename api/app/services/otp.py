"""OTP 2FA service — generate, send, and verify one-time codes.

Supports SMS (Africa's Talking) and Email (Resend) delivery.
"""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from api.app.config import settings
from api.app.models.otp import OtpCode

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com"
AT_API = "https://api.africastalking.com/version1/messaging"


# ---------------------------------------------------------------------------
# Code generation + hashing
# ---------------------------------------------------------------------------

def generate_otp_code() -> str:
    """6-digit numeric OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Delivery helpers
# ---------------------------------------------------------------------------

def send_sms_otp(phone: str, code: str) -> bool:
    """Send OTP via Africa's Talking SMS."""
    api_key = settings.africastalking_api_key
    username = settings.africastalking_username
    if not api_key:
        logger.warning("Africa's Talking API key not configured — skipping SMS")
        return False

    headers = {
        "apiKey": api_key,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "username": username,
        "to": phone,
        "message": f"Your Farm-to-Fork verification code is: {code}. Valid for {settings.otp_expire_minutes} minutes.",
    }
    try:
        resp = httpx.post(AT_API, headers=headers, data=payload, timeout=10)
        resp.raise_for_status()
        logger.info("SMS OTP sent to %s", phone)
        return True
    except Exception:
        logger.exception("Failed to send SMS OTP to %s", phone)
        return False


def send_email_otp(email: str, code: str) -> bool:
    """Send OTP via Resend email."""
    api_key = settings.resend_api_key
    if not api_key:
        logger.warning("Resend API key not configured — skipping email")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": "Farm-to-Fork <onboarding@resend.dev>",
        "to": [email],
        "subject": "Your verification code",
        "html": (
            f"<p>Your Farm-to-Fork verification code is:</p>"
            f"<h2 style='letter-spacing:0.3em;font-size:2rem'>{code}</h2>"
            f"<p>Valid for {settings.otp_expire_minutes} minutes. Do not share this code.</p>"
        ),
    }
    try:
        resp = httpx.post(f"{RESEND_API}/emails", headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Email OTP sent to %s", email)
        return True
    except Exception:
        logger.exception("Failed to send email OTP to %s", email)
        return False


# ---------------------------------------------------------------------------
# OTP store + verify
# ---------------------------------------------------------------------------

def create_otp(db: Session, user_id: int, delivery: str, target: str) -> OtpCode:
    """Generate, hash, and persist an OTP code. Returns the OtpCode row."""
    code = generate_otp_code()
    otp = OtpCode(
        user_id=user_id,
        code_hash=_hash_code(code),
        delivery=delivery,
        target=target,
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.otp_expire_minutes),
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    otp._plain_code = code  # type: ignore[attr-defined]
    return otp


def verify_otp(db: Session, user_id: int, code: str) -> bool:
    """Check the latest unused OTP for this user. Returns True on success."""
    now = datetime.now(UTC)
    otp = (
        db.query(OtpCode)
        .filter(
            OtpCode.user_id == user_id,
            OtpCode.used == False,  # noqa: E712
            OtpCode.expires_at > now,
        )
        .order_by(OtpCode.id.desc())
        .first()
    )
    if not otp:
        return False
    if otp.attempts >= settings.otp_max_attempts:
        return False
    otp.attempts += 1
    if not secrets.compare_digest(otp.code_hash, _hash_code(code)):
        db.commit()
        return False
    otp.used = True
    db.commit()
    return True


def mask_target(value: str, delivery: str) -> str:
    """Mask phone or email for display. +256701234567 → +256****4567"""
    if delivery == "sms":
        digits = "".join(c for c in value if c.isdigit())
        if len(digits) >= 4:
            return value[: -len(digits) + len(digits) // 2] + "****" + digits[len(digits) // 2 :]
        return value
    parts = value.split("@")
    if len(parts) == 2:
        name = parts[0]
        masked_name = name[0] + "***" if name else "***"
        return f"{masked_name}@{parts[1]}"
    return value
