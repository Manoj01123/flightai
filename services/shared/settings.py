from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Environment
    environment: str = "development"
    debug: bool = False
    service_name: str = "flightai"

    # Database (Cloud SQL / PostgreSQL)
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/flightai"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    # Duffel (replaces Amadeus)
    duffel_api_key: str = ""
    duffel_base_url: str = "https://api.duffel.com"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # SendGrid
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@flightai.io"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Pub/Sub
    pubsub_topic_price_updated: str = "price.updated"
    pubsub_topic_booking_confirmed: str = "booking.confirmed"
    pubsub_topic_booking_failed: str = "booking.failed"
    pubsub_topic_wallet_low: str = "wallet.low"

    # GCS / ML
    gcs_model_bucket: str = ""
    xgboost_model_path: str = "models/xgboost_v0.pkl"

    # Vertex AI
    vertex_location: str = "us-central1"

    # PNR encryption (AES-256-GCM) — base64-encoded 32-byte key
    pnr_encryption_key: str = ""

    # Internal admin API key — guards /v1/admin/* and /v1/agent/logs on the orchestrator
    admin_api_key: str = ""


settings = Settings()
