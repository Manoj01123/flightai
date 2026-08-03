"""Duffel booking client — offer confirmation and order creation."""
import httpx
from datetime import date
from decimal import Decimal

from ..shared.settings import settings
from ..shared.logging import logger

DUFFEL_VERSION = "v2"


class DuffelBookingClient:
    def __init__(self):
        self._http = httpx.AsyncClient(
            base_url=settings.duffel_base_url,
            headers={
                "Authorization": f"Bearer {settings.duffel_api_key}",
                "Duffel-Version": DUFFEL_VERSION,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=30.0,
        )

    async def search_offers(self, route) -> list[dict]:
        """Search for fresh offers at booking time."""
        payload = {
            "data": {
                "slices": [
                    {
                        "origin": route.origin,
                        "destination": route.destination,
                        "departure_date": route.date_from.isoformat(),
                    }
                ],
                "passengers": [{"type": "adult"} for _ in range(route.adults)],
                "cabin_class": route.cabin_class.lower(),
            }
        }
        resp = await self._http.post("/air/offer_requests", json=payload)
        resp.raise_for_status()
        offer_request_id = resp.json()["data"]["id"]

        offers_resp = await self._http.get(
            "/air/offers",
            params={"offer_request_id": offer_request_id, "limit": 3, "sort": "total_amount"},
        )
        offers_resp.raise_for_status()
        return offers_resp.json().get("data", [])

    async def get_offer(self, offer_id: str) -> dict:
        """Fetch a single offer to confirm current price before booking."""
        resp = await self._http.get(f"/air/offers/{offer_id}")
        resp.raise_for_status()
        return resp.json()["data"]

    async def create_order(self, offer: dict, passengers: list[dict]) -> dict:
        """
        Create a Duffel order (booking).
        Duffel uses balance payment in test mode — no real card needed.
        Returns order dict with booking_reference (PNR).
        """
        payload = {
            "data": {
                "selected_offers": [offer["id"]],
                "passengers": passengers,
                "payments": [
                    {
                        "type": "balance",
                        "amount": offer["total_amount"],
                        "currency": offer["total_currency"],
                    }
                ],
            }
        }
        resp = await self._http.post("/air/orders", json=payload)

        if resp.status_code == 422:
            detail = resp.json().get("errors", [{}])[0].get("message", "Offer unavailable")
            raise DuffelOrderError(detail)

        resp.raise_for_status()
        return resp.json()["data"]

    async def cancel_order(self, order_id: str) -> bool:
        """Request cancellation (creates a cancellation request in Duffel)."""
        try:
            resp = await self._http.post(
                "/air/order_cancellations",
                json={"data": {"order_id": order_id}},
            )
            if resp.status_code in (200, 201):
                cancel_id = resp.json()["data"]["id"]
                # Confirm the cancellation
                confirm_resp = await self._http.post(
                    f"/air/order_cancellations/{cancel_id}/actions/confirm"
                )
                logger.info("duffel order cancelled", order_id=order_id)
                return confirm_resp.status_code in (200, 201)
        except Exception as e:
            logger.error("duffel cancel failed", order_id=order_id, error=str(e))
        return False

    def extract_best_offer(self, offers: list[dict]) -> dict | None:
        if not offers:
            return None
        return min(offers, key=lambda o: float(o["total_amount"]))

    def parse_offer_metadata(self, offer: dict) -> tuple[Decimal, str, str, str]:
        """Returns (price, airline_iata, flight_number, departure_at_iso)."""
        price = Decimal(str(offer["total_amount"]))
        airline = offer.get("owner", {}).get("iata_code", "?")
        slices = offer.get("slices", [])
        departure_at = ""
        flight_number = "?"
        if slices and slices[0].get("segments"):
            seg = slices[0]["segments"][0]
            carrier = seg.get("marketing_carrier", {}).get("iata_code", "")
            number = seg.get("marketing_carrier_flight_number", "")
            flight_number = f"{carrier}{number}"
            departure_at = seg.get("departing_at", "")
        return price, airline, flight_number, departure_at

    async def close(self):
        await self._http.aclose()


class DuffelOrderError(Exception):
    pass


duffel_booking_client = DuffelBookingClient()
