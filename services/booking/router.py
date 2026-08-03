import hashlib
import hmac
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..shared.database import get_db
from ..shared.exceptions import NotFoundError, ForbiddenError
from ..shared.settings import settings
from ..user.dependencies import get_current_user, require_admin_user
from ..user.models import User
from .models import Route, Booking, BookingStatus, PriceSnapshot, ConfirmToken
from .schemas import (
    CreateRouteRequest,
    UpdateRouteRequest,
    RouteResponse,
    BookingResponse,
    PriceSnapshotResponse,
)

import os

routes_router = APIRouter(prefix="/routes", tags=["routes"])
bookings_router = APIRouter(prefix="/bookings", tags=["bookings"])
admin_bookings_router = APIRouter(prefix="/admin", tags=["admin"])

MCP_BOOKING_URL = os.getenv("MCP_BOOKING_URL", "http://mcp-booking")


@routes_router.get("", response_model=list[RouteResponse])
async def list_routes(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Route).where(Route.user_id == current_user.id).order_by(Route.created_at.desc())
    if status:
        query = query.where(Route.status == status)
    result = await db.execute(query)
    return [RouteResponse.model_validate(r) for r in result.scalars().all()]


@routes_router.post("", response_model=RouteResponse, status_code=201)
async def create_route(
    body: CreateRouteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    route = Route(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        **body.model_dump(),
    )
    db.add(route)
    await db.flush()
    return RouteResponse.model_validate(route)


@routes_router.get("/{route_id}", response_model=RouteResponse)
async def get_route(
    route_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if not route:
        raise NotFoundError("Route not found")
    if route.user_id != current_user.id:
        raise ForbiddenError()
    return RouteResponse.model_validate(route)


@routes_router.patch("/{route_id}", response_model=RouteResponse)
async def update_route(
    route_id: str,
    body: UpdateRouteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if not route:
        raise NotFoundError("Route not found")
    if route.user_id != current_user.id:
        raise ForbiddenError()

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(route, field, value)
    await db.flush()
    return RouteResponse.model_validate(route)


@routes_router.delete("/{route_id}", status_code=204)
async def delete_route(
    route_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if not route:
        raise NotFoundError("Route not found")
    if route.user_id != current_user.id:
        raise ForbiddenError()
    route.status = "cancelled"
    await db.flush()


@routes_router.get("/{route_id}/snapshots", response_model=list[PriceSnapshotResponse])
@routes_router.get("/{route_id}/prices", response_model=list[PriceSnapshotResponse])
async def get_price_history(
    route_id: str,
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Route).where(Route.id == route_id, Route.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise NotFoundError("Route not found")

    snapshots = await db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.route_id == route_id)
        .order_by(PriceSnapshot.fetched_at.desc())
        .limit(limit)
    )
    return [PriceSnapshotResponse.model_validate(s) for s in snapshots.scalars().all()]


@bookings_router.get("", response_model=list[BookingResponse])
async def list_bookings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking)
        .where(Booking.user_id == current_user.id)
        .order_by(Booking.created_at.desc())
    )
    return [BookingResponse.model_validate(b) for b in result.scalars().all()]


@bookings_router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise NotFoundError("Booking not found")
    if booking.user_id != current_user.id:
        raise ForbiddenError()
    return BookingResponse.model_validate(booking)


@bookings_router.post("/confirm/{token}", response_model=BookingResponse)
async def confirm_booking(token: str, db: AsyncSession = Depends(get_db)):
    """
    Mode A confirmation endpoint — user clicks link from SMS/email.
    Validates HMAC token, checks expiry and single-use, then triggers booking.
    """
    token_hash = hmac.new(
        settings.jwt_secret.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()

    result = await db.execute(
        select(ConfirmToken).where(ConfirmToken.token_hash == token_hash)
    )
    confirm = result.scalar_one_or_none()

    if not confirm:
        raise HTTPException(status_code=404, detail="Invalid confirmation token")

    if confirm.used_at is not None:
        raise HTTPException(status_code=409, detail="Token already used")

    now = datetime.now(timezone.utc)
    if now > confirm.expires_at:
        raise HTTPException(status_code=410, detail="Confirmation token has expired")

    # Mark token as used (single-use enforcement)
    confirm.used_at = now
    await db.flush()

    # Fetch the pending booking
    booking_result = await db.execute(
        select(Booking).where(Booking.id == confirm.booking_id)
    )
    booking = booking_result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Booking is already {booking.status} — cannot confirm"
        )

    # Trigger the actual Amadeus order via mcp-booking (self-contained: fetches offers internally)
    import httpx
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{MCP_BOOKING_URL}/tools/create_order",
            json={"route_id": booking.route_id, "user_id": booking.user_id},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=resp.json().get("detail", "Booking failed"))

    await db.commit()

    # Re-fetch to get updated status from mcp-booking
    refreshed = await db.execute(select(Booking).where(Booking.id == booking.id))
    booking = refreshed.scalar_one()
    return BookingResponse.model_validate(booking)


@admin_bookings_router.get("/bookings", response_model=list[BookingResponse])
async def admin_list_bookings(
    _=Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking).order_by(Booking.created_at.desc()).limit(200)
    )
    return [BookingResponse.model_validate(b) for b in result.scalars().all()]
