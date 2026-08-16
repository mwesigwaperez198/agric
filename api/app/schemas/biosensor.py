from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

THREAT_LEVELS = ("safe", "watch", "warning", "critical")


class BiosensorPayload(BaseModel):
    """Free-form sensor reading. Values are strings/numbers as received from devices."""

    model_config = ConfigDict(extra="allow")

    device_id: str = Field(min_length=1, max_length=80)
    farm_id: int | None = None
    crop_name: str = "coffee"
    batch_id: str | None = None
    read_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Threat(BaseModel):
    code: str
    label: str
    level: str
    message: str
    value: float | None = None
    limit: float | None = None


class BiosensorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    farm_id: int | None
    crop_name: str
    batch_id: str | None
    payload: dict[str, Any]
    threat_level: str
    threats: list[dict[str, Any]]
    risk_score: float
    received_at: datetime
    read_at: datetime | None


class BiosensorSeries(BaseModel):
    device_id: str
    crop_name: str
    readings: list[BiosensorOut]
