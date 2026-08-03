import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from google.cloud import pubsub_v1
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from ..shared.logging import configure_logging, logger
from ..shared.settings import settings
from .agent_loop import agent_graph


def _setup_tracing():
    exporter = CloudTraceSpanExporter(project_id=settings.gcp_project_id)
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()


tracer = trace.get_tracer("flightai.orchestrator")


def _require_admin_key(x_admin_key: str | None = Header(default=None)):
    """Dependency: validates X-Admin-Key header against settings.admin_api_key."""
    configured = settings.admin_api_key
    if not configured:
        raise HTTPException(status_code=503, detail="Admin API key not configured on this service")
    if x_admin_key != configured:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Key header")


def _log_viewer_user_id(
    x_admin_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> str | None:
    """
    Returns None if the X-Admin-Key is valid (caller sees all logs).
    Returns a user_id string if a valid JWT Bearer token is present (caller sees only their logs).
    Raises 403 if neither credential is valid.
    """
    configured = settings.admin_api_key
    if configured and x_admin_key == configured:
        return None  # admin — unrestricted

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            from jose import JWTError, jwt as jose_jwt
            payload = jose_jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id: str | None = payload.get("sub")
            if user_id:
                return user_id
        except Exception:
            pass

    raise HTTPException(status_code=403, detail="Valid X-Admin-Key or Bearer token required")

_loop: asyncio.AbstractEventLoop | None = None


def _handle_pubsub_message(message: pubsub_v1.subscriber.message.Message):
    try:
        data = json.loads(message.data.decode())
        logger.info("received price.updated event", route_id=data.get("route_id"))
        if _loop is not None:
            asyncio.run_coroutine_threadsafe(_run_agent(data), _loop)
        message.ack()
    except Exception as e:
        logger.error("pubsub message handling failed", error=str(e))
        message.nack()


async def _run_agent(event: dict):
    try:
        await _run_agent_inner(event)
    except Exception as e:
        logger.error("agent run failed", route_id=event.get("route_id"), error=str(e), exc_info=True)


_agent_semaphore: asyncio.Semaphore | None = None


async def _run_agent_inner(event: dict):
    global _agent_semaphore
    if _agent_semaphore is None:
        _agent_semaphore = asyncio.Semaphore(3)

    async with _agent_semaphore:
        await _run_agent_body(event)


async def _run_agent_body(event: dict):
    from sqlalchemy import select
    from ..shared.database import AsyncSessionLocal
    from ..user.models import User

    user_phone = None
    user_email = None
    user_first_name = None

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == event["user_id"]))
            user = result.scalar_one_or_none()
            if user:
                user_phone = user.phone if user.sms_notifications else None
                user_email = user.email if user.email_notifications else None
                user_first_name = user.first_name
    except Exception as e:
        logger.warning("user lookup failed, continuing without user info", error=str(e))

    state = {
        "route_id": event["route_id"],
        "user_id": event["user_id"],
        "origin": event["origin"],
        "destination": event["destination"],
        "current_price": float(event["price"]),
        "target_price": float(event["target_price"]),
        "booking_mode": event["booking_mode"],
        "airline": event.get("airline", ""),
        "flight_number": event.get("flight_number", ""),
        "departure_date": event.get("departure_date"),
        "user_phone": user_phone,
        "user_email": user_email,
        "user_first_name": user_first_name,
        "booking_id": None,
        "prediction": None,
        "confidence": None,
        "rag_context": "",
        "decision": "wait",
        "reasoning": "",
        "ml_score": 0.0,
        "gemini_trace_id": None,
    }
    with tracer.start_as_current_span(
        "agent.run",
        attributes={
            "route_id": event["route_id"],
            "user_id": event["user_id"],
            "origin": event["origin"],
            "destination": event["destination"],
            "booking_mode": event["booking_mode"],
        },
    ):
        await agent_graph.ainvoke(state)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop
    configure_logging("orchestrator", settings.environment)
    _setup_tracing()
    _loop = asyncio.get_running_loop()
    logger.info("orchestrator starting")

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(
        settings.gcp_project_id,
        f"{settings.pubsub_topic_price_updated}-orchestrator-sub",
    )
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=_handle_pubsub_message)
    logger.info("subscribed to Pub/Sub", subscription=subscription_path)

    yield

    streaming_pull_future.cancel()
    streaming_pull_future.result(timeout=5)
    logger.info("orchestrator stopped")


app = FastAPI(title="FlightAI Orchestrator", version="1.0.0", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "orchestrator"}


@app.post("/v1/admin/bq-export")
async def bq_export(_=Depends(_require_admin_key)):
    """Export recent agent_logs to BigQuery. Called by Cloud Scheduler daily."""
    from datetime import timedelta
    from sqlalchemy import select
    from ..shared.database import AsyncSessionLocal
    from .models import AgentLog
    from google.cloud import bigquery

    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentLog).where(AgentLog.created_at >= cutoff).order_by(AgentLog.created_at)
        )
        logs = result.scalars().all()

    if not logs:
        return {"exported": 0}

    bq = bigquery.Client(project=settings.gcp_project_id)
    rows = [
        {
            "id": l.id,
            "route_id": l.route_id,
            "user_id": l.user_id,
            "action": l.action,
            "ml_score": float(l.ml_score or 0),
            "gemini_trace_id": l.gemini_trace_id or "",
            "reasoning": l.reasoning or "",
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
    errors = bq.insert_rows_json(f"{settings.gcp_project_id}.flightai.agent_logs_export", rows)
    if errors:
        logger.warning("bq export partial errors", errors=str(errors[:2]))
    logger.info("bq export complete", rows=len(rows))
    return {"exported": len(rows)}


@app.get("/v1/agent/logs")
async def list_agent_logs(
    route_id: str | None = None,
    limit: int = 50,
    viewer_user_id: str | None = Depends(_log_viewer_user_id),
):
    from sqlalchemy import select
    from ..shared.database import AsyncSessionLocal
    from .models import AgentLog

    async with AsyncSessionLocal() as db:
        query = select(AgentLog).order_by(AgentLog.created_at.desc()).limit(limit)
        if viewer_user_id:  # JWT caller — filter to their own logs
            query = query.where(AgentLog.user_id == viewer_user_id)
        if route_id:
            query = query.where(AgentLog.route_id == route_id)
        result = await db.execute(query)
        logs = result.scalars().all()
        return [
            {
                "id": l.id,
                "route_id": l.route_id,
                "user_id": l.user_id,
                "action": l.action,
                "ml_score": l.ml_score,
                "reasoning": l.reasoning,
                "gemini_trace_id": l.gemini_trace_id,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ]
