"""MCP tool implementations for notifications and confirm-link generation."""
import hashlib
import hmac
import uuid
from datetime import datetime, timezone, timedelta

from ..shared.logging import logger
from ..shared.settings import settings


# ── SMS via Twilio ────────────────────────────────────────────────────────────

async def send_sms(to_number: str, body: str) -> dict:
    """MCP tool: send an SMS via Twilio."""
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException

    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        message = client.messages.create(
            body=body,
            from_=settings.twilio_from_number,
            to=to_number,
        )
        logger.info("sms sent", to=to_number, sid=message.sid)
        return {"sent": True, "sid": message.sid}
    except TwilioRestException as e:
        logger.error("twilio sms failed", to=to_number, error=str(e))
        return {"sent": False, "error": str(e)}


# ── Email via SendGrid ────────────────────────────────────────────────────────

async def send_email(to_email: str, subject: str, html_body: str, plain_body: str = "") -> dict:
    """MCP tool: send a transactional email via SendGrid."""
    import sendgrid
    from sendgrid.helpers.mail import Mail
    from python_http_client.exceptions import HTTPError

    try:
        sg = sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        mail = Mail(
            from_email=settings.sendgrid_from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
            plain_text_content=plain_body or _strip_html(html_body),
        )
        response = sg.client.mail.send.post(request_body=mail.get())
        logger.info("email sent", to=to_email, status=response.status_code)
        return {"sent": True, "status_code": response.status_code}
    except HTTPError as e:
        logger.error("sendgrid email failed", to=to_email, error=str(e))
        return {"sent": False, "error": str(e)}


# ── Confirm link generation ───────────────────────────────────────────────────

async def gen_confirm_link(
    booking_id: str,
    user_id: str,
    route_id: str,
    price: str,
) -> dict:
    """
    MCP tool: generate a single-use HMAC-SHA256 confirm link for Mode A.
    Stores token hash in confirm_tokens table with 30-min expiry.
    Returns the full URL to include in SMS/email.
    """
    from ..shared.database import AsyncSessionLocal
    from ..booking.models import ConfirmToken

    raw_token = str(uuid.uuid4())
    token_hash = hmac.new(
        settings.jwt_secret.encode(),
        raw_token.encode(),
        hashlib.sha256,
    ).hexdigest()

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    async with AsyncSessionLocal() as db:
        confirm = ConfirmToken(
            id=str(uuid.uuid4()),
            booking_id=booking_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(confirm)
        await db.commit()

    confirm_url = f"https://app.flightai.io/confirm/{raw_token}"
    logger.info("confirm link generated", booking_id=booking_id, expires_at=expires_at.isoformat())
    return {
        "token": raw_token,
        "confirm_url": confirm_url,
        "expires_at": expires_at.isoformat(),
    }


# ── Pre-built notification templates ─────────────────────────────────────────

async def send_confirm_link(
    route_id: str,
    user_id: str,
    price: str,
    to_phone: str | None = None,
    to_email: str | None = None,
    booking_id: str = "",
    origin: str = "",
    destination: str = "",
    airline: str = "",
) -> dict:
    """
    Convenience wrapper: generate confirm link then send via SMS and/or email.
    Called by orchestrator for Mode A decisions.
    """
    link_result = await gen_confirm_link(
        booking_id=booking_id,
        user_id=user_id,
        route_id=route_id,
        price=price,
    )
    confirm_url = link_result["confirm_url"]

    results = {}

    if to_phone:
        sms_body = (
            f"✈️ FlightAI: {origin}→{destination} ${price} found via {airline}! "
            f"Tap to confirm (expires 30min): {confirm_url}"
        )
        results["sms"] = await send_sms(to_phone, sms_body)

    if to_email:
        html = _confirm_email_html(origin, destination, price, airline, confirm_url)
        results["email"] = await send_email(
            to_email=to_email,
            subject=f"✈️ FlightAI found a deal: {origin}→{destination} at ${price}",
            html_body=html,
        )

    return {"confirm_url": confirm_url, "expires_at": link_result["expires_at"], **results}


async def send_booking_confirmation(
    booking_id: str,
    user_id: str,
    route_id: str,
    price: str,
    airline: str,
    flight_number: str,
    to_phone: str | None = None,
    to_email: str | None = None,
    origin: str = "",
    destination: str = "",
) -> dict:
    """Send post-booking confirmation SMS and/or email (Mode B or after Mode A confirm)."""
    results = {}

    if to_phone:
        sms_body = (
            f"✅ FlightAI booked! {origin}→{destination} {airline}{flight_number} "
            f"at ${price}. Booking ID: {booking_id[:8].upper()}"
        )
        results["sms"] = await send_sms(to_phone, sms_body)

    if to_email:
        html = _booking_confirmation_html(booking_id, origin, destination, price, airline, flight_number)
        results["email"] = await send_email(
            to_email=to_email,
            subject=f"✅ FlightAI booking confirmed — {origin}→{destination}",
            html_body=html,
        )

    return results


# ── HTML templates ────────────────────────────────────────────────────────────

def _confirm_email_html(origin: str, destination: str, price: str, airline: str, confirm_url: str) -> str:
    return f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
      <h2>✈️ FlightAI found a deal!</h2>
      <p><strong>{origin} → {destination}</strong></p>
      <p>Price: <strong>${price}</strong> via {airline}</p>
      <p>This is below your target price. Click below to confirm your booking.</p>
      <a href="{confirm_url}"
         style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;
                border-radius:6px;text-decoration:none;font-weight:bold;margin:16px 0">
        Confirm Booking
      </a>
      <p style="color:#6b7280;font-size:12px">Link expires in 30 minutes. Do not share this link.</p>
    </body></html>
    """


def _booking_confirmation_html(
    booking_id: str, origin: str, destination: str, price: str, airline: str, flight_number: str
) -> str:
    return f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
      <h2>✅ Booking Confirmed!</h2>
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:8px;color:#6b7280">Route</td>
            <td style="padding:8px"><strong>{origin} → {destination}</strong></td></tr>
        <tr><td style="padding:8px;color:#6b7280">Flight</td>
            <td style="padding:8px">{airline} {flight_number}</td></tr>
        <tr><td style="padding:8px;color:#6b7280">Price</td>
            <td style="padding:8px"><strong>${price}</strong></td></tr>
        <tr><td style="padding:8px;color:#6b7280">Agent fee</td>
            <td style="padding:8px">$5.00</td></tr>
        <tr><td style="padding:8px;color:#6b7280">Booking ID</td>
            <td style="padding:8px">{booking_id[:8].upper()}</td></tr>
      </table>
      <p style="color:#6b7280;font-size:12px;margin-top:24px">
        Your PNR will appear in the FlightAI app. Thank you for using FlightAI!
      </p>
    </body></html>
    """


def _strip_html(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html).strip()
