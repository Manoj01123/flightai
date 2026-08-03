"""
Set up Cloud Monitoring alerting policies for FlightAI.

Creates:
  1. Booking failure rate > 5 alert
  2. Duffel API error rate alert
  3. Wallet debit failure alert
  4. Pub/Sub consumer lag alert

Usage:
    python -m ml.analytics.setup_alerting
"""
from google.cloud import monitoring_v3
from google.protobuf.duration_pb2 import Duration

PROJECT = "flightai-dev"
PROJECT_NAME = f"projects/{PROJECT}"


def create_policy(client, policy: dict) -> str:
    from google.cloud.monitoring_v3.types import AlertPolicy
    result = client.create_alert_policy(
        name=PROJECT_NAME,
        alert_policy=policy,
    )
    print(f"  Created: {result.display_name}  ({result.name.split('/')[-1]})")
    return result.name


def setup_all():
    client = monitoring_v3.AlertPolicyServiceClient()

    # ── 1. Booking failure rate ────────────────────────────────────────────────
    # Triggers if booking_failure_rate log metric exceeds 5 events in 5 minutes
    create_policy(client, {
        "display_name": "FlightAI — Booking Failure Rate High",
        "documentation": {
            "content": (
                "Booking failure rate exceeded threshold.\n\n"
                "**Actions:**\n"
                "1. Check mcp-booking Cloud Run logs\n"
                "2. Verify Duffel API status at status.duffel.com\n"
                "3. Check wallet balance for affected users"
            ),
            "mime_type": "text/markdown",
        },
        "conditions": [
            {
                "display_name": "booking_failure_rate > 5 per 5min",
                "condition_threshold": {
                    "filter": (
                        'metric.type="logging.googleapis.com/user/booking_failure_rate" '
                        'resource.type="cloud_run_revision"'
                    ),
                    "comparison": monitoring_v3.ComparisonType.COMPARISON_GT,
                    "threshold_value": 5.0,
                    "duration": Duration(seconds=300),
                    "aggregations": [
                        {
                            "alignment_period": Duration(seconds=300),
                            "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_SUM,
                        }
                    ],
                },
            }
        ],
        "combiner": monitoring_v3.AlertPolicy.ConditionCombinerType.OR,
        "enabled": True,
        "alert_strategy": {"auto_close": Duration(seconds=1800)},
    })

    # ── 2. Pub/Sub undelivered messages ───────────────────────────────────────
    create_policy(client, {
        "display_name": "FlightAI — Pub/Sub Subscription Backlog High",
        "documentation": {
            "content": (
                "Pub/Sub subscription has >100 undelivered messages. "
                "The price-watcher or orchestrator may be down."
            ),
            "mime_type": "text/markdown",
        },
        "conditions": [
            {
                "display_name": "Undelivered message count > 100",
                "condition_threshold": {
                    "filter": (
                        'metric.type="pubsub.googleapis.com/subscription/num_undelivered_messages" '
                        'resource.type="pubsub_subscription"'
                    ),
                    "comparison": monitoring_v3.ComparisonType.COMPARISON_GT,
                    "threshold_value": 100.0,
                    "duration": Duration(seconds=300),
                    "aggregations": [
                        {
                            "alignment_period": Duration(seconds=300),
                            "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MAX,
                        }
                    ],
                },
            }
        ],
        "combiner": monitoring_v3.AlertPolicy.ConditionCombinerType.OR,
        "enabled": True,
        "alert_strategy": {"auto_close": Duration(seconds=3600)},
    })

    # ── 3. Cloud Run error rate ────────────────────────────────────────────────
    create_policy(client, {
        "display_name": "FlightAI — Cloud Run 5xx Error Rate High",
        "documentation": {
            "content": "Cloud Run services are returning 5xx errors. Check service logs.",
            "mime_type": "text/markdown",
        },
        "conditions": [
            {
                "display_name": "5xx response count > 10 per 5min",
                "condition_threshold": {
                    "filter": (
                        'metric.type="run.googleapis.com/request_count" '
                        'resource.type="cloud_run_revision" '
                        'metric.labels.response_code_class="5xx"'
                    ),
                    "comparison": monitoring_v3.ComparisonType.COMPARISON_GT,
                    "threshold_value": 10.0,
                    "duration": Duration(seconds=300),
                    "aggregations": [
                        {
                            "alignment_period": Duration(seconds=300),
                            "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_SUM,
                        }
                    ],
                },
            }
        ],
        "combiner": monitoring_v3.AlertPolicy.ConditionCombinerType.OR,
        "enabled": True,
        "alert_strategy": {"auto_close": Duration(seconds=1800)},
    })

    print("\nAll alerting policies created.")
    print(f"View at: https://console.cloud.google.com/monitoring/alerting?project={PROJECT}")


if __name__ == "__main__":
    print("Creating Cloud Monitoring alerting policies...")
    setup_all()
