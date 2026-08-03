from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from ..shared.logging import logger
from .model_loader import load_model


def _build_features(
    origin: str,
    destination: str,
    departure_date: date,
    current_price: float,
    route_avg: float,
) -> np.ndarray:
    today = date.today()
    days_out = (departure_date - today).days
    price_ratio = current_price / max(route_avg, 1.0)
    return np.array([[
        days_out,
        departure_date.weekday(),
        departure_date.month,
        route_avg,      # historical_avg — feature 4 as trained
        price_ratio,    # current_price / historical_avg — feature 5 as trained
    ]])


def predict_price(
    origin: str,
    destination: str,
    departure_date: date,
    current_price: float,
    route_historical_avg: float,
) -> dict:
    """MCP tool: predict fare price and return buy/wait signal."""
    model = load_model()
    features = _build_features(origin, destination, departure_date, current_price, route_historical_avg)
    predicted_price = float(model.predict(features)[0])
    direction = "down" if predicted_price < current_price else "up"
    confidence = min(abs(current_price - predicted_price) / max(current_price, 1) * 100, 99.0)

    logger.info(
        "price predicted",
        origin=origin,
        destination=destination,
        current=current_price,
        predicted=predicted_price,
        confidence=confidence,
    )
    return {
        "predicted_price": round(predicted_price, 2),
        "current_price": current_price,
        "direction": direction,
        "confidence_pct": round(confidence, 1),
        "signal": "buy" if predicted_price > current_price else "wait",
    }


def get_best_window(
    origin: str,
    destination: str,
    date_from: date,
    date_to: date,
    route_historical_avg: float,
) -> dict:
    """MCP tool: scan date range, return date with lowest predicted fare."""
    model = load_model()
    best_date = date_from
    best_price = float("inf")
    current = date_from

    while current <= date_to:
        features = _build_features(origin, destination, current, route_historical_avg, route_historical_avg)
        predicted = float(model.predict(features)[0])
        if predicted < best_price:
            best_price = predicted
            best_date = current
        current += timedelta(days=1)

    return {
        "best_departure_date": best_date.isoformat(),
        "predicted_price": round(best_price, 2),
    }


def score_confidence(current_price: float, predicted_price: float, target_price: float) -> dict:
    """MCP tool: return buy/wait recommendation with reasoning."""
    below_target = current_price <= target_price
    below_predicted = current_price <= predicted_price
    savings_vs_target = target_price - current_price
    savings_vs_predicted = predicted_price - current_price

    if below_target and below_predicted:
        recommendation = "buy"
        reasoning = f"Price ${current_price:.2f} is ${savings_vs_target:.2f} below target and ${savings_vs_predicted:.2f} below predicted future price."
        confidence = 90.0
    elif below_target and not below_predicted:
        recommendation = "buy"
        reasoning = f"Price ${current_price:.2f} meets target. Expected to rise to ${predicted_price:.2f}."
        confidence = 75.0
    elif not below_target and below_predicted:
        recommendation = "wait"
        reasoning = f"Price ${current_price:.2f} is above target ${target_price:.2f} and expected to rise to ${predicted_price:.2f}."
        confidence = 60.0
    else:
        recommendation = "wait"
        reasoning = f"Price ${current_price:.2f} is above target ${target_price:.2f} and expected to remain high."
        confidence = 80.0

    return {"recommendation": recommendation, "confidence_pct": confidence, "reasoning": reasoning}
