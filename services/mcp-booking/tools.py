"""MCP tool implementations for flight booking."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from ..shared.database import AsyncSessionLocal
from ..shared.logging import logger
from ..booking.models import Booking, BookingAttempt, BookingStatus, Route, RouteStatus
from ..user.models import User
from ..wallet.service import debit_wallet
from ..shared.exceptions import InsufficientFundsError, NotFoundError
from .duffel_booking import duffel_booking_client, DuffelOrderError
from .encryption import encrypt_pnr


async def hold_fare(route_id: str, offer_id: str) -> dict:
    """
    MCP tool: confirm a Duffel offer's current price before create_order.
    Returns the refreshed offer with confirmed price.
    """
    try:
        confirmed_offer = await duffel_booking_client.get_offer(offer_id)
        price, airline, flight_number, _ = duffel_booking_client.parse_offer_metadata(confirmed_offer)
        logger.info("fare confirmed", route_id=route_id, price=str(price))
        return {"confirmed": True, "offer": confirmed_offer, "price": str(price), "airline": airline}
    except Exception as e:
        logger.error("hold_fare failed", route_id=route_id, error=str(e))
        return {"confirmed": False, "error": str(e)}


async def create_order(route_id: str, user_id: str) -> dict:
    """
    MCP tool: fully self-contained end-to-end booking.

    Flow:
      1. Idempotency check — bail if booking already exists for this route
      2. Fetch route + user from DB
      3. Re-search Amadeus for fresh offers + confirm pricing
      4. Create pending booking row + attempt row
      5. Call Amadeus Orders API
      6. Debit wallet (amount + $5 fee)
      7. Encrypt PNR, confirm booking, mark route booked
      8. Rollback Amadeus order if wallet debit fails
    """
    async with AsyncSessionLocal() as db:
        # ── 1. Idempotency ──────────────────────────────────────────────────
        existing = await db.execute(
            select(Booking).where(
                Booking.route_id == route_id,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
            )
        )
        if existing.scalar_one_or_none():
            logger.warning("booking already exists for route", route_id=route_id)
            return {"success": False, "error": "Booking already exists for this route"}

        # ── 2. Fetch route + user ───────────────────────────────────────────
        route_result = await db.execute(select(Route).where(Route.id == route_id))
        route = route_result.scalar_one_or_none()
        if not route:
            raise NotFoundError(f"Route {route_id} not found")

        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise NotFoundError(f"User {user_id} not found")

        # ── 3. Re-search Duffel + pick best offer ───────────────────────────
        try:
            offers = await duffel_booking_client.search_offers(route)
            best_offer = duffel_booking_client.extract_best_offer(offers)
            if not best_offer:
                return {"success": False, "error": "No available offers found at booking time"}
            # Refresh offer to confirm latest price
            confirmed_offer = await duffel_booking_client.get_offer(best_offer["id"])
        except Exception as e:
            logger.error("duffel search failed at booking", route_id=route_id, error=str(e))
            return {"success": False, "error": f"Could not retrieve offer: {e}"}

        price, airline, flight_number, departure_str = duffel_booking_client.parse_offer_metadata(confirmed_offer)
        departure_at = datetime.fromisoformat(departure_str) if departure_str else None

        booking_id = str(uuid.uuid4())
        idempotency_key = f"booking:{booking_id}"

        # ── 4. Pending booking + attempt ────────────────────────────────────
        booking = Booking(
            id=booking_id,
            route_id=route_id,
            user_id=user_id,
            price=price,
            airline=airline,
            origin=route.origin,
            destination=route.destination,
            departure_at=departure_at,
            status=BookingStatus.PENDING,
        )
        attempt = BookingAttempt(
            id=str(uuid.uuid4()),
            booking_id=booking_id,
            fare_id=confirmed_offer.get("id", ""),
            status="in_progress",
        )
        db.add(booking)
        db.add(attempt)
        await db.flush()

        # ── 5. Duffel order creation ────────────────────────────────────────
        passengers = [_build_duffel_passenger(user, confirmed_offer)]

        try:
            duffel_order = await duffel_booking_client.create_order(
                offer=confirmed_offer,
                passengers=passengers,
            )
        except DuffelOrderError as e:
            attempt.status = "failed"
            attempt.error_msg = str(e)
            booking.status = BookingStatus.FAILED
            await db.commit()
            return {"success": False, "error": str(e)}
        except Exception as e:
            attempt.status = "failed"
            attempt.error_msg = str(e)
            booking.status = BookingStatus.FAILED
            await db.commit()
            logger.error("duffel order failed", route_id=route_id, error=str(e))
            return {"success": False, "error": f"Duffel error: {e}"}

        duffel_order_id = duffel_order.get("id", "")
        raw_pnr = duffel_order.get("booking_reference", "")

        # ── 6. Debit wallet ─────────────────────────────────────────────────
        try:
            await debit_wallet(
                user_id=user_id,
                amount=price,
                idempotency_key=idempotency_key,
                description=f"Flight {route.origin}→{route.destination} {airline}{flight_number}",
                related_booking_id=booking_id,
                db=db,
            )
        except InsufficientFundsError as e:
            await duffel_booking_client.cancel_order(duffel_order_id)
            attempt.status = "failed"
            attempt.error_msg = f"Insufficient funds: {e}"
            booking.status = BookingStatus.FAILED
            await db.commit()
            logger.warning("wallet debit failed, duffel order cancelled", order_id=duffel_order_id)
            return {"success": False, "error": str(e)}
        except Exception as e:
            await duffel_booking_client.cancel_order(duffel_order_id)
            attempt.status = "failed"
            attempt.error_msg = str(e)
            booking.status = BookingStatus.FAILED
            await db.commit()
            return {"success": False, "error": str(e)}

        # ── 7. Confirm ──────────────────────────────────────────────────────
        if raw_pnr:
            try:
                booking.pnr_encrypted = encrypt_pnr(raw_pnr)
            except Exception as enc_err:
                logger.warning("PNR encryption failed, storing unencrypted", error=str(enc_err))
                booking.pnr_encrypted = raw_pnr
        else:
            booking.pnr_encrypted = None
        booking.amadeus_order_id = duffel_order_id
        booking.status = BookingStatus.CONFIRMED
        attempt.status = "succeeded"
        route.status = RouteStatus.BOOKED
        await db.commit()

        logger.info("booking confirmed", booking_id=booking_id, route_id=route_id, price=str(price))

        try:
            _publish_booking_confirmed(
                booking_id=booking_id,
                user_id=user_id,
                route_id=route_id,
                price=price,
                airline=airline,
                flight_number=flight_number,
                origin=route.origin,
                destination=route.destination,
                phone=user.phone if user.sms_notifications else None,
                email=user.email if user.email_notifications else None,
            )
        except Exception as pub_err:
            logger.warning("booking.confirmed publish failed (non-fatal)", error=str(pub_err))

        return {
            "success": True,
            "booking_id": booking_id,
            "duffel_order_id": duffel_order_id,
            "price": str(price),
            "airline": airline,
            "flight_number": flight_number,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_duffel_passenger(user: User, offer: dict) -> dict:
    """Build Duffel passenger dict from user + the offer's passenger_id."""
    offer_passenger_id = offer.get("passengers", [{}])[0].get("id", "")

    gender = getattr(user, "gender", None) or "m"
    title = getattr(user, "title", None) or ("mr" if gender == "m" else "ms")
    born_on = getattr(user, "date_of_birth", None)
    born_on_str = born_on.isoformat() if born_on else "1990-01-01"

    if not getattr(user, "date_of_birth", None):
        logger.warning("passenger date_of_birth missing, using placeholder", user_id=user.id)

    return {
        "id": offer_passenger_id,
        "given_name": user.first_name or "Traveler",
        "family_name": user.last_name or "Unknown",
        "email": user.email,
        "phone_number": user.phone or "+10000000000",
        "born_on": born_on_str,
        "gender": gender,
        "title": title,
    }


def _publish_booking_confirmed(
    booking_id: str, user_id: str, route_id: str, price: Decimal,
    airline: str, flight_number: str, origin: str, destination: str,
    phone: str | None, email: str | None,
):
    import json
    from google.cloud import pubsub_v1
    from ..shared.settings import settings

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.gcp_project_id, settings.pubsub_topic_booking_confirmed)
    message = {
        "booking_id": booking_id,
        "user_id": user_id,
        "route_id": route_id,
        "price": str(price),
        "airline": airline,
        "flight_number": flight_number,
        "origin": origin,
        "destination": destination,
        "phone": phone,
        "email": email,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    publisher.publish(topic_path, data=json.dumps(message).encode())
    logger.info("booking.confirmed published", booking_id=booking_id)
