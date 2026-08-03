"""
Monthly retraining job — submits a Vertex AI CustomJob that:
  1. Reads fresh fare_features from BigQuery
  2. Re-trains XGBoost with the latest data
  3. Uploads the new model pkl to GCS

Designed to be called by Cloud Scheduler once per month:
    POST https://{region}-aiplatform.googleapis.com/... (handled by SDK)

Usage:
    python -m ml.training.retrain_job                     # queues Vertex AI job
    python -m ml.training.retrain_job --local             # run training locally instead
"""
import argparse
import json
import subprocess
import sys
from datetime import date

PROJECT = "flightai-dev"
REGION = "us-central1"
GCS_BUCKET = "flightai-models"
TRAINING_IMAGE = "us-docker.pkg.dev/vertex-ai/training/scikit-learn-cpu.1-0:latest"
SERVICE_ACCOUNT = f"flightai-training@{PROJECT}.iam.gserviceaccount.com"


def submit_vertex_job(version: str) -> dict:
    """Submit an asynchronous Vertex AI CustomJob via the gcloud CLI."""
    job_name = f"xgboost-retrain-{version}-{date.today().isoformat()}"
    gcs_output = f"gs://{GCS_BUCKET}/vertex-jobs/{job_name}"

    # The training container runs our existing train_xgboost.py script.
    # We pass data path pointing to the BQ export that the feature pipeline writes.
    worker_pool_spec = json.dumps([{
        "machineSpec": {"machineType": "n1-standard-4"},
        "replicaCount": 1,
        "containerSpec": {
            "imageUri": TRAINING_IMAGE,
            "command": ["python3", "-m", "ml.training.train_xgboost"],
            "args": [
                "--data", f"gs://{GCS_BUCKET}/training-data/fare_features_latest.csv",
                "--version", version,
            ],
            "env": [
                {"name": "GCS_MODEL_BUCKET", "value": GCS_BUCKET},
                {"name": "GCP_PROJECT_ID", "value": PROJECT},
            ],
        },
    }])

    cmd = [
        "gcloud", "ai", "custom-jobs", "create",
        f"--project={PROJECT}",
        f"--region={REGION}",
        f"--display-name={job_name}",
        f"--worker-pool-spec={worker_pool_spec}",
        f"--base-output-directory={gcs_output}",
        f"--service-account={SERVICE_ACCOUNT}",
        "--format=json",
    ]

    print(f"Submitting Vertex AI CustomJob: {job_name}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"gcloud failed:\n{result.stderr}")

    job_info = json.loads(result.stdout)
    job_id = job_info.get("name", "").split("/")[-1]
    print(f"Job submitted: {job_id}")
    print(f"Monitor: https://console.cloud.google.com/vertex-ai/training/custom-jobs?project={PROJECT}")
    return {"job_id": job_id, "job_name": job_name, "status": "QUEUED"}


def export_bq_features_to_gcs(version: str):
    """Export the latest BigQuery fare_features to GCS so the training container can read it."""
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT)
    dest_uri = f"gs://{GCS_BUCKET}/training-data/fare_features_latest.csv"

    job_config = bigquery.ExtractJobConfig(
        destination_format=bigquery.DestinationFormat.CSV,
        print_header=True,
        compression=bigquery.Compression.NONE,
    )
    job = client.extract_table(
        f"{PROJECT}.flightai.fare_features",
        dest_uri,
        job_config=job_config,
    )
    job.result()
    print(f"Exported fare_features → {dest_uri}")


def run_local(version: str):
    """Fallback: run training locally (no Vertex AI)."""
    from ml.training.train_xgboost import train
    import os

    data_path = "ml/data/fare_training_data.csv"
    if not os.path.exists(data_path):
        from ml.data.generate_synthetic_data import generate_dataset
        generate_dataset(data_path)

    metrics = train(data_path, version)
    print(json.dumps(metrics, indent=2))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit monthly XGBoost retraining job")
    parser.add_argument("--version", default=f"v{date.today().strftime('%Y%m')}")
    parser.add_argument("--local", action="store_true", help="Run training locally instead of Vertex AI")
    args = parser.parse_args()

    if args.local:
        print(f"Running locally (version={args.version})")
        run_local(args.version)
    else:
        try:
            print(f"Exporting BQ features to GCS before submitting job...")
            export_bq_features_to_gcs(args.version)
        except Exception as e:
            print(f"BQ export skipped (ADC or table missing): {e}")

        result = submit_vertex_job(args.version)
        print(json.dumps(result, indent=2))
