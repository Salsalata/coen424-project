#!/usr/bin/env bash
# Build catalog-service from its Dockerfile with Cloud Build and deploy it to
# Cloud Run (REST lecture, slide 34). Cloud Build builds on amd64 servers, so
# the image is right for the cloud even when you run this from a Mac.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$(dirname "$0")/.."

gcloud run deploy "$CATALOG_SERVICE" --source catalog-service --region "$REGION" \
  --service-account "$CATALOG_SA" --allow-unauthenticated \
  --set-env-vars "STORAGE=firestore,SEED=false,GCP_PROJECT=$PROJECT_ID" \
  --labels "app=reco-api,component=catalog"

CATALOG_URL=$(gcloud run services describe "$CATALOG_SERVICE" --region "$REGION" --format='value(status.url)')
echo "catalog-service is live at $CATALOG_URL"
curl -s "$CATALOG_URL/healthz"; echo
echo "Next: seed the products once:  python deploy/seed_firestore.py"
