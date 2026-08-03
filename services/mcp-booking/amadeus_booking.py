"""Amadeus Orders API client — fare hold and order creation."""
import httpx
from datetime import datetime, timezone, timedelta

from ..shared.settings import settings
from ..shared.logging import logger


class AmadeusBookingClient:
    def __init__(self):
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self._http = httpx.AsyncClient(base_url=settings.amadeus_base_url, timeout=30.0)

    async def _get_token(self) -> str:
        now = datetime.now(timezone.utc)
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token

        resp = await self._http.post(
            "/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.amadeus_client_id,
                "client_secret": settings.amadeus_client_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = now + timedelta(seconds=data["expires_in"] - 60)
        return self._token

    async def _headers(self) -> dict:
        return {"Authorization": f"Bearer {await self._get_token()}"}

    async def price_fare(self, flight_offer: dict) -> dict:
        """Confirm pricing for a flight offer before holding."""
        resp = await self._http.post(
            "/v1/shopping/flight-offers/pricing",
            headers=await self._headers(),
            json={"data": {"type": "flight-offers-pricing", "flightOffers": [flight_offer]}},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["flightOffers"][0]

    async def create_order(
        self,
        flight_offer: dict,
        traveler: dict,
        contact: dict,
    ) -> dict:
        """
        Create a flight order via Amadeus Orders API.
        Returns the full order response including PNR (lastTicketingDate / id).
        """
        payload = {
            "data": {
                "type": "flight-order",
                "flightOffers": [flight_offer],
                "travelers": [traveler],
                "contacts": [contact],
            }
        }
        resp = await self._http.post(
            "/v1/booking/flight-orders",
            headers=await self._headers(),
            json=payload,
        )
        if resp.status_code == 409:
            raise AmadeusOrderConflict("Fare already booked or expired")
        resp.raise_for_status()
        return resp.json()["data"]

    async def _get_fresh_offers(self, route) -> list[dict]:
        """Re-search Amadeus at booking time to get the freshest available offers."""
        resp = await self._http.get(
            "/v2/shopping/flight-offers",
            headers=await self._headers(),
            params={
                "originLocationCode": route.origin,
                "destinationLocationCode": route.destination,
                "departureDate": route.date_from.isoformat(),
                "adults": route.adults,
                "travelClass": route.cabin_class,
                "max": 3,
                "currencyCode": "USD",
            },
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order (for rollback on wallet failure)."""
        resp = await self._http.delete(
            f"/v1/booking/flight-orders/{order_id}",
            headers=await self._headers(),
        )
        if resp.status_code in (200, 204, 404):
            logger.info("amadeus order cancelled/not-found", order_id=order_id)
            return True
        logger.error("amadeus cancel failed", order_id=order_id, status=resp.status_code)
        return False

    async def close(self):
        await self._http.aclose()


class AmadeusOrderConflict(Exception):
    pass


amadeus_booking_client = AmadeusBookingClient()
