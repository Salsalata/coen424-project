#!/usr/bin/env bash
# Deploy recommendation-service v2 (Gemini agent) as a NEW REVISION with 0%
# traffic and the tag "agent-v2" (REST lecture, slide 35, step 1). Same code, same
# image; RECOMMENDER=v2 switches the decision-maker.
#
# Fault injection for the rollback demo:  FAULT_MODE=invalid_ids deploy/04_deploy_v2.sh
# After redeploying v2, run deploy/canary.sh again: traffic follows the tag to the new revision.
set -euo pipefail
source "$(dirname "$0")/config.sh"
cd "$(dirname "$0")/.."

gcloud run deploy "$RECO_SERVICE" --source recommendation-service --region "$REGION" \
  --service-account "$RECO_SA" --no-traffic --tag agent-v2 \
  --update-env-vars "RECOMMENDER=v2,AGENT_MODEL=gemini,GEMINI_MODEL=$GEMINI_MODEL,VERTEX_PROJECT=$PROJECT_ID,VERTEX_LOCATION=$VERTEX_LOCATION,FAULT_MODE=${FAULT_MODE:-none},AGENT_TIMEOUT_SECONDS=${AGENT_TIMEOUT_SECONDS:-8},PRICE_INPUT_PER_M=$PRICE_INPUT_PER_M,PRICE_OUTPUT_PER_M=$PRICE_OUTPUT_PER_M"

# Each tag also gets its own URL, so v2 can be tried directly before it gets traffic
gcloud run services describe "$RECO_SERVICE" --region "$REGION" \
  --format='table(status.traffic.tag,status.traffic.percent,status.traffic.revisionName,status.traffic.url)'
echo "v2 is deployed with 0% traffic. Try its tag URL above, then: deploy/canary.sh 10"
