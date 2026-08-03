"""
Cloud Monitoring custom metrics for FlightAI agent decisions.

Emits the following custom metrics to Google Cloud Monitoring:
  custom.googleapis.com/flightai/agent_decision  (counter, label: action)
  custom.googleapis.com/flightai/ml_score        (gauge)
  custom.googleapis.com/flightai/booking_price   (gauge, USD)
  custom.googleapis.com/flightai/wallet_balance  (gauge, USD, per user)

Usage (from agent_loop.py log_decision_node):
    from ..shared.monitoring import emit_decision_metric
    emit_decision_metric(action="buy", ml_score=87.3, route_id="...")

The emit is fire-and-forget in a background thread so it never blocks the agent loop.
"""
import threading
from datetime import datetime, timezone
from typing import Optional

from .logging import logger
from .settings import settings

_METRIC_PREFIX = "custom.googleapis.com/flightai"


def _build_time_series(metric_type: str, value, labels: dict, is_gauge: bool = True):
    try:
        from google.cloud import monitoring_v3
    except ImportError:
        return  # google-cloud-monitoring not installed; skip silently

    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{settings.gcp_project_id}"

    series = monitoring_v3.TimeSeries()
    series.metric.type = f"{_METRIC_PREFIX}/{metric_type}"
    for k, v in labels.items():
        series.metric.labels[k] = str(v)

    series.resource.type = "global"

    now = datetime.now(timezone.utc)
    seconds = int(now.timestamp())

    point = monitoring_v3.Point()
    interval = monitoring_v3.TimeInterval(
        end_time={"seconds": seconds, "nanos": 0}
    )
    if not is_gauge:
        interval.start_time = {"seconds": seconds - 1, "nanos": 0}
    point.interval = interval

    if isinstance(value, float):
        point.value.double_value = value
    elif isinstance(value, int):
        point.value.int64_value = value
    else:
        point.value.double_value = float(value)

    series.points = [point]

    client.create_time_series(name=project_name, time_series=[series])


def _safe_emit(metric_type: str, value, labels: dict, is_gauge: bool = True):
    """Emit in a background daemon thread — never raises."""
    def _run():
        try:
            _build_time_series(metric_type, value, labels, is_gauge)
        except Exception as e:
            logger.warning("monitoring emit failed", metric=metric_type, error=str(e))

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def emit_decision_metric(
    action: str,
    ml_score: float,
    route_id: str,
    user_id: Optional[str] = None,
    booking_mode: Optional[str] = None,
):
    """Emit agent_decision counter + ml_score gauge after each agent run."""
    labels = {
        "action": action,
        "booking_mode": booking_mode or "unknown",
    }
    _safe_emit("agent_decision", 1, labels, is_gauge=False)
    _safe_emit("ml_score", ml_score, {"action": action})


def emit_booking_price_metric(price: float, origin: str, destination: str):
    """Emit booking price whenever a flight is booked."""
    labels = {"origin": origin, "destination": destination}
    _safe_emit("booking_price", price, labels)


def emit_wallet_balance_metric(user_id: str, balance: float):
    """Emit wallet balance after each debit/top-up."""
    _safe_emit("wallet_balance", balance, {"user_id": user_id})
