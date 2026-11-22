#!/usr/bin/env bash
# Per-version canary report from Cloud Logging.
#   deploy/report.sh 10     the last 10 minutes
#   deploy/report.sh step   only since the last deploy/canary.sh (read from canary-history.log):
#                           leaves out warm-up requests and the previous step
set -euo pipefail
source "$(dirname "$0")/config.sh"
ARG="${1:-10}"

if [ "$ARG" = "step" ]; then
  HISTORY=canary-history.log                                  # canary.sh writes it in the current folder
  [ -f "$HISTORY" ] || HISTORY="$(dirname "$0")/../canary-history.log"
  [ -f "$HISTORY" ] || { echo "no canary-history.log: run deploy/canary.sh first" >&2; exit 1; }
  LAST=$(tail -1 "$HISTORY")
  SINCE=${LAST%% *}                                           # the timestamp at the start of the line
  echo "report since $SINCE (last step:${LAST#*canary step:})" >&2
else
  case "$ARG" in *[!0-9]*) echo "usage: $0 <minutes> | step" >&2; exit 1 ;; esac
  SINCE=$(python3 -c "import datetime as d; print((d.datetime.now(d.timezone.utc)-d.timedelta(minutes=$ARG)).strftime('%Y-%m-%dT%H:%M:%SZ'))")
fi

gcloud logging read \
  "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$RECO_SERVICE\" AND jsonPayload.event=\"recommendation\" AND timestamp>=\"$SINCE\"" \
  --format=json --limit=100000 | python3 "$(dirname "$0")/../scripts/split_report.py"
