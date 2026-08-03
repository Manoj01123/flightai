"""MCP Booking Server — exposes hold_fare and create_order as HTTP tool endpoints."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..shared.logging import logger
from .duffel_booking import duffel_booking_client
from .tools import hold_fare, create_order


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("mcp-booking starting")
    yield
    await duffel_booking_client.close()
    logger.info("mcp-booking stopped")


app = FastAPI(title="FlightAI MCP Booking", lifespan=lifespan)


# ── Request / Response schemas ────────────────────────────────────────────────

class HoldFareRequest(BaseModel):
    route_id: str
    offer_id: str


class CreateOrderRequest(BaseModel):
    route_id: str
    user_id: str


# ── Tool endpoints ─────────────────────────────────────────────────────────────

@app.post("/tools/hold_fare")
async def tool_hold_fare(body: HoldFareRequest):
    result = await hold_fare(route_id=body.route_id, offer_id=body.offer_id)
    if not result.get("confirmed"):
        raise HTTPException(status_code=409, detail=result.get("error", "Fare confirmation failed"))
    return result


@app.post("/tools/create_order")
async def tool_create_order(body: CreateOrderRequest):
    result = await create_order(route_id=body.route_id, user_id=body.user_id)
    if not result.get("success"):
        raise HTTPException(status_code=422, detail=result.get("error", "Booking failed"))
    return result


@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-booking"}
