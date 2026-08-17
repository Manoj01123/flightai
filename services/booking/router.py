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
flights_router = APIRouter(prefix="/flights", tags=["flights"])
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
    route_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Booking)
        .where(Booking.user_id == current_user.id)
        .order_by(Booking.created_at.desc())
    )
    if route_id:
        query = query.where(Booking.route_id == route_id)
    result = await db.execute(query)
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


@bookings_router.post("/{booking_id}/payment-intent")
async def create_payment_intent(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe PaymentIntent for the exact flight price. Returns client_secret for Apple Pay."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise NotFoundError("Booking not found")
    if booking.user_id != current_user.id:
        raise ForbiddenError()
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(status_code=409, detail="Booking is not pending")

    import stripe
    stripe.api_key = settings.stripe_secret_key
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(float(booking.price) * 100),
            currency="usd",
            metadata={
                "booking_id": booking_id,
                "user_id": current_user.id,
                "route": f"{booking.origin}-{booking.destination}",
            },
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"client_secret": intent.client_secret, "amount": int(float(booking.price) * 100)}


@bookings_router.post("/{booking_id}/pay", response_model=BookingResponse)
async def pay_booking(
    booking_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify Stripe payment succeeded, then trigger Duffel to create the actual flight order."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise NotFoundError("Booking not found")
    if booking.user_id != current_user.id:
        raise ForbiddenError()
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Booking is already {booking.status}")

    payment_intent_id = body.get("payment_intent_id")
    if not payment_intent_id:
        raise HTTPException(status_code=400, detail="payment_intent_id required")

    import stripe
    stripe.api_key = settings.stripe_secret_key
    try:
        pi = stripe.PaymentIntent.retrieve(payment_intent_id)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if pi.status != "succeeded":
        raise HTTPException(status_code=402, detail="Payment not completed")
    if pi.metadata.get("booking_id") != booking_id:
        raise HTTPException(status_code=403, detail="Payment intent does not match this booking")

    import httpx
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{MCP_BOOKING_URL}/tools/create_order",
            json={"route_id": booking.route_id, "user_id": booking.user_id},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=resp.json().get("detail", "Booking failed"))

    await db.commit()

    refreshed = await db.execute(select(Booking).where(Booking.id == booking.id))
    booking = refreshed.scalar_one()
    return BookingResponse.model_validate(booking)


@flights_router.get("/search")
async def search_flights(
    origin: str,
    destination: str,
    date: str,
    adults: int = 1,
    cabin_class: str = "economy",
    max_connections: int | None = None,
    current_user: User = Depends(get_current_user),
):
    """Search real flights via Duffel and return formatted offer list."""
    from .duffel_booking import duffel_booking_client
    import httpx

    origin = origin.upper().strip()
    destination = destination.upper().strip()

    payload = {
        "data": {
            "slices": [{"origin": origin, "destination": destination, "departure_date": date}],
            "passengers": [{"type": "adult"} for _ in range(adults)],
            "cabin_class": cabin_class.lower(),
        }
    }

    try:
        resp = await duffel_booking_client._http.post("/air/offer_requests", json=payload)
        resp.raise_for_status()
        offer_request_id = resp.json()["data"]["id"]

        params = {"offer_request_id": offer_request_id, "limit": 20, "sort": "total_amount"}
        if max_connections is not None:
            params["max_connections"] = max_connections

        offers_resp = await duffel_booking_client._http.get("/air/offers", params=params)
        offers_resp.raise_for_status()
        raw_offers = offers_resp.json().get("data", [])
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Flight search failed: {e.response.text[:200]}")

    results = []
    for o in raw_offers:
        try:
            slice_ = o["slices"][0]
            segs = slice_.get("segments", [])
            stops = len(segs) - 1
            dep = segs[0]["departing_at"] if segs else None
            arr = segs[-1]["arriving_at"] if segs else None
            airline = segs[0]["operating_carrier"]["name"] if segs else o.get("owner", {}).get("name", "")
            iata = segs[0]["operating_carrier"]["iata_code"] if segs else ""
            duration = slice_.get("duration", "")
            results.append({
                "id": o["id"],
                "price": float(o["total_amount"]),
                "currency": o["total_currency"],
                "airline": airline,
                "airline_iata": iata,
                "stops": stops,
                "origin": origin,
                "destination": destination,
                "departing_at": dep,
                "arriving_at": arr,
                "duration": duration,
                "segments": [
                    {
                        "origin": s["origin"]["iata_code"],
                        "destination": s["destination"]["iata_code"],
                        "departing_at": s["departing_at"],
                        "arriving_at": s["arriving_at"],
                        "flight_number": f"{s['operating_carrier']['iata_code']}{s['operating_carrier_flight_number']}",
                        "airline": s["operating_carrier"]["name"],
                    }
                    for s in segs
                ],
            })
        except (KeyError, IndexError):
            continue

    return results


@admin_bookings_router.get("/bookings", response_model=list[BookingResponse])
async def admin_list_bookings(
    _=Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking).order_by(Booking.created_at.desc()).limit(200)
    )
    return [BookingResponse.model_validate(b) for b in result.scalars().all()]
