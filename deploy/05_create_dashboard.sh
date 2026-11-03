#!/usr/bin/env bash
# Create the canary dashboard in Cloud Monitoring (four charts: traffic,
# 5xx, p95 latency per revision; v2 requests vs invalid answers).
set -euo pipefail
source "$(dirname "$0")/config.sh"
gcloud monitoring dashboards create --config-from-file="$(dirname "$0")/dashboard.json"
echo "Open: https://console.cloud.google.com/monitoring/dashboards?project=$PROJECT_ID"
