"""
Download BTS DB1B Market data (US DOT — free, authoritative).

Source: Bureau of Transportation Statistics
        Origin and Destination Survey (DB1B) — Market table
        10% sample of all US domestic airline tickets
        Quarterly data from 1993 to present.

Downloads 10 years (2015–2024), 40 quarterly zips.
Filters to one-way direct fares on our 20 target routes.
Outputs a unified CSV compatible with train_xgboost.py.
Also uploads directly to BigQuery fare_data table.

Usage:
    python -m ml.data.download_bts_data                         # full 10yr download
    python -m ml.data.download_bts_data --years 2023 2024       # quick test (2 years)
    python -m ml.data.download_bts_data --skip-bq               # CSV only, skip BigQuery
"""
from __future__ import annotations

import argparse
import io
import os
import zipfile
import urllib.request
import csv
from pathlib import Path
from datetime import date
from typing import Optional

import pandas as pd
from google.cloud import bigquery

# ── Config ────────────────────────────────────────────────────────────────────

BTS_URL = "https://transtats.bts.gov/PREZIP/Origin_and_Destination_Survey_DB1BMarket_{year}_{quarter}.zip"

TARGET_ROUTES = {
    ("JFK", "LAX"), ("LAX", "JFK"), ("ORD", "LAX"), ("JFK", "MIA"),
    ("LAX", "SFO"), ("ORD", "DFW"), ("ATL", "LAX"), ("JFK", "ORD"),
    ("DFW", "LAX"), ("SEA", "LAX"), ("BOS", "LAX"), ("LAX", "LAS"),
    ("JFK", "SFO"), ("ORD", "MIA"), ("ATL", "JFK"), ("DEN", "LAX"),
    ("PHX", "LAX"), ("MIA", "JFK"), ("SFO", "SEA"), ("JFK", "BOS"),
}

OUTPUT_PATH = "ml/data/fare_training_data.csv"
CACHE_DIR = Path("ml/data/bts_cache")
BQ_PROJECT = "flightai-dev"
BQ_TABLE = f"{BQ_PROJECT}.flightai.fare_data"

# Quarter → approximate month (mid-quarter)
QUARTER_MONTH = {1: 2, 2: 5, 3: 8, 4: 11}

# BTS DB1B Market columns we care about
COLS_NEEDED = [
    "Year", "Quarter", "Origin", "Dest",
    "AirCarrier", "Passengers", "MktFare",
    "MktMilesFlown", "NumTicketsOrdered",
]

# Minimum sensible fare (removes $0 / employee / award tickets)
MIN_FARE = 49.0
MAX_FARE = 3000.0


# ── Download helpers ───────────────────────────────────────────────────────────

def download_quarter(year: int, quarter: int) -> Optional[pd.DataFrame]:
    url = BTS_URL.format(year=year, quarter=quarter)
    cache_path = CACHE_DIR / f"bts_{year}_{quarter}.parquet"

    if cache_path.exists():
        print(f"  Cache hit: {cache_path.name}")
        return pd.read_parquet(cache_path)

    print(f"  Downloading {year} Q{quarter}…", end=" ", flush=True)
    try:
        resp = urllib.request.urlopen(url, timeout=120)
        data = resp.read()
        print(f"{len(data) // 1024 // 1024}MB", end=" ")
    except Exception as e:
        print(f"FAILED: {e}")
        return None

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        csv_name = next((n for n in zf.namelist() if n.endswith(".csv")), None)
        if not csv_name:
            print("no CSV in zip")
            return None
        with zf.open(csv_name) as f:
            # Read only needed columns — BTS files are large
            try:
                df = pd.read_csv(f, usecols=lambda c: c in COLS_NEEDED, low_memory=False)
            except Exception as e:
                print(f"CSV parse error: {e}")
                return None

    # Filter to target routes only
    df = df[
        df[["Origin", "Dest"]].apply(tuple, axis=1).isin(TARGET_ROUTES)
    ]

    # Keep only sane fares (exclude $0 / mileage / error rows)
    df = df[(df["MktFare"] >= MIN_FARE) & (df["MktFare"] <= MAX_FARE)]
    df = df[df["Passengers"] > 0]

    print(f"→ {len(df):,} rows after filter")

    # Cache for next run
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path, index=False)
    return df


# ── Transform to ML features ───────────────────────────────────────────────────

def transform(df: pd.DataFrame) -> pd.DataFrame:
    """Convert BTS columns → our training schema."""
    df = df.copy()

    # Approximate departure date: mid-quarter
    df["month"] = df["Quarter"].map(QUARTER_MONTH)
    df["departure_date"] = pd.to_datetime(
        df["Year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-15"
    )
    df["fetch_date"] = df["departure_date"] - pd.Timedelta(days=30)
    df["days_to_departure"] = 30
    df["day_of_week"] = df["departure_date"].dt.dayofweek

    # Historical avg per route (computed across all data)
    route_avg = (
        df.groupby(["Origin", "Dest"])["MktFare"]
        .mean()
        .rename("historical_avg")
        .reset_index()
    )
    df = df.merge(route_avg, on=["Origin", "Dest"], how="left")

    # Rename to match our schema
    df = df.rename(columns={
        "Origin": "origin",
        "Dest": "destination",
        "MktFare": "price",
        "AirCarrier": "airline",
        "TkCarrier": "airline",   # BTS alternate column name
        "OpCarrier": "airline",   # BTS alternate column name
        "Year": "year",
        "Quarter": "quarter",
    })

    # BTS files don't always include carrier — default to UNKNOWN (not a model feature)
    if "airline" not in df.columns:
        df["airline"] = "UNKNOWN"

    df["cabin_class"] = "ECONOMY"

    out_cols = [
        "origin", "destination", "departure_date", "fetch_date",
        "days_to_departure", "day_of_week", "month",
        "price", "airline", "cabin_class", "historical_avg",
    ]
    return df[out_cols].dropna()


# ── BigQuery upload ────────────────────────────────────────────────────────────

def upload_to_bq(df: pd.DataFrame):
    client = bigquery.Client(project=BQ_PROJECT)

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=[
            bigquery.SchemaField("origin", "STRING"),
            bigquery.SchemaField("destination", "STRING"),
            bigquery.SchemaField("departure_date", "DATE"),
            bigquery.SchemaField("fetch_date", "DATE"),
            bigquery.SchemaField("days_to_departure", "INTEGER"),
            bigquery.SchemaField("day_of_week", "INTEGER"),
            bigquery.SchemaField("month", "INTEGER"),
            bigquery.SchemaField("price", "FLOAT"),
            bigquery.SchemaField("airline", "STRING"),
            bigquery.SchemaField("cabin_class", "STRING"),
            bigquery.SchemaField("historical_avg", "FLOAT"),
        ],
        source_format=bigquery.SourceFormat.CSV,
    )

    # Convert dates to string for BQ
    df = df.copy()
    df["departure_date"] = df["departure_date"].dt.strftime("%Y-%m-%d")
    df["fetch_date"] = df["fetch_date"].dt.strftime("%Y-%m-%d")

    print(f"\nUploading {len(df):,} rows to BigQuery {BQ_TABLE}…")
    job = client.load_table_from_dataframe(df, BQ_TABLE, job_config=job_config)
    job.result()
    print(f"Uploaded → {BQ_TABLE}  ({len(df):,} rows)")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(years: list[int], skip_bq: bool = False):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    all_frames = []

    for year in sorted(years):
        for quarter in [1, 2, 3, 4]:
            if year == date.today().year and quarter > (date.today().month - 1) // 3 + 1:
                continue  # skip future quarters
            df = download_quarter(year, quarter)
            if df is not None and not df.empty:
                all_frames.append(df)

    if not all_frames:
        print("No data downloaded.")
        return

    combined = pd.concat(all_frames, ignore_index=True)
    print(f"\nCombined: {len(combined):,} raw rows across {len(all_frames)} quarters")

    transformed = transform(combined)
    print(f"After transform: {len(transformed):,} training rows")

    # Save CSV
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    transformed.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved → {OUTPUT_PATH}")

    # Print summary
    print("\nRoutes covered:")
    summary = (
        transformed.groupby(["origin", "destination"])
        .agg(rows=("price", "count"), avg_fare=("price", "mean"))
        .reset_index()
    )
    print(summary.to_string(index=False))

    if not skip_bq:
        upload_to_bq(transformed)

    return transformed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download BTS DB1B fare data (free, authoritative)")
    parser.add_argument(
        "--years", type=int, nargs="+",
        default=list(range(2015, 2025)),
        help="Years to download (default: 2015–2024)",
    )
    parser.add_argument("--skip-bq", action="store_true", help="Skip BigQuery upload")
    args = parser.parse_args()

    run(args.years, skip_bq=args.skip_bq)
    print("\nDone! Re-run train_xgboost.py to retrain on real data.")
