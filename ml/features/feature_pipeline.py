"""
BigQuery feature engineering pipeline.

Reads raw fare_data from BigQuery, computes ML features, and writes the
feature table back to BigQuery for use by training and prediction jobs.

Usage:
    python -m ml.features.feature_pipeline
    python -m ml.features.feature_pipeline --project flightai-dev --dataset flightai
"""
import argparse
from datetime import date

from google.cloud import bigquery

FEATURE_TABLE = "fare_features"

# SQL that computes all features from raw fare_data
FEATURE_SQL = """
WITH base AS (
  SELECT
    origin,
    destination,
    departure_date,
    fetch_date,
    airline,
    cabin_class,
    price,
    DATE_DIFF(departure_date, fetch_date, DAY)                   AS days_to_departure,
    EXTRACT(DAYOFWEEK FROM departure_date)                       AS day_of_week,   -- 1=Sun, 7=Sat
    EXTRACT(MONTH    FROM departure_date)                        AS month,
    EXTRACT(YEAR     FROM departure_date)                        AS year
  FROM `{project}.{dataset}.fare_data`
  WHERE fetch_date IS NOT NULL
    AND departure_date > fetch_date
),
route_stats AS (
  SELECT
    origin,
    destination,
    cabin_class,
    AVG(price)    AS historical_avg,
    STDDEV(price) AS price_stddev,
    COUNT(*)      AS sample_count
  FROM base
  GROUP BY 1, 2, 3
),
with_stats AS (
  SELECT
    b.*,
    rs.historical_avg,
    rs.price_stddev,
    rs.sample_count,
    SAFE_DIVIDE(b.price, rs.historical_avg)                      AS price_ratio,
    SAFE_DIVIDE(b.price - rs.historical_avg, rs.price_stddev)    AS price_z_score,

    -- Last-minute indicator
    CASE
      WHEN b.days_to_departure <= 7  THEN 1
      ELSE 0
    END                                                           AS is_last_minute,

    -- Peak season indicator (Jun–Aug, Dec)
    CASE
      WHEN b.month IN (6, 7, 8, 12) THEN 1
      ELSE 0
    END                                                           AS is_peak_season,

    -- Weekend departure
    CASE
      WHEN b.day_of_week IN (1, 7) THEN 1
      ELSE 0
    END                                                           AS is_weekend,

    -- Price bucket for classification tasks (cheap / mid / expensive)
    CASE
      WHEN b.price < rs.historical_avg * 0.85  THEN 'cheap'
      WHEN b.price > rs.historical_avg * 1.20  THEN 'expensive'
      ELSE 'mid'
    END                                                           AS price_bucket
  FROM base b
  JOIN route_stats rs USING (origin, destination, cabin_class)
)
SELECT
  origin,
  destination,
  departure_date,
  fetch_date,
  airline,
  cabin_class,
  price,
  days_to_departure,
  day_of_week,
  month,
  year,
  historical_avg,
  price_stddev,
  sample_count,
  price_ratio,
  price_z_score,
  is_last_minute,
  is_peak_season,
  is_weekend,
  price_bucket,
  CURRENT_TIMESTAMP()                                             AS feature_created_at
FROM with_stats
"""


def run_pipeline(project: str, dataset: str, dry_run: bool = False) -> dict:
    client = bigquery.Client(project=project)

    sql = FEATURE_SQL.format(project=project, dataset=dataset)
    dest_table = f"{project}.{dataset}.{FEATURE_TABLE}"

    job_config = bigquery.QueryJobConfig(
        destination=dest_table,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        dry_run=dry_run,
    )

    print(f"Running feature pipeline → {dest_table}  (dry_run={dry_run})")
    job = client.query(sql, job_config=job_config)

    if dry_run:
        bytes_processed = job.total_bytes_processed
        print(f"Dry run OK — would process {bytes_processed / 1e6:.1f} MB")
        return {"dry_run": True, "bytes_processed": bytes_processed}

    job.result()  # wait for completion

    dest_ref = client.get_table(dest_table)
    row_count = dest_ref.num_rows
    print(f"Done — {row_count:,} feature rows written to {dest_table}")

    _log_run(client, project, dataset, row_count)
    return {"rows_written": row_count, "destination": dest_table}


def _log_run(client: bigquery.Client, project: str, dataset: str, row_count: int):
    """Append a pipeline run record to agent_logs_export (reusing that table for simplicity)."""
    table_id = f"{project}.{dataset}.agent_logs_export"
    rows = [{
        "run_date": date.today().isoformat(),
        "pipeline": "feature_pipeline",
        "rows_written": row_count,
        "status": "success",
    }]
    try:
        errors = client.insert_rows_json(table_id, rows)
        if errors:
            print(f"Log insert warnings: {errors}")
    except Exception as e:
        print(f"Log skipped: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FlightAI BigQuery feature pipeline")
    parser.add_argument("--project", default="flightai-dev")
    parser.add_argument("--dataset", default="flightai")
    parser.add_argument("--dry-run", action="store_true", help="Validate SQL without writing")
    args = parser.parse_args()

    result = run_pipeline(args.project, args.dataset, dry_run=args.dry_run)
    print(result)
