#!/usr/bin/env bash
# One canary step: give v2 this percentage of traffic, v1 the rest.
#   deploy/canary.sh 10    step 1
#   deploy/canary.sh 25    promote
#   deploy/canary.sh 50    promote
#   deploy/canary.sh 100   full promotion
#   deploy/canary.sh 0     ROLLBACK: everything back to v1
# Cloud Run's traffic split is our strangler facade (REST lecture, slide 35).
#
# Live demo without waiting for a build: a broken v2 can be deployed BEFOREHAND under
# its own tag (FAULT_MODE=invalid_ids V2_TAG=faulty-v2 deploy/04_deploy_v2.sh); then
#   deploy/canary.sh 25 faulty-v2   sends 25% to the broken v2 (the healthy one gets 0%)
#   deploy/canary.sh 0              rollback: v1 100%, every v2 tag 0%
set -euo pipefail
source "$(dirname "$0")/config.sh"

V2="${1:-}"
TARGET="${2:-agent-v2}"
case "$V2" in ''|*[!0-9]*) echo "usage: $0 <percent to v2, 0-100> [agent-v2|faulty-v2]" >&2; exit 1 ;; esac
[ "$V2" -le 100 ] || { echo "percent must be 0-100" >&2; exit 1; }
case "$TARGET" in agent-v2|faulty-v2) ;; *) echo "tag must be agent-v2 or faulty-v2" >&2; exit 1 ;; esac
V1=$((100 - V2))

# Name every v2 tag that exists, so the shares always add up to 100% and a tag
# that is not the target is set to 0% (otherwise it could keep its old share)
TAGS=$(gcloud run services describe "$RECO_SERVICE" --region "$REGION" --format='value(status.traffic.tag)' | tr ';,' '\n\n')
if [ "$TARGET" = "faulty-v2" ] && ! echo "$TAGS" | grep -qx faulty-v2; then
  echo "no faulty-v2 tag yet: FAULT_MODE=invalid_ids V2_TAG=faulty-v2 deploy/04_deploy_v2.sh" >&2; exit 1
fi
SPEC="rules-v1=$V1"
for tag in agent-v2 faulty-v2; do
  if [ "$tag" = "$TARGET" ]; then
    SPEC="$SPEC,$tag=$V2"
  elif echo "$TAGS" | grep -qx "$tag"; then
    SPEC="$SPEC,$tag=0"
  fi
done

gcloud run services update-traffic "$RECO_SERVICE" --region "$REGION" --to-tags "$SPEC"
echo "$(date -u +%FT%TZ)  canary step: v1=$V1%  $TARGET=$V2%" | tee -a canary-history.log
