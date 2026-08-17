"""Duffel flight search client — replaces Amadeus FlightOffersSearch."""
import httpx
from datetime import date
from decimal import Decimal

from ..shared.settings import settings
from ..shared.logging import logger

DUFFEL_VERSION = "v2"


class DuffelClient:
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

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        adults: int = 1,
        cabin_class: str = "ECONOMY",
        max_results: int = 5,
    ) -> list[dict]:
        """
        Two-step Duffel search:
          1. POST /air/offer_requests  → gets offer_request_id
          2. GET  /air/offers          → returns list of offers
        """
        cabin = cabin_class.lower()  # Duffel uses lowercase: economy, business, first
        if cabin not in ("economy", "premium_economy", "business", "first"):
            cabin = "economy"

        # Step 1 — create offer request
        payload = {
            "data": {
                "slices": [
                    {
                        "origin": origin,
                        "destination": destination,
                        "departure_date": departure_date.isoformat(),
                    }
                ],
                "passengers": [{"type": "adult"} for _ in range(adults)],
                "cabin_class": cabin,
            }
        }
        resp = await self._http.post("/air/offer_requests", json=payload)
        resp.raise_for_status()
        offer_request_id = resp.json()["data"]["id"]

        # Step 2 — fetch offers
        offers_resp = await self._http.get(
            "/air/offers",
            params={
                "offer_request_id": offer_request_id,
                "limit": max_results,
                "sort": "total_amount",
            },
        )
        offers_resp.raise_for_status()
        return offers_resp.json().get("data", [])

    def extract_best_price(self, offers: list[dict], max_connections: int | None = None) -> tuple[Decimal, str, str] | None:
        """Return (price, airline_name, flight_number) from the cheapest matching offer."""
        if not offers:
            return None

        if max_connections is not None:
            offers = [
                o for o in offers
                if sum(len(s.get("segments", [])) - 1 for s in o.get("slices", [])) <= max_connections
            ]
        if not offers:
            return None

        best = min(offers, key=lambda o: float(o["total_amount"]))
        price = Decimal(str(best["total_amount"]))

        slices = best.get("slices", [])
        if slices and slices[0].get("segments"):
            seg = slices[0]["segments"][0]
            airline = seg.get("operating_carrier", {}).get("name") or best.get("owner", {}).get("name", "?")
            carrier_iata = seg.get("marketing_carrier", {}).get("iata_code", "")
            number = seg.get("marketing_carrier_flight_number", "")
            flight_number = f"{carrier_iata}{number}"
        else:
            airline = best.get("owner", {}).get("name", "?")
            flight_number = "?"

        return price, airline, flight_number

    async def close(self):
        await self._http.aclose()


duffel_client = DuffelClient()
