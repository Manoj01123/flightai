"""MCP Notifier Server — SMS, email, and confirm link tools."""
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from ..shared.logging import logger
from ..shared.settings import settings
from .tools import (
    send_sms,
    send_email,
    gen_confirm_link,
    send_confirm_link,
    send_booking_confirmation,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("mcp-notifier starting")
    _start_pubsub_listener()
    yield
    logger.info("mcp-notifier stopped")


app = FastAPI(title="FlightAI MCP Notifier", lifespan=lifespan)


# ── Request schemas ───────────────────────────────────────────────────────────

class SendSmsRequest(BaseModel):
    to_number: str
    body: str


class SendEmailRequest(BaseModel):
    to_email: str
    subject: str
    html_body: str
    plain_body: str = ""


class GenConfirmLinkRequest(BaseModel):
    booking_id: str
    user_id: str
    route_id: str
    price: str


class SendConfirmLinkRequest(BaseModel):
    route_id: str
    user_id: str
    booking_id: str
    price: str
    origin: str
    destination: str
    airline: str
    to_phone: str | None = None
    to_email: str | None = None


class SendBookingConfirmationRequest(BaseModel):
    booking_id: str
    user_id: str
    route_id: str
    price: str
    airline: str
    flight_number: str
    origin: str
    destination: str
    to_phone: str | None = None
    to_email: str | None = None


# ── Tool endpoints ─────────────────────────────────────────────────────────────

@app.post("/tools/send_sms")
async def tool_send_sms(body: SendSmsRequest):
    return await send_sms(to_number=body.to_number, body=body.body)


@app.post("/tools/send_email")
async def tool_send_email(body: SendEmailRequest):
    return await send_email(
        to_email=body.to_email,
        subject=body.subject,
        html_body=body.html_body,
        plain_body=body.plain_body,
    )


@app.post("/tools/gen_confirm_link")
async def tool_gen_confirm_link(body: GenConfirmLinkRequest):
    return await gen_confirm_link(
        booking_id=body.booking_id,
        user_id=body.user_id,
        route_id=body.route_id,
        price=body.price,
    )


@app.post("/tools/send_confirm_link")
async def tool_send_confirm_link(body: SendConfirmLinkRequest):
    return await send_confirm_link(
        route_id=body.route_id,
        user_id=body.user_id,
        price=body.price,
        to_phone=body.to_phone,
        to_email=body.to_email,
        booking_id=body.booking_id,
        origin=body.origin,
        destination=body.destination,
        airline=body.airline,
    )


@app.post("/tools/send_booking_confirmation")
async def tool_send_booking_confirmation(body: SendBookingConfirmationRequest):
    return await send_booking_confirmation(
        booking_id=body.booking_id,
        user_id=body.user_id,
        route_id=body.route_id,
        price=body.price,
        airline=body.airline,
        flight_number=body.flight_number,
        to_phone=body.to_phone,
        to_email=body.to_email,
        origin=body.origin,
        destination=body.destination,
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-notifier"}


# ── Pub/Sub subscriber for booking.confirmed ──────────────────────────────────

def _start_pubsub_listener():
    """Subscribe to booking.confirmed and wallet.low Pub/Sub topics."""
    import threading
    from google.cloud import pubsub_v1

    if not settings.gcp_project_id:
        logger.warning("GCP_PROJECT_ID not set — skipping Pub/Sub listeners")
        return

    subscriber = pubsub_v1.SubscriberClient()

    # ── booking.confirmed ─────────────────────────────────────────────────────
    def on_booking_confirmed(message):
        try:
            data = json.loads(message.data.decode())
            logger.info("booking.confirmed received", booking_id=data.get("booking_id"))
            import asyncio
            asyncio.run(
                send_booking_confirmation(
                    booking_id=data["booking_id"],
                    user_id=data["user_id"],
                    route_id=data["route_id"],
                    price=data["price"],
                    airline=data.get("airline", ""),
                    flight_number=data.get("flight_number", ""),
                    to_phone=data.get("phone"),
                    to_email=data.get("email"),
                    origin=data.get("origin", ""),
                    destination=data.get("destination", ""),
                )
            )
            message.ack()
        except Exception as e:
            logger.error("booking.confirmed callback error", error=str(e))
            message.nack()

    booking_sub = subscriber.subscription_path(settings.gcp_project_id, "booking-confirmed-notifier-sub")
    f1 = subscriber.subscribe(booking_sub, callback=on_booking_confirmed)
    threading.Thread(target=f1.result, daemon=True).start()
    logger.info("listening on booking.confirmed", subscription=booking_sub)

    # ── wallet.low ────────────────────────────────────────────────────────────
    def on_wallet_low(message):
        try:
            data = json.loads(message.data.decode())
            logger.info("wallet.low received", user_id=data.get("user_id"))
            import asyncio
            phone = data.get("phone")
            email = data.get("email")
            balance = data.get("balance", "0")
            body = f"⚠️ FlightAI: Your wallet balance is low (${balance}). Top up to keep your agent running."
            if phone:
                asyncio.run(send_sms(to_number=phone, body=body))
            if email:
                asyncio.run(send_email(
                    to_email=email,
                    subject="⚠️ FlightAI wallet balance low",
                    html_body=f"<p>{body}</p><a href='https://app.flightai.io/wallet'>Top up now</a>",
                ))
            message.ack()
        except Exception as e:
            logger.error("wallet.low callback error", error=str(e))
            message.nack()

    wallet_sub = subscriber.subscription_path(settings.gcp_project_id, "wallet-low-notifier-sub")
    f2 = subscriber.subscribe(wallet_sub, callback=on_wallet_low)
    threading.Thread(target=f2.result, daemon=True).start()
    logger.info("listening on wallet.low", subscription=wallet_sub)
