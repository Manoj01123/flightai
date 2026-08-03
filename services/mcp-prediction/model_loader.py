import io
import pickle
from functools import lru_cache

from google.cloud import storage

from ..shared.logging import logger
from ..shared.settings import settings


@lru_cache(maxsize=1)
def load_model():
    """Load XGBoost model from GCS. Cached after first load."""
    logger.info("loading model from GCS", bucket=settings.gcs_model_bucket, path=settings.xgboost_model_path)
    client = storage.Client(project=settings.gcp_project_id)
    bucket = client.bucket(settings.gcs_model_bucket)
    blob = bucket.blob(settings.xgboost_model_path)
    model_bytes = blob.download_as_bytes()
    model = pickle.loads(model_bytes)
    logger.info("model loaded successfully")
    return model
