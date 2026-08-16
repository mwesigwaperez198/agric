from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from api.app.database import Base


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    crop_type: Mapped[str] = mapped_column(String(64), default="coffee", nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(512))
    prompt: Mapped[str | None] = mapped_column(Text)

    prediction: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model: Mapped[str] = mapped_column(String(64), default="mock-cnn", nullable=False)
    guardrail_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    advice: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    crop_name: Mapped[str] = mapped_column(String(120), default="coffee", nullable=False)
    dialect: Mapped[str] = mapped_column(String(16), default="en", nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
