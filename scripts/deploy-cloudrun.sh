#!/usr/bin/env bash
# FlightAI — Full Cloud Run deployment script
# Usage: bash scripts/deploy-cloudrun.sh
set -euo pipefail

PROJECT=flightai-dev
REGION=us-central1
REPO=us-central1-docker.pkg.dev/$PROJECT/flightai
DB_CONN=$PROJECT:$REGION:flightai-dev
SA=flightai-app@$PROJECT.iam.gserviceaccount.com
GCLOUD=~/google-cloud-sdk/bin/gcloud

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo "========================================"
echo " FlightAI — Cloud Run Deployment"
echo "========================================"
echo " Project : $PROJECT"
echo " Region  : $REGION"
echo " Repo    : $REPO"
echo "========================================"
echo ""

# ── 0. Auth & config ──────────────────────────────────────────────────────────
$GCLOUD config set project $PROJECT --quiet

secret() {
  $GCLOUD secrets versions access latest --secret="$1" --project=$PROJECT 2>/dev/null || echo ""
}

# ── 1. Read secrets ───────────────────────────────────────────────────────────
echo "[1/10] Reading secrets from Secret Manager..."
DB_PASS=$(secret db-password)
JWT_SECRET=$(secret jwt-secret)
DUFFEL_KEY=$(secret duffel-api-key)
STRIPE_SECRET=$(secret stripe-secret-key)
STRIPE_WEBHOOK=$(secret stripe-webhook-secret)
TWILIO_SID=$(secret twilio-account-sid)
TWILIO_TOKEN=$(secret twilio-auth-token)
SENDGRID_KEY=$(secret sendgrid-api-key)
PNR_KEY=$(secret pnr-encryption-key)

if [[ -z "$DB_PASS" || -z "$JWT_SECRET" ]]; then
  echo "ERROR: db-password or jwt-secret missing from Secret Manager. Cannot deploy."
  exit 1
fi
echo "    Secrets loaded (Twilio/SendGrid optional — empty = notifications disabled)"

DATABASE_URL="postgresql+asyncpg://flightai_app:${DB_PASS}@/flightai?host=/cloudsql/${DB_CONN}"
COMMON_ENV="ENVIRONMENT=production,GCP_PROJECT_ID=$PROJECT,GCP_REGION=$REGION,GCS_MODEL_BUCKET=flightai-models,XGBOOST_MODEL_PATH=models/xgboost_v1.pkl"
DB_ENV="DATABASE_URL=$DATABASE_URL,JWT_SECRET=$JWT_SECRET"

# deploy_svc NAME DOCKERFILE [extra gcloud run deploy flags...]
# Sends all progress to stderr; prints only the service URL to stdout (so callers can capture it).
deploy_svc() {
  local NAME=$1; local DOCKERFILE=$2; shift 2

  >&2 echo ""
  >&2 echo ">>> [build] $NAME — Cloud Build submitting from $ROOT ..."

  # gcloud builds submit has no --dockerfile flag; generate a temp cloudbuild.yaml
  local CBFILE
  CBFILE=$(mktemp /tmp/cloudbuild-XXXXXX.yaml)
  cat > "$CBFILE" <<CBEOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-f', '${DOCKERFILE}', '-t', '${REPO}/${NAME}:latest', '.']
images: ['${REPO}/${NAME}:latest']
CBEOF

  $GCLOUD builds submit \
    --config "$CBFILE" \
    --project=$PROJECT \
    --quiet \
    . >&2

  rm -f "$CBFILE"

  >&2 echo ">>> [deploy] $NAME → Cloud Run..."
  $GCLOUD run deploy "$NAME" \
    --image "$REPO/$NAME:latest" \
    --region $REGION \
    --platform managed \
    --project=$PROJECT \
    --service-account $SA \
    --allow-unauthenticated \
    --min-instances 0 \
    --max-instances 5 \
    --memory 512Mi \
    --cpu 1 \
    --timeout 60 \
    --quiet \
    "$@" >&2

  $GCLOUD run services describe "$NAME" \
    --region $REGION \
    --project=$PROJECT \
    --format "value(status.url)"
}

# ── 2. mcp-prediction ─────────────────────────────────────────────────────────
echo "[2/10] Deploying mcp-prediction..."
MCP_PRED_URL=$(deploy_svc mcp-prediction services/mcp-prediction/Dockerfile \
  --set-env-vars "$COMMON_ENV")
[[ -n "$MCP_PRED_URL" ]] || { echo "ERROR: mcp-prediction deploy failed"; exit 1; }
echo "    mcp-prediction → $MCP_PRED_URL"

# ── 3. mcp-notifier ───────────────────────────────────────────────────────────
echo "[3/10] Deploying mcp-notifier..."
MCP_NOTIF_URL=$(deploy_svc mcp-notifier services/mcp-notifier/Dockerfile \
  --set-env-vars "$COMMON_ENV,TWILIO_ACCOUNT_SID=$TWILIO_SID,TWILIO_AUTH_TOKEN=$TWILIO_TOKEN,TWILIO_FROM_NUMBER=+1XXXXXXXXXX,SENDGRID_API_KEY=$SENDGRID_KEY,SENDGRID_FROM_EMAIL=noreply@flightai.io,JWT_SECRET=$JWT_SECRET")
echo "    mcp-notifier → $MCP_NOTIF_URL"

# ── 4. mcp-booking ────────────────────────────────────────────────────────────
echo "[4/10] Deploying mcp-booking..."
MCP_BOOK_URL=$(deploy_svc mcp-booking services/mcp-booking/Dockerfile \
  --add-cloudsql-instances $DB_CONN \
  --set-env-vars "$COMMON_ENV,$DB_ENV,DUFFEL_API_KEY=$DUFFEL_KEY,PNR_ENCRYPTION_KEY=$PNR_KEY")
echo "    mcp-booking → $MCP_BOOK_URL"

# ── 5. user service + DB migrations ───────────────────────────────────────────
echo "[5/10] Deploying user service..."
USER_URL=$(deploy_svc user-service services/user/Dockerfile \
  --add-cloudsql-instances $DB_CONN \
  --set-env-vars "$COMMON_ENV,$DB_ENV")
echo "    user-service → $USER_URL"

echo "    Running DB migrations..."
# Jobs use --set-cloudsql-instances (not --add-cloudsql-instances like services)
$GCLOUD run jobs delete flightai-migrate --region $REGION --project=$PROJECT --quiet 2>/dev/null || true
$GCLOUD run jobs create flightai-migrate \
  --image "$REPO/user-service:latest" \
  --region $REGION \
  --project=$PROJECT \
  --service-account $SA \
  --set-cloudsql-instances $DB_CONN \
  --set-env-vars "$COMMON_ENV,$DB_ENV" \
  --command "alembic" \
  --args "upgrade,head" \
  --quiet
$GCLOUD run jobs execute flightai-migrate \
  --region $REGION \
  --project=$PROJECT \
  --wait \
  --quiet
echo "    Migrations complete."

# ── 6. wallet service ─────────────────────────────────────────────────────────
echo "[6/10] Deploying wallet service..."
WALLET_URL=$(deploy_svc wallet-service services/wallet/Dockerfile \
  --add-cloudsql-instances $DB_CONN \
  --set-env-vars "$COMMON_ENV,$DB_ENV,STRIPE_SECRET_KEY=$STRIPE_SECRET,STRIPE_WEBHOOK_SECRET=$STRIPE_WEBHOOK")
echo "    wallet-service → $WALLET_URL"

# ── 7. booking service ────────────────────────────────────────────────────────
echo "[7/10] Deploying booking service..."
BOOKING_URL=$(deploy_svc booking-service services/booking/Dockerfile \
  --add-cloudsql-instances $DB_CONN \
  --set-env-vars "$COMMON_ENV,$DB_ENV,MCP_BOOKING_URL=$MCP_BOOK_URL")
echo "    booking-service → $BOOKING_URL"

# ── 8. orchestrator ───────────────────────────────────────────────────────────
echo "[8/10] Deploying orchestrator..."
ORCH_URL=$(deploy_svc orchestrator services/orchestrator/Dockerfile \
  --add-cloudsql-instances $DB_CONN \
  --set-env-vars "$COMMON_ENV,$DB_ENV,MCP_PREDICTION_URL=$MCP_PRED_URL,MCP_BOOKING_URL=$MCP_BOOK_URL,MCP_NOTIFIER_URL=$MCP_NOTIF_URL" \
  --min-instances 1)
echo "    orchestrator → $ORCH_URL"

# ── 9. API gateway ────────────────────────────────────────────────────────────
echo "[9/10] Deploying API gateway..."
GATEWAY_URL=$(deploy_svc gateway services/gateway/Dockerfile \
  --set-env-vars "USER_SERVICE_URL=$USER_URL,WALLET_SERVICE_URL=$WALLET_URL,BOOKING_SERVICE_URL=$BOOKING_URL,ORCHESTRATOR_URL=$ORCH_URL" \
  --min-instances 1)
echo "    gateway → $GATEWAY_URL"

# ── 10. Frontend ──────────────────────────────────────────────────────────────
echo "[10/10] Building and deploying frontend..."
pushd "$ROOT/frontend" > /dev/null

# Write production .env before building
cat > .env.production << EOF
VITE_API_URL=$GATEWAY_URL
VITE_FIREBASE_API_KEY=${VITE_FIREBASE_API_KEY:-}
VITE_FIREBASE_AUTH_DOMAIN=${VITE_FIREBASE_AUTH_DOMAIN:-}
VITE_FIREBASE_PROJECT_ID=$PROJECT
VITE_FIREBASE_STORAGE_BUCKET=$PROJECT.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=${VITE_FIREBASE_MESSAGING_SENDER_ID:-}
VITE_FIREBASE_APP_ID=${VITE_FIREBASE_APP_ID:-}
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_51TsZOQCtDBXl7BLPOBulUXe8IM6rL0rrSyOdJOocsqYWCz0ZJiCmOEYxYfwKpUgcJYmi1smQuvoScFzfc1OlxrkI00n9LRhMwI
EOF

npm install --silent
npm run build

# nginx Dockerfile — submitting from frontend/ so 'dist' and this file are at source root
cat > Dockerfile.static << 'DOCKEREOF'
FROM nginx:alpine
COPY dist /usr/share/nginx/html
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
DOCKEREOF

cat > nginx-spa.conf << 'NGINXEOF'
server {
    listen 8080;
    root /usr/share/nginx/html;
    index index.html;
    location / { try_files $uri $uri/ /index.html; }
    location ~* \.(js|css|png|jpg|ico|svg|woff2?)$ {
        expires 1y; add_header Cache-Control "public, immutable";
    }
}
NGINXEOF

echo ">>> [build] frontend — Cloud Build submitting from frontend/ ..."
CBFILE_FE=$(mktemp /tmp/cloudbuild-frontend-XXXXXX.yaml)
cat > "$CBFILE_FE" <<CBEOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-f', 'Dockerfile.static', '-t', '${REPO}/frontend:latest', '.']
images: ['${REPO}/frontend:latest']
CBEOF

$GCLOUD builds submit \
  --config "$CBFILE_FE" \
  --project=$PROJECT \
  --quiet \
  .

rm -f "$CBFILE_FE"
popd > /dev/null

echo ">>> [deploy] frontend → Cloud Run..."
$GCLOUD run deploy frontend \
  --image "$REPO/frontend:latest" \
  --region $REGION \
  --platform managed \
  --project=$PROJECT \
  --service-account $SA \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 5 \
  --memory 256Mi \
  --cpu 1 \
  --timeout 60 \
  --quiet

FRONTEND_URL=$($GCLOUD run services describe frontend \
  --region $REGION \
  --project=$PROJECT \
  --format "value(status.url)")
echo "    frontend → $FRONTEND_URL"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " DEPLOYMENT COMPLETE"
echo "========================================"
echo " Frontend  : $FRONTEND_URL"
echo " API GW    : $GATEWAY_URL"
echo " Docs      : $USER_URL/docs"
echo "========================================"
echo ""
echo "Next: open $FRONTEND_URL in your browser"
