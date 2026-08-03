.PHONY: help setup venv install install-dev lint test migrate migrate-down run-user run-wallet run-booking run-watcher run-orchestrator docker-build clean db-start db-stop

VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
ALEMBIC := $(VENV)/bin/alembic
PYTEST := $(VENV)/bin/pytest
BLACK := $(VENV)/bin/black
ISORT := $(VENV)/bin/isort
FLAKE8 := $(VENV)/bin/flake8

GCP_PROJECT ?= $(shell gcloud config get-value project)
REGION ?= us-central1
ENV ?= dev

help:
	@echo ""
	@echo "FlightAI — Developer Commands"
	@echo "─────────────────────────────"
	@echo "  make setup          Full first-time setup (venv + deps + .env)"
	@echo "  make install        Install base dependencies"
	@echo "  make install-dev    Install dev dependencies (includes testing tools)"
	@echo "  make lint           Run black + isort + flake8"
	@echo "  make test           Run all tests with coverage"
	@echo "  make migrate        Apply all pending DB migrations"
	@echo "  make migrate-down   Rollback last migration"
	@echo "  make run-user       Start user service locally"
	@echo "  make run-wallet     Start wallet service locally"
	@echo "  make run-booking    Start booking service locally"
	@echo "  make run-watcher    Start price-watcher locally"
	@echo "  make run-orchestrator  Start orchestrator locally"
	@echo "  make docker-build   Build all Docker images"
	@echo ""

setup: venv install-dev
	@if [ ! -f .env ]; then cp .env.example .env; echo "✅ .env created from .env.example — fill in your credentials"; fi
	@echo "✅ Setup complete. Run 'make migrate' once your DB is ready."

venv:
	python3 -m venv $(VENV)
	@echo "✅ venv created"

install:
	$(PIP) install -r requirements/base.txt

install-dev:
	$(PIP) install -r requirements/dev.txt
	$(PIP) install -r requirements/ml.txt

lint:
	$(BLACK) --check services/
	$(ISORT) --check-only services/
	$(FLAKE8) services/ --max-line-length=120 --extend-ignore=E203,W503

lint-fix:
	$(BLACK) services/
	$(ISORT) services/

test:
	$(PYTEST) tests/ -v --cov=services --cov-report=term-missing

migrate:
	$(ALEMBIC) upgrade head

migrate-down:
	$(ALEMBIC) downgrade -1

migrate-history:
	$(ALEMBIC) history --verbose

run-user:
	$(VENV)/bin/uvicorn services.user.main:app --reload --port 8001

run-wallet:
	$(VENV)/bin/uvicorn services.wallet.main:app --reload --port 8002

run-booking:
	$(VENV)/bin/uvicorn services.booking.main:app --reload --port 8003

run-watcher:
	$(VENV)/bin/uvicorn services.price-watcher.main:app --reload --port 8004

run-prediction:
	$(VENV)/bin/uvicorn services.mcp-prediction.main:app --reload --port 8005

run-notifier:
	$(VENV)/bin/uvicorn services.mcp-notifier.main:app --reload --port 8006

run-orchestrator:
	$(VENV)/bin/uvicorn services.orchestrator.main:app --reload --port 8007

docker-build:
	@for svc in user wallet booking price-watcher mcp-prediction mcp-notifier orchestrator; do \
		echo "Building $$svc..."; \
		docker build -f services/$$svc/Dockerfile -t flightai/$$svc:local .; \
	done

gcp-enable-apis:
	gcloud services enable \
		run.googleapis.com \
		sqladmin.googleapis.com \
		pubsub.googleapis.com \
		secretmanager.googleapis.com \
		artifactregistry.googleapis.com \
		bigquery.googleapis.com \
		aiplatform.googleapis.com \
		redis.googleapis.com \
		cloudtrace.googleapis.com \
		monitoring.googleapis.com \
		--project=$(GCP_PROJECT)
	@echo "✅ GCP APIs enabled for project $(GCP_PROJECT)"

db-start:
	~/google-cloud-sdk/bin/gcloud sql instances patch flightai-dev --activation-policy=ALWAYS --project=flightai-dev
	@echo "✅ Cloud SQL started — ready in ~30 seconds"

db-stop:
	~/google-cloud-sdk/bin/gcloud sql instances patch flightai-dev --activation-policy=NEVER --project=flightai-dev
	@echo "✅ Cloud SQL stopped — no charges until next start"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"
