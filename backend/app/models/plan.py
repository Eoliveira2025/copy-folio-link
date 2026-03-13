"""Subscription Plan model."""

import uuid
from sqlalchemy import String, Float, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    allowed_strategies: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["low","medium","high"]
    trial_days: Mapped[int] = mapped_column(Integer, default=30)
    max_accounts: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    subscriptions = relationship("Subscription", back_populates="plan")
