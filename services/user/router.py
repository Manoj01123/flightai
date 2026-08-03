from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..shared.database import get_db
from ..shared.exceptions import ConflictError, UnauthorizedError
from .auth import hash_password, verify_password, create_access_token
from .dependencies import get_current_user, require_admin_user
from .models import User
from .schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    AuthResponse,
    UserResponse,
    UpdateNotificationsRequest,
    UpdateMeRequest,
)

import uuid

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["users"])
users_router = APIRouter(prefix="/users", tags=["users"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise ConflictError("Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        hashed_password=hash_password(body.password),
        phone=body.phone,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    db.add(user)
    await db.flush()
    from ..shared.settings import settings
    token = create_access_token(user.id, user.email, user.tier, user.booking_mode)
    return AuthResponse(
        access_token=token,
        expires_in=settings.jwt_expiry_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise UnauthorizedError("Invalid credentials")

    token = create_access_token(user.id, user.email, user.tier, user.booking_mode)
    from ..shared.settings import settings
    return AuthResponse(
        access_token=token,
        expires_in=settings.jwt_expiry_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@me_router.get("", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@me_router.patch("/notifications", response_model=UserResponse)
async def update_notifications(
    body: UpdateNotificationsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.sms_notifications is not None:
        current_user.sms_notifications = body.sms_notifications
    if body.email_notifications is not None:
        current_user.email_notifications = body.email_notifications
    if body.push_notifications is not None:
        current_user.push_notifications = body.push_notifications
    if body.booking_mode is not None:
        current_user.booking_mode = body.booking_mode
    await db.flush()
    return UserResponse.model_validate(current_user)


# /v1/users/me — called by frontend Settings + AuthContext (FCM token)
@users_router.get("/me", response_model=UserResponse)
async def get_users_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@users_router.patch("/me", response_model=UserResponse)
async def update_users_me(
    body: UpdateMeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for field in ("sms_notifications", "email_notifications", "push_notifications",
                  "booking_mode", "fcm_token", "phone",
                  "date_of_birth", "gender", "title"):
        value = getattr(body, field, None)
        if value is not None and hasattr(current_user, field):
            setattr(current_user, field, value)
    await db.flush()
    return UserResponse.model_validate(current_user)


# ── Push notification subscription ──────────────────────────────────────────────
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])

@notifications_router.post("/push-subscribe", status_code=204)
async def push_subscribe(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json
    current_user.push_subscription = json.dumps(body)
    current_user.push_notifications = True
    await db.flush()


@notifications_router.delete("/push-subscribe", status_code=204)
async def push_unsubscribe(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.push_subscription = None
    current_user.push_notifications = False
    await db.flush()


# Admin endpoints
@admin_router.get("/users", response_model=list[UserResponse])
async def admin_list_users(
    _: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()).limit(200))
    return [UserResponse.model_validate(u) for u in result.scalars().all()]
