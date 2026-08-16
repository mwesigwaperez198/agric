from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FarmCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    region: str = Field(min_length=2, max_length=120)
    country: str = "UG"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    certifications: str | None = None


class FarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    description: str | None
    region: str
    country: str
    latitude: float | None
    longitude: float | None
    certifications: str | None
    created_at: datetime


class WalletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    balance: float
    currency: str
