from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from api.app.database import Base

THREAT_LEVELS = ("safe", "watch", "warning", "critical")


class BiosensorReading(Base):
    __tablename__ = "biosensor_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    farm_id: Mapped[int | None] = mapped_column(Integer, index=True)
    crop_name: Mapped[str] = mapped_column(String(120), default="coffee", nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(80), index=True)

    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    threat_level: Mapped[str] = mapped_column(String(24), default="safe", nullable=False)
    threats: Mapped[list] = mapped_column(JSON, default=list)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
