terraform {
  required_version = ">= 1.9"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "gcs" {
    # Populated per-environment in environments/*/backend.tf
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Enable GCP APIs ──────────────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sql-component.googleapis.com",
    "sqladmin.googleapis.com",
    "pubsub.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "aiplatform.googleapis.com",
    "redis.googleapis.com",
    "cloudtrace.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ── Artifact Registry ────────────────────────────────────────────────────────
resource "google_artifact_registry_repository" "flightai" {
  repository_id = "flightai"
  location      = var.region
  format        = "DOCKER"
  description   = "FlightAI Docker images"
  depends_on    = [google_project_service.apis]
}

# ── Cloud SQL (PostgreSQL) ───────────────────────────────────────────────────
resource "google_sql_database_instance" "main" {
  name             = "flightai-${var.environment}"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = var.environment == "prod" ? "db-custom-2-7680" : "db-f1-micro"
    availability_type = var.environment == "prod" ? "REGIONAL" : "ZONAL"
    disk_autoresize   = true
    disk_size         = 20

    backup_configuration {
      enabled            = true
      start_time         = "03:00"
      binary_log_enabled = false
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }
  }

  deletion_protection = var.environment == "prod"
  depends_on          = [google_project_service.apis, google_service_networking_connection.private_vpc]
}

resource "google_sql_database" "flightai" {
  name     = "flightai"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "app" {
  name     = "flightai_app"
  instance = google_sql_database_instance.main.name
  password = data.google_secret_manager_secret_version.db_password.secret_data
}

# ── Pub/Sub Topics ───────────────────────────────────────────────────────────
locals {
  pubsub_topics = [
    "price.updated",
    "booking.confirmed",
    "booking.failed",
    "wallet.low",
  ]
}

resource "google_pubsub_topic" "topics" {
  for_each   = toset(local.pubsub_topics)
  name       = replace(each.value, ".", "-")
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "orchestrator_price" {
  name  = "price-updated-orchestrator-sub"
  topic = google_pubsub_topic.topics["price-updated"].name

  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"  # 7 days

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.topics["booking-failed"].id
    max_delivery_attempts = 5
  }
}

# ── Cloud Memorystore (Redis) ────────────────────────────────────────────────
resource "google_redis_instance" "cache" {
  name           = "flightai-${var.environment}"
  tier           = "BASIC"
  memory_size_gb = 1
  region         = var.region
  redis_version  = "REDIS_7_0"
  display_name   = "FlightAI Cache"
  depends_on     = [google_project_service.apis]
}

# ── Secret Manager ───────────────────────────────────────────────────────────
locals {
  secrets = [
    "amadeus-client-id",
    "amadeus-client-secret",
    "stripe-secret-key",
    "stripe-webhook-secret",
    "twilio-account-sid",
    "twilio-auth-token",
    "sendgrid-api-key",
    "db-password",
    "jwt-secret",
  ]
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(local.secrets)
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

data "google_secret_manager_secret_version" "db_password" {
  secret  = "db-password"
  version = "latest"
  depends_on = [google_secret_manager_secret.secrets]
}

# ── Budget Alert ─────────────────────────────────────────────────────────────
resource "google_billing_budget" "alert" {
  billing_account = var.billing_account_id
  display_name    = "FlightAI ${var.environment} Budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = "100"
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }
}
