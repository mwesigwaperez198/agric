from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ROLES = ("farmer", "consumer", "admin")


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    role: str = Field(default="consumer", pattern="^(farmer|consumer)$")
    locale: str = Field(default="en", max_length=16)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TotpConfirmRequest(BaseModel):
    email: EmailStr
    password: str
    code: str = Field(min_length=6, max_length=6)


class TotpEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TokenPair(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    totp_required: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    locale: str
    phone: str | None
    is_active: bool
    is_verified: bool
    totp_enabled: bool
    created_at: datetime
