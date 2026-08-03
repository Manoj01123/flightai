from datetime import date, datetime
from pydantic import BaseModel, EmailStr, field_validator
import re


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: str
    email: str
    phone: str | None
    first_name: str | None
    last_name: str | None
    booking_mode: str
    tier: str
    sms_notifications: bool
    email_notifications: bool
    push_notifications: bool
    is_admin: bool = False
    date_of_birth: date | None = None
    gender: str | None = None
    title: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateNotificationsRequest(BaseModel):
    sms_notifications: bool | None = None
    email_notifications: bool | None = None
    push_notifications: bool | None = None
    booking_mode: str | None = None


class UpdateMeRequest(BaseModel):
    sms_notifications: bool | None = None
    email_notifications: bool | None = None
    push_notifications: bool | None = None
    booking_mode: str | None = None
    fcm_token: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    title: str | None = None
