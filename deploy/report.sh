#!/usr/bin/env bash
# Per-version canary report for the last N minutes, from Cloud Logging.
#   deploy/report.sh 10
set -euo pipefail
source "$(dirname "$0")/config.sh"
MINUTES="${1:-10}"
SINCE=$(python3 -c "import datetime as d; print((d.datetime.now(d.timezone.utc)-d.timedelta(minutes=$MINUTES)).strftime('%Y-%m-%dT%H:%M:%SZ'))")

gcloud logging read \
  "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$RECO_SERVICE\" AND jsonPayload.event=\"recommendation\" AND timestamp>=\"$SINCE\"" \
  --format=json --limit=100000 | python3 "$(dirname "$0")/../scripts/split_report.py"
