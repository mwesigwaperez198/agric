import base64
import binascii
import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
import pyotp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from api.app.config import settings

# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT access / refresh tokens
# ---------------------------------------------------------------------------


def _create_token(subject: str, token_type: str, expires_delta: timedelta, claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": secrets.token_hex(12),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        {"role": role},
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, "refresh", timedelta(days=settings.refresh_token_expire_days))


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload


# ---------------------------------------------------------------------------
# Time-based one-time passwords (2FA)
# ---------------------------------------------------------------------------


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.totp_issuer)


def verify_totp(secret: str, code: str) -> bool:
    if not code or not secret:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ---------------------------------------------------------------------------
# AES-256-GCM field encryption (secrets at rest)
# ---------------------------------------------------------------------------


def _field_key() -> bytes:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return digest[:32]


def encrypt_field(plain: str) -> str:
    if not plain:
        return plain
    key = _field_key()
    iv = secrets.token_bytes(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(iv)).encryptor()
    ciphertext = encryptor.update(plain.encode("utf-8")) + encryptor.finalize()
    payload = iv + ciphertext + encryptor.tag
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt_field(token: str) -> str:
    if not token:
        return token
    try:
        payload = base64.urlsafe_b64decode(token.encode("ascii"))
    except (binascii.Error, ValueError):
        return token
    if len(payload) < 28:
        return token
    iv, ciphertext, tag = payload[:12], payload[12:-16], payload[-16:]
    key = _field_key()
    try:
        decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode("utf-8")
    except Exception:
        return token


# ---------------------------------------------------------------------------
# Ledger integrity hashing (SHA-256 chained)
# ---------------------------------------------------------------------------


def ledger_hash(prev_hash: str, payload_json: str) -> str:
    raw = f"{prev_hash}|{payload_json}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# ---------------------------------------------------------------------------
# Simple in-memory rate limiter (per route + identity)
# ---------------------------------------------------------------------------

_requests: dict[str, list[float]] = {}


def rate_limit(identity: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
    """Returns (allowed, retry_after_seconds)."""
    now = time.monotonic()
    bucket = _requests.setdefault(identity, [])
    cutoff = now - window_seconds
    bucket[:] = [ts for ts in bucket if ts > cutoff]
    if len(bucket) >= limit:
        retry_after = max(0, int(window_seconds - (now - bucket[0])))
        return False, retry_after
    bucket.append(now)
    return True, 0


def reset_rate_limits() -> None:
    """Clears rate-limit buckets (used by tests)."""
    _requests.clear()
