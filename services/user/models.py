import uuid
from datetime import date, datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import String, Boolean, DateTime, Date, func
from sqlalchemy.orm import Mapped, mapped_column

from ..shared.database import Base


class BookingMode(str, Enum):
    ALERT = "A"       # alert + confirm
    AUTONOMOUS = "B"  # auto-book


class UserTier(str, Enum):
    FREE = "free"
    PRO = "pro"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    booking_mode: Mapped[str] = mapped_column(String(1), default=BookingMode.ALERT)
    tier: Mapped[str] = mapped_column(String(20), default=UserTier.FREE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    push_notifications: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # Passenger details for flight bookings (required by Duffel)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)   # "m" or "f"
    title: Mapped[str | None] = mapped_column(String(10), nullable=True)    # "mr","ms","mrs","miss","dr"
    fcm_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    push_subscription: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
