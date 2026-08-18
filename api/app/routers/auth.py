from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from api.app.deps import CurrentUser, DbSession, decode_refresh_token
from api.app.models import User
from api.app.schemas.auth import (
    LoginRequest,
    OtpSendRequest,
    OtpSetupRequest,
    OtpVerifyRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    TotpConfirmRequest,
    TotpEnableRequest,
    TotpSetupResponse,
    UserOut,
)
from api.app.security import (
    create_access_token,
    create_refresh_token,
    decrypt_field,
    encrypt_field,
    generate_totp_secret,
    hash_password,
    rate_limit,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from api.app.services.otp import (
    create_otp,
    mask_target,
    send_email_otp,
    send_sms_otp,
    verify_otp,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role),
        refresh_token=create_refresh_token(str(user.id)),
    )


# ---------------------------------------------------------------------------
# Register / Login / Refresh / Me
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, db: DbSession):
    allowed, retry = rate_limit(f"register:{request.client.host}", limit=30)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts, retry in {retry}s")

    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if body.phone and db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(status_code=409, detail="Phone already registered")

    user = User(
        email=str(body.email).lower(),
        full_name=body.full_name.strip(),
        phone=body.phone,
        password_hash=hash_password(body.password),
        role=body.role,
        locale=body.locale,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_pair(user)


@router.post("/login-phone", response_model=TokenPair)
def login_phone(body: dict, request: Request, db: DbSession):
    """Login with phone number + 4-digit PIN (WhatsApp-created accounts)."""
    allowed, retry = rate_limit(f"login:{request.client.host}", limit=30)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts, retry in {retry}s")

    phone = (body.get("phone") or "").strip()
    pin = (body.get("pin") or "").strip()
    if not phone or not pin:
        raise HTTPException(status_code=400, detail="Phone and PIN are required")

    user = db.query(User).filter(User.phone == phone).first()
    if not user or not verify_password(pin, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone or PIN")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return _token_pair(user)


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, request: Request, db: DbSession):
    allowed, retry = rate_limit(f"login:{request.client.host}", limit=30)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts, retry in {retry}s")

    user = db.query(User).filter(User.email == str(body.email).lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # TOTP 2FA (authenticator app)
    if user.totp_enabled:
        return TokenPair(totp_required=True)

    # OTP 2FA (SMS or email)
    if user.otp_enabled and user.otp_method:
        target = user.phone if user.otp_method == "sms" else user.email
        if not target:
            return _token_pair(user)
        otp = create_otp(db, user.id, user.otp_method, target)
        code = otp._plain_code  # type: ignore[attr-defined]
        if user.otp_method == "sms":
            send_sms_otp(target, code)
        else:
            send_email_otp(target, code)
        return TokenPair(otp_required=True, otp_target=mask_target(target, user.otp_method))

    return _token_pair(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: DbSession):
    payload = decode_refresh_token(body.refresh_token)
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account inactive or missing")
    return _token_pair(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


# ---------------------------------------------------------------------------
# TOTP 2FA (authenticator app)
# ---------------------------------------------------------------------------


@router.post("/totp/login", response_model=TokenPair)
def totp_login(body: TotpConfirmRequest, request: Request, db: DbSession):
    """Second factor step: email + password + TOTP code -> tokens."""
    allowed, retry = rate_limit(f"totp:{request.client.host}", limit=30)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts, retry in {retry}s")

    user = db.query(User).filter(User.email == str(body.email).lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    secret = decrypt_field(user.totp_secret_enc or "")
    if not user.totp_enabled or not secret or not verify_totp(secret, body.code):
        raise HTTPException(status_code=401, detail="Invalid 2FA code")

    return _token_pair(user)


@router.post("/totp/setup", response_model=TotpSetupResponse)
def totp_setup(user: CurrentUser, db: DbSession):
    secret = generate_totp_secret()
    user.totp_secret_enc = encrypt_field(secret)
    db.commit()
    return TotpSetupResponse(secret=secret, provisioning_uri=totp_provisioning_uri(secret, user.email))


@router.post("/totp/enable", response_model=UserOut)
def totp_enable(body: TotpEnableRequest, user: CurrentUser, db: DbSession):
    secret = decrypt_field(user.totp_secret_enc or "")
    if not secret or not verify_totp(secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")
    user.totp_enabled = True
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# OTP 2FA (SMS / Email)
# ---------------------------------------------------------------------------


@router.post("/otp/send")
def otp_send(body: OtpSendRequest, user: CurrentUser, request: Request, db: DbSession):
    """Send an OTP code to the user's phone or email."""
    allowed, retry = rate_limit(f"otp-send:{user.id}", limit=3, window_seconds=600)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many requests, retry in {retry}s")

    target = user.phone if body.delivery == "sms" else user.email
    if not target:
        field = "phone number" if body.delivery == "sms" else "email"
        raise HTTPException(status_code=400, detail=f"No {field} on account")

    otp = create_otp(db, user.id, body.delivery, target)
    code = otp._plain_code  # type: ignore[attr-defined]

    sent = False
    if body.delivery == "sms":
        sent = send_sms_otp(target, code)
    else:
        sent = send_email_otp(target, code)

    if not sent:
        raise HTTPException(status_code=502, detail="Failed to send verification code")

    return {"delivery": body.delivery, "target": mask_target(target, body.delivery)}


@router.post("/otp/verify", response_model=TokenPair)
def otp_verify(body: OtpVerifyRequest, request: Request, db: DbSession):
    """Second factor step: email + password + OTP code -> tokens."""
    allowed, retry = rate_limit(f"otp-verify:{request.client.host}", limit=30)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many attempts, retry in {retry}s")

    user = db.query(User).filter(User.email == str(body.email).lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_otp(db, user.id, body.code):
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    return _token_pair(user)


@router.post("/otp/setup", response_model=UserOut)
def otp_setup(body: OtpSetupRequest, user: CurrentUser, db: DbSession):
    """Enable OTP 2FA after verifying the first code."""
    if not user.phone and body.delivery == "sms":
        raise HTTPException(status_code=400, detail="No phone number on account. Update your profile first.")
    if body.delivery == "sms" and user.phone:
        target = user.phone
    elif body.delivery == "email":
        target = user.email
    else:
        raise HTTPException(status_code=400, detail="Invalid delivery method")

    otp = create_otp(db, user.id, body.delivery, target)
    code = otp._plain_code  # type: ignore[attr-defined]

    sent = False
    if body.delivery == "sms":
        sent = send_sms_otp(target, code)
    else:
        sent = send_email_otp(target, code)

    if not sent:
        raise HTTPException(status_code=502, detail="Failed to send verification code")

    if not verify_otp(db, user.id, body.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    user.otp_enabled = True
    user.otp_method = body.delivery
    db.commit()
    db.refresh(user)
    return user


@router.post("/otp/disable", response_model=UserOut)
def otp_disable(user: CurrentUser, db: DbSession):
    """Disable OTP 2FA."""
    user.otp_enabled = False
    user.otp_method = None
    db.commit()
    db.refresh(user)
    return user
