"""System settings and risk incident models."""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Float, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    global_max_drawdown_percent: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    protection_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RiskIncident(Base):
    __tablename__ = "risk_incidents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False)
    drawdown_percent: Mapped[float] = mapped_column(Float, nullable=False)
    total_balance: Mapped[float] = mapped_column(Float, nullable=False)
    total_equity: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
