#!/usr/bin/env bash
# One canary step: give v2 this percentage of traffic, v1 the rest.
#   deploy/canary.sh 10    step 1
#   deploy/canary.sh 25    promote
#   deploy/canary.sh 50    promote
#   deploy/canary.sh 100   full promotion
#   deploy/canary.sh 0     ROLLBACK: everything back to v1
# Cloud Run's traffic split is our strangler facade (REST lecture, slide 35).
set -euo pipefail
source "$(dirname "$0")/config.sh"

V2="${1:-}"
case "$V2" in ''|*[!0-9]*) echo "usage: $0 <percent to v2, 0-100>" >&2; exit 1 ;; esac
[ "$V2" -le 100 ] || { echo "percent must be 0-100" >&2; exit 1; }
V1=$((100 - V2))

gcloud run services update-traffic "$RECO_SERVICE" --region "$REGION" --to-tags "rules-v1=$V1,agent-v2=$V2"
echo "$(date -u +%FT%TZ)  canary step: v1=$V1%  v2=$V2%" | tee -a canary-history.log
