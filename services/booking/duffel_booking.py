import httpx
from ..shared.settings import settings

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


duffel_booking_client = DuffelClient()
