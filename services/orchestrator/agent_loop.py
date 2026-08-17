"""
LangGraph-based Gemini orchestrator.
Subscribes to price.updated Pub/Sub events and runs the agent decision loop.
"""
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from google.cloud import pubsub_v1
from google.cloud import aiplatform
from langgraph.graph import StateGraph, END

from ..shared.database import AsyncSessionLocal
from ..shared.logging import logger
from ..shared.monitoring import emit_decision_metric
from ..shared.settings import settings


import os
MCP_PREDICTION_URL = os.getenv("MCP_PREDICTION_URL", "http://mcp-prediction") + "/tools"
MCP_BOOKING_URL = os.getenv("MCP_BOOKING_URL", "http://mcp-booking") + "/tools"
MCP_NOTIFIER_URL = os.getenv("MCP_NOTIFIER_URL", "http://mcp-notifier") + "/tools"

# ── Fare corpus for Vector Search ID → text lookup ────────────────────────────
_MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}
_MONTH_MULT = {
    1: 0.90, 2: 0.88, 3: 1.05, 4: 1.08, 5: 1.10, 6: 1.20,
    7: 1.22, 8: 1.18, 9: 0.95, 10: 1.00, 11: 1.15, 12: 1.25,
}
_ROUTE_PATTERNS = [
    ("JFK","LAX",280),("LAX","JFK",280),("ORD","LAX",240),("JFK","MIA",180),
    ("LAX","SFO",120),("ORD","DFW",160),("ATL","LAX",260),("JFK","ORD",170),
    ("DFW","LAX",220),("SEA","LAX",150),("BOS","LAX",290),("LAX","LAS",90),
    ("JFK","SFO",310),("ORD","MIA",200),("ATL","JFK",190),("DEN","LAX",180),
    ("PHX","LAX",110),("MIA","JFK",185),("SFO","SEA",130),("JFK","BOS",95),
]

def _build_fare_corpus() -> dict[str, str]:
    """Build {doc_id: text} map for Vector Search result lookup."""
    corpus: dict[str, str] = {}
    for origin, dest, baseline in _ROUTE_PATTERNS:
        annual = {m: round(baseline * mult, 0) for m, mult in _MONTH_MULT.items()}
        cheapest = min(annual, key=annual.get)
        priciest = max(annual, key=annual.get)
        corpus[f"{origin}-{dest}-annual"] = (
            f"Flight {origin} to {dest}: avg ${baseline}. "
            f"Cheapest: {_MONTH_NAMES[cheapest]} (~${annual[cheapest]:.0f}). "
            f"Most expensive: {_MONTH_NAMES[priciest]} (~${annual[priciest]:.0f}). "
            f"Book 30+ days ahead. Last-minute fares run 35–55% above average."
        )
        for m, price in annual.items():
            peak = "Peak season." if _MONTH_MULT[m] >= 1.15 else ("Off-peak." if _MONTH_MULT[m] <= 0.90 else "")
            corpus[f"{origin}-{dest}-{m:02d}"] = (
                f"Flight {origin} to {dest} in {_MONTH_NAMES[m]}: ~${price:.0f}. {peak}"
            )
    return corpus

_FARE_CORPUS: dict[str, str] = _build_fare_corpus()

_VS_ENDPOINT_NAME = "flightai-fare-rag-endpoint"
_VS_DEPLOYED_INDEX_ID = "flightai_fare_rag_index"


async def _fetch_rag_context(origin: str, destination: str, month: int) -> str:
    """Query Vector Search for historical fare context. Returns "" on any failure."""
    try:
        import asyncio
        import vertexai
        from vertexai.language_models import TextEmbeddingModel

        query = (
            f"Typical fare for flight {origin} to {destination} "
            f"in {_MONTH_NAMES.get(month, 'any month')}"
        )

        loop = asyncio.get_running_loop()

        def _query_sync() -> list[dict]:
            vertexai.init(project=settings.gcp_project_id, location=settings.vertex_location)
            aiplatform.init(project=settings.gcp_project_id, location=settings.vertex_location)

            embed_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
            [embedding] = embed_model.get_embeddings([query])

            endpoints = [
                ep for ep in aiplatform.MatchingEngineIndexEndpoint.list()
                if ep.display_name == _VS_ENDPOINT_NAME
            ]
            if not endpoints:
                return []

            results = endpoints[0].find_neighbors(
                deployed_index_id=_VS_DEPLOYED_INDEX_ID,
                queries=[embedding.values],
                num_neighbors=3,
            )
            return [{"id": m.id, "distance": m.distance} for m in results[0]]

        matches = await asyncio.wait_for(
            loop.run_in_executor(None, _query_sync),
            timeout=8.0,
        )

        if not matches:
            return ""

        snippets = [_FARE_CORPUS[m["id"]] for m in matches if m["id"] in _FARE_CORPUS]
        if not snippets:
            return ""

        return "Historical fare context:\n" + "\n".join(f"- {s}" for s in snippets)
    except BaseException as e:
        # Catch CancelledError (BaseException in Python 3.12) to prevent thread leaks
        logger.debug("rag context fetch skipped", error=repr(e))
        return ""


class AgentState(dict):
    """State passed between LangGraph nodes."""
    route_id: str
    user_id: str
    origin: str
    destination: str
    current_price: float
    target_price: float
    booking_mode: str
    airline: str
    flight_number: str
    departure_date: str | None
    # user contact — loaded at start of run
    user_phone: str | None
    user_email: str | None
    user_first_name: str | None
    # filled in after booking
    booking_id: str | None
    prediction: dict | None
    confidence: dict | None
    rag_context: str  # historical fare context from Vector Search
    decision: str  # buy | wait | booked | book_failed | error
    reasoning: str
    ml_score: float
    gemini_trace_id: str | None


async def fetch_price_node(state: AgentState) -> AgentState:
    """Node 1: price already fetched from snapshot — just pass through."""
    logger.info("agent: fetch_price", route_id=state["route_id"], price=state["current_price"])
    return state


async def predict_node(state: AgentState) -> AgentState:
    """Node 2: call Prediction MCP to get ML score; fetch RAG context in parallel via background task."""
    import asyncio
    from datetime import date, timedelta
    departure_date = state.get("departure_date") or (date.today() + timedelta(days=30)).isoformat()
    departure_month = int(departure_date[5:7]) if departure_date else date.today().month

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MCP_PREDICTION_URL}/predict_price",
                json={
                    "origin": state["origin"],
                    "destination": state["destination"],
                    "departure_date": departure_date,
                    "current_price": state["current_price"],
                    "route_historical_avg": state["target_price"],
                },
                timeout=_MCP_TIMEOUT,
            )
            resp.raise_for_status()
            state["prediction"] = resp.json()

        confidence_resp = await _call_mcp(
            f"{MCP_PREDICTION_URL}/score_confidence",
            {
                "current_price": state["current_price"],
                "predicted_price": state["prediction"]["predicted_price"],
                "target_price": state["target_price"],
            },
        )
        state["confidence"] = confidence_resp
        state["ml_score"] = state["prediction"]["confidence_pct"]
    except Exception as e:
        logger.warning("predict_node failed, using defaults", error=repr(e))
        state["prediction"] = {"predicted_price": state["target_price"], "direction": "stable", "confidence_pct": 50.0, "signal": "wait"}
        state["confidence"] = {"recommendation": "wait", "confidence_pct": 50.0, "reasoning": "ML unavailable."}
        state["ml_score"] = 50.0

    # RAG context — sequential after ML, capped at 5s so it never blocks the agent
    try:
        state["rag_context"] = await asyncio.wait_for(
            _fetch_rag_context(state["origin"], state["destination"], departure_month),
            timeout=5.0,
        )
    except BaseException:
        state["rag_context"] = ""

    return state


async def decide_node(state: AgentState) -> AgentState:
    """Node 3: call Gemini Flash to reason over price + prediction data."""
    try:
        prompt = _build_gemini_prompt(state)
        gemini_response = await _call_gemini(prompt)
        state["decision"] = gemini_response.get("action", "wait")
        state["reasoning"] = gemini_response.get("reasoning", "Gemini decision.")
        state["gemini_trace_id"] = gemini_response.get("trace_id")
    except Exception as e:
        logger.warning("gemini call failed, using rule-based fallback", error=str(e))
        below_target = state["current_price"] <= state["target_price"]
        ml_says_buy = (state.get("prediction") or {}).get("signal") == "buy"
        confidence_says_buy = (state.get("confidence") or {}).get("recommendation") == "buy"
        state["decision"] = "buy" if (below_target and (ml_says_buy or confidence_says_buy)) else "wait"
        state["reasoning"] = (
            f"Rule-based: price {'below' if below_target else 'above'} target. "
            f"ML signal: {(state.get('prediction') or {}).get('signal','unknown')}. "
            f"Confidence: {(state.get('confidence') or {}).get('recommendation','unknown')}. "
            "Gemini unavailable."
        )
        state["gemini_trace_id"] = str(uuid.uuid4())
    return state


async def book_node(state: AgentState) -> AgentState:
    """Node 4 (Mode B): auto-book via Booking MCP. MCP handles Amadeus search + order internally."""
    try:
        resp = await _call_mcp(
            f"{MCP_BOOKING_URL}/create_order",
            {
                "route_id": state["route_id"],
                "user_id": state["user_id"],
            },
        )
        if resp.get("success"):
            state["decision"] = "booked"
            state["booking_id"] = resp.get("booking_id")
            state["airline"] = resp.get("airline", state.get("airline", ""))
            state["flight_number"] = resp.get("flight_number", state.get("flight_number", ""))
        else:
            state["decision"] = "book_failed"
    except Exception as e:
        logger.warning("book_node failed, marking as book_failed", error=str(e))
        state["decision"] = "book_failed"
    return state


async def notify_node(state: AgentState) -> AgentState:
    """Node 5: send push notification for deal found (Mode A) or booking confirmed."""
    try:
        if state["decision"] == "buy":
            price = state["current_price"]
            origin = state["origin"]
            destination = state["destination"]
            booking_id = state.get("booking_id", "")
            await _call_mcp(
                f"{MCP_NOTIFIER_URL}/send_web_push",
                {
                    "user_id": state["user_id"],
                    "title": f"Deal found: {origin} → {destination}",
                    "body": f"${price:.0f} — tap to pay with Apple Pay and lock this price",
                    "data": {
                        "booking_id": booking_id,
                        "route_id": state["route_id"],
                        "price": str(price),
                    },
                },
            )
        elif state["decision"] == "booked":
            await _call_mcp(
                f"{MCP_NOTIFIER_URL}/send_web_push",
                {
                    "user_id": state["user_id"],
                    "title": "Booking confirmed!",
                    "body": f"{state['origin']} → {state['destination']} booked at ${state['current_price']:.0f}",
                    "data": {"booking_id": state.get("booking_id", ""), "route_id": state["route_id"]},
                },
            )
            await _call_mcp(
                f"{MCP_NOTIFIER_URL}/send_booking_confirmation",
                {
                    "booking_id": state.get("booking_id", ""),
                    "user_id": state["user_id"],
                    "route_id": state["route_id"],
                    "price": str(state["current_price"]),
                    "airline": state.get("airline", ""),
                    "flight_number": state.get("flight_number", ""),
                    "origin": state["origin"],
                    "destination": state["destination"],
                    "to_phone": state.get("user_phone"),
                    "to_email": state.get("user_email"),
                },
            )
    except Exception as e:
        logger.warning("notify_node failed, continuing to log", error=str(e))
    return state


async def log_decision_node(state: AgentState) -> AgentState:
    """Node 6: always write to agent_logs table."""
    async with AsyncSessionLocal() as db:
        from .models import AgentLog
        log = AgentLog(
            id=str(uuid.uuid4()),
            route_id=state["route_id"],
            user_id=state["user_id"],
            action=state["decision"],
            ml_score=state.get("ml_score", 0.0),
            gemini_trace_id=state.get("gemini_trace_id"),
            reasoning=state.get("reasoning", ""),
            created_at=datetime.now(timezone.utc),
        )
        db.add(log)
        await db.commit()
    logger.info("agent decision logged", route_id=state["route_id"], action=state["decision"])

    emit_decision_metric(
        action=state["decision"],
        ml_score=state.get("ml_score", 0.0),
        route_id=state["route_id"],
        user_id=state.get("user_id"),
        booking_mode=state.get("booking_mode"),
    )
    return state


def route_after_decide(state: AgentState) -> str:
    if state["decision"] == "buy" and state["booking_mode"] == "B":
        return "book"
    if state["decision"] == "buy" and state["booking_mode"] == "A":
        return "notify"
    return "log"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("fetch_price", fetch_price_node)
    graph.add_node("predict", predict_node)
    graph.add_node("decide", decide_node)
    graph.add_node("book", book_node)
    graph.add_node("notify", notify_node)
    graph.add_node("log", log_decision_node)

    graph.set_entry_point("fetch_price")
    graph.add_edge("fetch_price", "predict")
    graph.add_edge("predict", "decide")
    graph.add_conditional_edges("decide", route_after_decide, {"book": "book", "notify": "notify", "log": "log"})
    graph.add_edge("book", "notify")
    graph.add_edge("notify", "log")
    graph.add_edge("log", END)
    return graph.compile()


agent_graph = build_graph()


def _build_gemini_prompt(state: AgentState) -> str:
    rag_section = ""
    if state.get("rag_context"):
        rag_section = f"\n{state['rag_context']}\n"
    return f"""You are FlightAI, an autonomous flight booking agent.

Route: {state["origin"]} → {state["destination"]}
Current Price: ${state["current_price"]:.2f}
Target Price: ${state["target_price"]:.2f}
ML Prediction: ${state["prediction"]["predicted_price"]:.2f} (direction: {state["prediction"]["direction"]})
ML Signal: {state["prediction"]["signal"]} (confidence: {state["prediction"]["confidence_pct"]}%)
Confidence Score: {state["confidence"]["recommendation"]} — {state["confidence"]["reasoning"]}
Booking Mode: {"Alert + Confirm" if state["booking_mode"] == "A" else "Fully Autonomous"}{rag_section}
Based on this data, decide: should we BUY now or WAIT?

Respond in JSON:
{{"action": "buy" or "wait", "reasoning": "one sentence explaining the decision"}}
"""


async def _call_gemini(prompt: str) -> dict:
    import asyncio
    import re
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from opentelemetry import trace as otel_trace

    vertexai.init(project=settings.gcp_project_id, location=settings.vertex_location)
    model = GenerativeModel("gemini-2.5-flash")

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))

    # Capture the current OTel trace ID as the Gemini trace ID for observability
    span = otel_trace.get_current_span()
    ctx = span.get_span_context()
    gemini_trace_id = format(ctx.trace_id, '032x') if ctx and ctx.trace_id else str(uuid.uuid4())

    text = response.text.strip()
    # Remove think blocks before JSON extraction (Gemini 2.5 uses thinking mode)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if json_match:
        result = json.loads(json_match.group())
        result["trace_id"] = gemini_trace_id
        return result
    return {"action": "wait", "reasoning": "Gemini response unparseable, defaulting to wait.", "trace_id": gemini_trace_id}


_MCP_TIMEOUT = httpx.Timeout(connect=30.0, read=15.0, write=10.0, pool=5.0)


async def _call_mcp(url: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=_MCP_TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
