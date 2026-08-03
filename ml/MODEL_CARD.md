# FlightAI XGBoost Price Prediction Model Card

## Model Overview

| Field | Value |
|---|---|
| **Model name** | XGBoost Fare Price Regressor |
| **Version** | v0 |
| **Training date** | 2026-07-15 |
| **Model path** | `gs://flightai-models/models/xgboost_v0.pkl` |
| **Algorithm** | XGBoost Regression (gradient-boosted trees) |
| **Task** | Predict domestic US flight fare price (USD) given route + time features |

## Intended Use

This model powers the FlightAI autonomous booking agent. It runs inside the `mcp-prediction` microservice and produces:
- **`predict_price`** — predicted fare in USD
- **`score_confidence`** — buy/wait recommendation with confidence percentage
- **`get_best_window`** — best booking date within a 30-day horizon

The model is **not** intended for financial advice, international routes, or business/first class prediction.

## Training Data

| Source | Description |
|---|---|
| **Primary** | BTS DB1B Market dataset (US DOT) — 10% sample of all US domestic tickets, 2015–2024 |
| **Fallback** | 10,000-row synthetic dataset (used for v0 initial training) |
| **Routes covered** | 20 high-volume US domestic routes (JFK↔LAX, ORD↔LAX, etc.) |
| **Date range** | Q1 2015 — Q4 2024 (40 quarters) |

## Features

| Feature | Description | Importance |
|---|---|---|
| `historical_avg` | Route's average fare across all training data | **74.2%** |
| `price_ratio` | Current price ÷ historical_avg | **17.6%** |
| `day_of_week` | Day of week of departure (0=Mon, 6=Sun) | 3.3% |
| `days_to_departure` | Days between fetch date and departure | 3.1% |
| `month` | Month of departure (1–12) | 1.8% |

## Performance (v0 — synthetic data)

| Metric | Value |
|---|---|
| **MAE** | $1.68 |
| **RMSE** | $3.01 |
| **Test set size** | 2,000 samples (20% holdout) |
| **Training set size** | 8,000 samples |

> After retraining on real BTS data (v1+), we expect MAE to increase slightly (~$15–25) due to real-world noise, but predictions will be far more authentic.

## Limitations

- **US domestic only** — model has no knowledge of international fares
- **Economy class only** — not trained on business/first class data
- **Quarterly granularity** — BTS data is quarterly; day-level price variation (Tue vs Fri) is approximated
- **No carrier-specific features** — doesn't model airline-specific pricing strategies (low-cost vs legacy)
- **No demand signal** — does not account for seat availability or load factor

## Monitoring

- MAE/RMSE tracked in BigQuery: `flightai-dev.flightai.model_accuracy`
- Monthly retraining via Vertex AI: `ml/training/retrain_job.py`
- Cloud Monitoring dashboard: `custom.googleapis.com/flightai/ml_score`

## Retraining Schedule

Retrained monthly on the 1st via Vertex AI CustomJob. Each new version is uploaded to:
- `gs://flightai-models/models/xgboost_v{YYYYMM}.pkl`
- `gs://flightai-models/models/xgboost_v{YYYYMM}_latest.pkl`

The `mcp-prediction` service loads the model specified by `XGBOOST_MODEL_PATH` env var.
