#!/usr/bin/env bash
# Run from the flightai/ directory: bash scripts/setup_github.sh
set -e

GITHUB_USER="Manoj01123"
REPO_NAME="flightai"
WIF_PROVIDER="projects/1098706474384/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider"
WIF_SERVICE_ACCOUNT="flightai-app@flightai-dev.iam.gserviceaccount.com"
GCP_PROJECT_ID="flightai-dev"
VITE_API_URL="https://gateway-t7zk5pacvq-uc.a.run.app"
VITE_STRIPE_KEY="pk_test_51TsZOQCtDBXl7BLPOBulUXe8IM6rL0rrSyOdJOocsqYWCz0ZJiCmOEYxYfwKpUgcJYmi1smQuvoScFzfc1OlxrkI00n9LRhMwI"

echo "=== Step 1: GitHub login ==="
gh auth login

echo ""
echo "=== Step 2: Stage and commit code ==="
git config user.name "$GITHUB_USER"
git config user.email "manoj.rayana@gmail.com"
git add .
git status --short | head -30
git commit -m "Initial commit — FlightAI XPRIZE submission

FastAPI microservices on Cloud Run, LangGraph orchestrator,
Gemini 2.5 Flash, XGBoost price prediction, React frontend.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

echo ""
echo "=== Step 3: Create private GitHub repo and push ==="
gh repo create "$GITHUB_USER/$REPO_NAME" \
  --private \
  --description "AI-powered autonomous flight booking agent — XPRIZE submission"

git remote add origin "https://github.com/$GITHUB_USER/$REPO_NAME.git"
git branch -M main
git push -u origin main

echo ""
echo "=== Step 4: Set GitHub Actions secrets ==="
echo "$WIF_PROVIDER"         | gh secret set WIF_PROVIDER         --repo "$GITHUB_USER/$REPO_NAME"
echo "$WIF_SERVICE_ACCOUNT"  | gh secret set WIF_SERVICE_ACCOUNT  --repo "$GITHUB_USER/$REPO_NAME"
echo "$GCP_PROJECT_ID"       | gh secret set GCP_PROJECT_ID       --repo "$GITHUB_USER/$REPO_NAME"
echo "$VITE_API_URL"         | gh secret set VITE_API_URL         --repo "$GITHUB_USER/$REPO_NAME"
echo "$VITE_STRIPE_KEY"      | gh secret set VITE_STRIPE_PUBLISHABLE_KEY --repo "$GITHUB_USER/$REPO_NAME"

echo ""
echo "=== Step 5: Create 'dev' and 'production' GitHub environments ==="
gh api "repos/$GITHUB_USER/$REPO_NAME/environments/dev"           --method PUT || true
gh api "repos/$GITHUB_USER/$REPO_NAME/environments/production"    --method PUT \
  --field wait_timer=0 || true

echo ""
echo "=== Done! ==="
echo "Repo: https://github.com/$GITHUB_USER/$REPO_NAME"
echo "Actions: https://github.com/$GITHUB_USER/$REPO_NAME/actions"
echo ""
echo "WIF GCP setup (already done):"
echo "  Pool: github-actions-pool"
echo "  Provider: github-provider"
echo "  Bound to: repo owner $GITHUB_USER"
echo ""
echo "Next push to 'develop' branch will trigger build + deploy to Cloud Run."
echo "Trigger prod deploy via Actions → 'Deploy to Production' → Run workflow."
