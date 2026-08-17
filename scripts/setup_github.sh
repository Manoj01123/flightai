#!/usr/bin/env bash
# Run from the flightai/ directory: bash scripts/setup_github.sh
# Fill in the values below before running.
set -e

GITHUB_USER="your-github-username"
REPO_NAME="flightai"
WIF_PROVIDER="projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider"
WIF_SERVICE_ACCOUNT="flightai-app@YOUR_GCP_PROJECT.iam.gserviceaccount.com"
GCP_PROJECT_ID="your-gcp-project-id"
VITE_API_URL="https://your-gateway-url.run.app"
VITE_STRIPE_KEY="pk_test_..."

echo "=== Step 1: GitHub login ==="
gh auth login

echo ""
echo "=== Step 2: Create private GitHub repo and push ==="
gh repo create "$GITHUB_USER/$REPO_NAME" \
  --private \
  --description "AI-powered autonomous flight booking agent — XPRIZE submission"

git remote add origin "https://github.com/$GITHUB_USER/$REPO_NAME.git"
git branch -M main
git push -u origin main

echo ""
echo "=== Step 3: Set GitHub Actions secrets ==="
echo "$WIF_PROVIDER"         | gh secret set WIF_PROVIDER         --repo "$GITHUB_USER/$REPO_NAME"
echo "$WIF_SERVICE_ACCOUNT"  | gh secret set WIF_SERVICE_ACCOUNT  --repo "$GITHUB_USER/$REPO_NAME"
echo "$GCP_PROJECT_ID"       | gh secret set GCP_PROJECT_ID       --repo "$GITHUB_USER/$REPO_NAME"
echo "$VITE_API_URL"         | gh secret set VITE_API_URL         --repo "$GITHUB_USER/$REPO_NAME"
echo "$VITE_STRIPE_KEY"      | gh secret set VITE_STRIPE_PUBLISHABLE_KEY --repo "$GITHUB_USER/$REPO_NAME"

echo ""
echo "=== Step 4: Create 'dev' and 'production' GitHub environments ==="
gh api "repos/$GITHUB_USER/$REPO_NAME/environments/dev"           --method PUT || true
gh api "repos/$GITHUB_USER/$REPO_NAME/environments/production"    --method PUT \
  --field wait_timer=0 || true

echo ""
echo "=== Done! ==="
echo "Repo: https://github.com/$GITHUB_USER/$REPO_NAME"
echo "Actions: https://github.com/$GITHUB_USER/$REPO_NAME/actions"
