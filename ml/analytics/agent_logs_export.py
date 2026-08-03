"""
Export agent_logs from Cloud SQL to BigQuery and run dashboard queries.

Two operations:
  1. export   — reads agent_logs from Cloud SQL via SQLAlchemy and streams to BQ
  2. dashboard — runs BigQuery SQL analytics and prints results

This runs as a daily Cloud Scheduler job (not real-time; logs accumulate in PG
and batch-export to BQ each night for analysis).

Usage:
    python -m ml.analytics.agent_logs_export export
    python -m ml.analytics.agent_logs_export dashboard
    python -m ml.analytics.agent_logs_export export --days 7
"""
import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

PROJECT = "flightai-dev"
DATASET = "flightai"
BQ_TABLE = f"{PROJECT}.{DATASET}.agent_logs_export"

# ── BigQuery dashboard queries ─────────────────────────────────────────────────

DASHBOARD_QUERIES = {
    "decision_summary_7d": f"""
        SELECT
            action,
            COUNT(*) AS total,
            ROUND(AVG(ml_score), 1) AS avg_ml_score,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM `{BQ_TABLE}`
        WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        GROUP BY action
        ORDER BY total DESC
    """,

    "daily_decisions_30d": f"""
        SELECT
            DATE(created_at) AS day,
            COUNTIF(action = 'buy')    AS buy_count,
            COUNTIF(action = 'wait')   AS wait_count,
            COUNTIF(action = 'booked') AS booked_count,
            ROUND(AVG(ml_score), 1)    AS avg_ml_score
        FROM `{BQ_TABLE}`
        WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        GROUP BY day
        ORDER BY day DESC
        LIMIT 30
    """,

    "top_routes_booked": f"""
        SELECT
            origin,
            destination,
            COUNT(*) AS bookings,
            ROUND(AVG(price_usd), 2) AS avg_price
        FROM `{BQ_TABLE}`
        WHERE action = 'booked'
          AND created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        GROUP BY origin, destination
        ORDER BY bookings DESC
        LIMIT 10
    """,

    "ml_score_distribution": f"""
        SELECT
            CASE
                WHEN ml_score >= 90 THEN '90-100'
                WHEN ml_score >= 75 THEN '75-89'
                WHEN ml_score >= 60 THEN '60-74'
                WHEN ml_score >= 40 THEN '40-59'
                ELSE '<40'
            END AS score_band,
            COUNT(*) AS count,
            COUNTIF(action = 'buy') AS bought
        FROM `{BQ_TABLE}`
        WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        GROUP BY score_band
        ORDER BY score_band DESC
    """,

    "hourly_activity_today": f"""
        SELECT
            EXTRACT(HOUR FROM created_at) AS hour_utc,
            COUNT(*) AS decisions
        FROM `{BQ_TABLE}`
        WHERE DATE(created_at) = CURRENT_DATE()
        GROUP BY hour_utc
        ORDER BY hour_utc
    """,
}


# ── Export: Cloud SQL → BigQuery ───────────────────────────────────────────────

async def export_logs(days: int = 1):
    """Pull agent_logs rows from PostgreSQL and stream them into BigQuery."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select, text
    from google.cloud import bigquery

    # Load DB URL from env
    from dotenv import load_dotenv
    load_dotenv("flightai/.env")
    db_url = os.environ["DATABASE_URL"]

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    print(f"Fetching agent_logs since {cutoff.isoformat()}...")
    async with async_session() as db:
        result = await db.execute(
            text("""
                SELECT al.id, al.route_id, al.user_id, al.action, al.ml_score,
                       al.reasoning, al.created_at,
                       r.origin, r.destination, r.target_price,
                       b.price AS price_usd
                FROM agent_logs al
                LEFT JOIN routes r  ON r.id = al.route_id
                LEFT JOIN bookings b ON b.route_id = al.route_id
                                     AND b.status = 'CONFIRMED'
                WHERE al.created_at >= :cutoff
                ORDER BY al.created_at
            """),
            {"cutoff": cutoff},
        )
        rows = result.fetchall()

    print(f"  {len(rows)} rows fetched")
    if not rows:
        return 0

    bq_client = bigquery.Client(project=PROJECT)
    bq_rows = [
        {
            "log_id": str(r.id),
            "route_id": str(r.route_id),
            "user_id": str(r.user_id),
            "action": r.action,
            "ml_score": float(r.ml_score or 0),
            "reasoning": r.reasoning or "",
            "origin": r.origin or "",
            "destination": r.destination or "",
            "target_price": float(r.target_price or 0),
            "price_usd": float(r.price_usd or 0),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

    errors = bq_client.insert_rows_json(BQ_TABLE, bq_rows)
    if errors:
        print(f"BQ insert errors: {errors}")
        return 0

    print(f"  Exported {len(bq_rows)} rows → {BQ_TABLE}")
    return len(bq_rows)


# ── Dashboard ─────────────────────────────────────────────────────────────────

def run_dashboard(query_name: str | None = None):
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT)
    queries = (
        {query_name: DASHBOARD_QUERIES[query_name]}
        if query_name and query_name in DASHBOARD_QUERIES
        else DASHBOARD_QUERIES
    )

    for name, sql in queries.items():
        print(f"\n{'='*60}")
        print(f"  {name}")
        print('='*60)
        try:
            job = client.query(sql.strip())
            rows = list(job.result())
            if not rows:
                print("  (no data)")
                continue
            headers = list(rows[0].keys())
            print("  " + "  ".join(f"{h:<18}" for h in headers))
            print("  " + "-" * (20 * len(headers)))
            for row in rows:
                print("  " + "  ".join(f"{str(v):<18}" for v in row.values()))
        except Exception as e:
            print(f"  Error: {e}")


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FlightAI agent_logs BigQuery export + dashboard")
    parser.add_argument("action", choices=["export", "dashboard"], help="What to do")
    parser.add_argument("--days", type=int, default=1, help="How many days of logs to export")
    parser.add_argument("--query", help="Specific dashboard query to run (omit for all)")
    args = parser.parse_args()

    if args.action == "export":
        count = asyncio.run(export_logs(days=args.days))
        print(f"Done. {count} rows exported.")
    elif args.action == "dashboard":
        run_dashboard(query_name=args.query)
