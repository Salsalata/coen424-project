#!/usr/bin/env bash
# One-time setup of the Google Cloud project. Run AFTER the budget alert exists
# (project requirement 5: budget before the first deployment).
set -euo pipefail
source "$(dirname "$0")/config.sh"

echo "1/4 Enabling the APIs we use..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firestore.googleapis.com aiplatform.googleapis.com logging.googleapis.com monitoring.googleapis.com

echo "2/4 Creating the Firestore database (native mode) in $REGION..."
# Check first instead of hiding errors: a hidden prompt would look like a hang.
if gcloud firestore databases describe --database="(default)" >/dev/null 2>&1; then
  echo "   (already exists)"
else
  gcloud firestore databases create --location="$REGION" --type=firestore-native --quiet
fi

echo "3/4 Creating one service account per service (least privilege, no key files)..."
gcloud iam service-accounts create catalog-sa --display-name="catalog-service" 2>/dev/null || true
gcloud iam service-accounts create reco-sa --display-name="recommendation-service" 2>/dev/null || true
# catalog-service reads and writes Firestore
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$CATALOG_SA" \
  --role="roles/datastore.user" --condition=None >/dev/null
# recommendation-service v2 calls Gemini on Vertex AI
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$RECO_SA" \
  --role="roles/aiplatform.user" --condition=None >/dev/null

echo "4/4 Log-based metrics for the canary dashboard (v2 requests, v2 invalid answers)..."
gcloud logging metrics create reco_v2_requests --description="v2 recommendation requests" \
  --log-filter='resource.type="cloud_run_revision" AND jsonPayload.event="recommendation" AND jsonPayload.version="v2"' \
  2>/dev/null || echo "   (reco_v2_requests exists)"
gcloud logging metrics create reco_v2_invalid --description="v2 answers that failed validation or fell back" \
  --log-filter='resource.type="cloud_run_revision" AND jsonPayload.event="recommendation" AND jsonPayload.version="v2" AND jsonPayload.valid=false' \
  2>/dev/null || echo "   (reco_v2_invalid exists)"

echo "Done. Next: deploy/02_deploy_catalog.sh"
