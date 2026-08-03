from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel

from ..shared.logging import configure_logging, logger
from ..shared.settings import settings
from .tools import predict_price, get_best_window, score_confidence


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("mcp-prediction", settings.environment)
    logger.info("mcp-prediction starting")
    # Pre-load model on startup so first request isn't slow
    try:
        from .model_loader import load_model
        load_model()
    except Exception as e:
        logger.warning("model pre-load failed (may be ok in dev)", error=str(e))
    yield
    logger.info("mcp-prediction stopped")


app = FastAPI(title="FlightAI Prediction MCP Server", version="1.0.0", lifespan=lifespan)


class PredictRequest(BaseModel):
    origin: str
    destination: str
    departure_date: date
    current_price: float
    route_historical_avg: float


class BestWindowRequest(BaseModel):
    origin: str
    destination: str
    date_from: date
    date_to: date
    route_historical_avg: float


class ConfidenceRequest(BaseModel):
    current_price: float
    predicted_price: float
    target_price: float


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp-prediction"}


@app.post("/tools/predict_price")
async def tool_predict_price(req: PredictRequest):
    return predict_price(
        req.origin, req.destination, req.departure_date,
        req.current_price, req.route_historical_avg
    )


@app.post("/tools/get_best_window")
async def tool_best_window(req: BestWindowRequest):
    return get_best_window(
        req.origin, req.destination, req.date_from, req.date_to, req.route_historical_avg
    )


@app.post("/tools/score_confidence")
async def tool_score_confidence(req: ConfidenceRequest):
    return score_confidence(req.current_price, req.predicted_price, req.target_price)


# MCP tool registry — consumed by the orchestrator
@app.get("/mcp/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "predict_price", "description": "Predict fare price and return buy/wait signal"},
            {"name": "get_best_window", "description": "Return the best departure date in a range"},
            {"name": "score_confidence", "description": "Score buy/wait confidence and generate reasoning"},
        ]
    }
