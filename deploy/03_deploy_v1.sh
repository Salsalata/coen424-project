#!/usr/bin/env bash
# Deploy recommendation-service v1 (rules). This first revision gets the tag
# "v1" and 100% of the traffic.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$(dirname "$0")/.."

CATALOG_URL=$(gcloud run services describe "$CATALOG_SERVICE" --region "$REGION" --format='value(status.url)')

gcloud run deploy "$RECO_SERVICE" --source recommendation-service --region "$REGION" \
  --service-account "$RECO_SA" --allow-unauthenticated \
  --set-env-vars "RECOMMENDER=v1,CATALOG_URL=$CATALOG_URL/api/v1" \
  --labels "app=reco-api,component=recommendation" \
  --tag v1

RECO_URL=$(gcloud run services describe "$RECO_SERVICE" --region "$REGION" --format='value(status.url)')
echo "recommendation-service (v1) is live at $RECO_URL"
curl -s "$RECO_URL/healthz"; echo
