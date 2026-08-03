import httpx
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal

from ..shared.settings import settings
from ..shared.logging import logger


class AmadeusClient:
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

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        adults: int = 1,
        cabin_class: str = "ECONOMY",
        max_results: int = 5,
    ) -> list[dict]:
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}

        resp = await self._http.get(
            "/v2/shopping/flight-offers",
            headers=headers,
            params={
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date.isoformat(),
                "adults": adults,
                "travelClass": cabin_class,
                "max": max_results,
                "currencyCode": "USD",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    def extract_best_price(self, offers: list[dict]) -> tuple[Decimal, str, str] | None:
        if not offers:
            return None
        best = min(offers, key=lambda o: float(o["price"]["grandTotal"]))
        price = Decimal(str(best["price"]["grandTotal"]))
        airline = best["validatingAirlineCodes"][0] if best.get("validatingAirlineCodes") else "?"
        itinerary = best["itineraries"][0]["segments"][0]
        flight_number = f"{itinerary['carrierCode']}{itinerary['number']}"
        return price, airline, flight_number

    async def close(self):
        await self._http.aclose()


amadeus_client = AmadeusClient()
