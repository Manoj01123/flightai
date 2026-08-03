"""
XGBoost v0 training script.
Trains on synthetic/real fare data, evaluates on holdout, uploads pkl to GCS.

Usage:
    python -m ml.training.train_xgboost
    python -m ml.training.train_xgboost --data ml/data/fare_training_data.csv --version v1
"""
import argparse
import io
import json
import pickle
import sys
import os
from datetime import date

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

GCS_BUCKET = "flightai-models"
GCS_MODEL_PREFIX = "models"


def build_features(df: pd.DataFrame) -> np.ndarray:
    return np.column_stack([
        df["days_to_departure"].values,
        df["day_of_week"].values,
        df["month"].values,
        df["historical_avg"].values,
        (df["historical_avg"].values > 0) * df["price"].values / np.maximum(df["historical_avg"].values, 1),
    ])


def train(data_path: str, version: str = "v0") -> dict:
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    print(f"  {len(df)} rows, {df['origin'].nunique()} routes")

    X = build_features(df)
    y = df["price"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"  Train: {len(X_train)}  Test: {len(X_test)}")

    model = XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred) ** 0.5
    print(f"\nEvaluation — MAE: ${mae:.2f}  RMSE: ${rmse:.2f}")

    # Feature importance
    feature_names = ["days_to_departure", "day_of_week", "month", "historical_avg", "price_ratio"]
    importances = dict(zip(feature_names, model.feature_importances_.tolist()))
    print(f"Feature importances: {importances}")

    metrics = {"version": version, "mae": round(mae, 2), "rmse": round(rmse, 2),
               "train_samples": len(X_train), "test_samples": len(X_test),
               "feature_importances": importances}

    _upload_model_to_gcs(model, version)
    _save_metrics_to_bq(metrics)

    return metrics


def _upload_model_to_gcs(model, version: str):
    from google.cloud import storage
    gcs_path = f"{GCS_MODEL_PREFIX}/xgboost_{version}.pkl"
    print(f"\nUploading model to gs://{GCS_BUCKET}/{gcs_path}...")
    buf = io.BytesIO()
    pickle.dump(model, buf)
    buf.seek(0)
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(gcs_path)
    blob.upload_from_file(buf, content_type="application/octet-stream")

    # Also write as the canonical "latest" path the prediction service reads
    latest_blob = bucket.blob(f"{GCS_MODEL_PREFIX}/xgboost_{version}_latest.pkl")
    latest_blob.rewrite(blob)
    print(f"Uploaded → gs://{GCS_BUCKET}/{gcs_path}")


def _save_metrics_to_bq(metrics: dict):
    try:
        from google.cloud import bigquery
        client = bigquery.Client()
        table_id = "flightai-dev.flightai.model_accuracy"
        rows = [{
            "model_version": metrics["version"],
            "evaluation_date": date.today().isoformat(),
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "sample_count": metrics["train_samples"] + metrics["test_samples"],
            "route_count": 20,
        }]
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            print(f"BigQuery insert warnings: {errors}")
        else:
            print(f"Metrics saved to BigQuery: MAE=${metrics['mae']}")
    except Exception as e:
        print(f"BigQuery save skipped: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="ml/data/fare_training_data.csv")
    parser.add_argument("--version", default="v0")
    args = parser.parse_args()

    if not os.path.exists(args.data):
        print(f"Data file not found: {args.data}")
        print("Generating synthetic data first...")
        sys.path.insert(0, os.getcwd())
        from ml.data.generate_synthetic_data import generate_dataset
        generate_dataset(args.data)

    metrics = train(args.data, args.version)
    print(f"\nDone! Model xgboost_{args.version} trained and uploaded.")
    print(json.dumps(metrics, indent=2))
