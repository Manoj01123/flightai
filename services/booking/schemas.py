from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, field_validator


class CreateRouteRequest(BaseModel):
    origin: str
    destination: str
    date_from: date
    date_to: date
    target_price: Decimal
    booking_mode: str = "A"
    adults: int = 1
    cabin_class: str = "ECONOMY"
    max_connections: int | None = None

    @field_validator("origin", "destination")
    @classmethod
    def iata_code(cls, v: str) -> str:
        v = v.upper().strip()
        if len(v) != 3:
            raise ValueError("Must be a 3-letter IATA airport code")
        return v

    @field_validator("booking_mode")
    @classmethod
    def valid_mode(cls, v: str) -> str:
        if v not in ("A", "B"):
            raise ValueError("booking_mode must be 'A' (alert) or 'B' (autonomous)")
        return v

    @field_validator("target_price")
    @classmethod
    def price_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Target price must be positive")
        return v


class UpdateRouteRequest(BaseModel):
    target_price: Decimal | None = None
    booking_mode: str | None = None
    status: str | None = None


class RouteResponse(BaseModel):
    id: str
    user_id: str
    origin: str
    destination: str
    date_from: date
    date_to: date
    target_price: Decimal
    booking_mode: str
    status: str
    adults: int
    cabin_class: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BookingResponse(BaseModel):
    id: str
    route_id: str
    user_id: str
    price: Decimal
    airline: str | None
    origin: str
    destination: str
    departure_at: datetime | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PriceSnapshotResponse(BaseModel):
    id: str
    route_id: str
    price: Decimal
    airline: str | None
    flight_number: str | None
    departure_at: datetime | None
    fetched_at: datetime

    model_config = {"from_attributes": True}
