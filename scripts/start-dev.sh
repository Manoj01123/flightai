#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/venv/bin"

echo ""
echo "FlightAI — Local Dev Startup"
echo "============================="

# Step 1: infrastructure
echo ""
echo "[1/3] Starting Postgres + Redis + Nginx proxy..."
docker compose -f "$ROOT/docker-compose.dev.yml" up -d
echo "      Waiting for Postgres to be healthy..."
until docker compose -f "$ROOT/docker-compose.dev.yml" exec postgres pg_isready -U flightai -q 2>/dev/null; do
  sleep 1
done
echo "      Postgres ready."

# Step 2: run migrations with local DB URL
echo ""
echo "[2/3] Running DB migrations..."
export DATABASE_URL="postgresql+asyncpg://flightai:flightai@localhost:5432/flightai"
cd "$ROOT" && "$VENV/alembic" upgrade head
echo "      Migrations done."

# Step 3: launch services in background
echo ""
echo "[3/3] Starting backend services..."
export DATABASE_URL="postgresql+asyncpg://flightai:flightai@localhost:5432/flightai"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="development"

"$VENV/uvicorn" services.user.main:app        --port 8001 --reload &
"$VENV/uvicorn" services.wallet.main:app      --port 8002 --reload &
"$VENV/uvicorn" services.booking.main:app     --port 8003 --reload &
"$VENV/uvicorn" services.orchestrator.main:app --port 8007 --reload &

echo ""
echo "============================="
echo "All services started."
echo ""
echo "  API gateway  → http://localhost:8000"
echo "  User service → http://localhost:8001/docs"
echo "  Wallet       → http://localhost:8002/docs"
echo "  Booking      → http://localhost:8003/docs"
echo "  Orchestrator → http://localhost:8007/docs"
echo ""
echo "Now open a NEW terminal and run:"
echo "  cd frontend && npm run dev"
echo ""
echo "Frontend will be at → http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all services."
wait
