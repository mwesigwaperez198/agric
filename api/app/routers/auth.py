from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from api.app.deps import CurrentUser, DbSession, decode_refresh_token
from api.app.models import User
from api.app.schemas.auth import (
    LoginRequest,
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

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role),
        refresh_token=create_refresh_token(str(user.id)),
    )


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

    if user.totp_enabled:
        return TokenPair(totp_required=True)

    return _token_pair(user)


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
