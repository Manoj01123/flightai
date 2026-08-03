#!/bin/bash
# Day 1 GCP Setup Script for FlightAI
# Usage: GCP_PROJECT=your-project-id ./scripts/setup_gcp.sh
set -euo pipefail

PROJECT=${GCP_PROJECT:?Set GCP_PROJECT environment variable}
REGION="us-central1"

echo "🚀 Setting up GCP project: $PROJECT"

# Set default project
gcloud config set project "$PROJECT"

# Enable all required APIs
echo "📡 Enabling APIs..."
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
  logging.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com

# Create Artifact Registry
echo "Creating Artifact Registry..."
gcloud artifacts repositories create flightai \
  --repository-format=docker \
  --location="$REGION" \
  --description="FlightAI Docker images" 2>/dev/null || echo "  (already exists)"

# Create Secret Manager placeholders
echo "🔐 Creating Secret Manager secrets..."
for secret in \
  amadeus-client-id \
  amadeus-client-secret \
  stripe-secret-key \
  stripe-webhook-secret \
  twilio-account-sid \
  twilio-auth-token \
  sendgrid-api-key \
  db-password \
  jwt-secret; do
  gcloud secrets create "$secret" \
    --replication-policy="automatic" 2>/dev/null || echo "  (secret $secret already exists)"
done

# Set budget alert
echo "💰 Setting budget alert..."
gcloud billing budgets create \
  --billing-account="$(gcloud billing projects describe $PROJECT --format='value(billingAccountName)' | sed 's|billingAccounts/||')" \
  --display-name="FlightAI Budget Alert" \
  --budget-amount=100USD \
  --threshold-rules=percent=0.5 \
  --threshold-rules=percent=1.0 2>/dev/null || echo "  (budget may already exist)"

# Configure Docker for Artifact Registry
echo "🐳 Configuring Docker auth..."
gcloud auth configure-docker "$REGION-docker.pkg.dev"

echo ""
echo "✅ GCP setup complete!"
echo ""
echo "Next steps:"
echo "  1. Add secret values: gcloud secrets versions add amadeus-client-id --data-file=-"
echo "  2. Create Cloud SQL: terraform -chdir=infra/terraform apply -var-file=environments/dev/terraform.tfvars"
echo "  3. Copy .env: cp .env.example .env && fill in your credentials"
echo "  4. Run migrations: make migrate"
