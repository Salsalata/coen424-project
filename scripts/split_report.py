"""Per-version canary report from recommendation-service logs.

Every request writes one JSON line (event="recommendation") with version,
source, valid, latency_ms, tokens and cost. This script reads those lines and
prints, for v1 and v2: share of traffic, error rate, p95 latency, correctness,
fallbacks, tokens and cost per request: the numbers of our criteria table.

Local (docker compose):
  docker compose logs --no-log-prefix --since 5m reco-v1 reco-v2 | python scripts/split_report.py
Cloud Run (Cloud Logging):
  gcloud logging read 'resource.type="cloud_run_revision" AND
      resource.labels.service_name="recommendation-service" AND
      jsonPayload.event="recommendation" AND timestamp>="2026-11-16T15:00:00Z"' \
      --format=json --limit=100000 | python scripts/split_report.py
"""

import json
import sys


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(pct / 100 * len(ordered) + 0.5) - 1))
    return ordered[index]


def read_records(text):
    text = text.strip()
    if text.startswith("["):  # gcloud logging read --format=json gives one JSON array
        try:
            return [e.get("jsonPayload", {}) for e in json.loads(text)]
        except json.JSONDecodeError:
            pass  # not an array: plain log lines that happen to start with "["
    records = []
    for line in text.splitlines():
        line = line.strip()
        start = line.find("{")
        if start == -1:
            continue
        try:
            records.append(json.loads(line[start:]))
        except json.JSONDecodeError:
            continue
    return records


def report(records):
    rows = [r for r in records if r.get("event") == "recommendation"]
    total = len(rows)
    out = {}
    for version in ("v1", "v2"):
        mine = [r for r in rows if r.get("version") == version]
        n = len(mine)
        if not n:
            out[version] = {"requests": 0}
            continue
        errors = sum(1 for r in mine if r.get("status", 200) >= 500)
        cost = sum(r.get("cost_usd", 0) for r in mine)
        out[version] = {
            "requests": n,
            "traffic_share_pct": round(100 * n / total, 1),
            "error_rate_pct": round(100 * errors / n, 2),
            "latency_ms_p95": percentile([r["latency_ms"] for r in mine if "latency_ms" in r], 95),
            "correct_pct": round(100 * sum(1 for r in mine if r.get("valid")) / n, 2),
            "fallbacks": sum(1 for r in mine if r.get("source") == "fallback"),
            "avg_input_tokens": round(sum(r.get("input_tokens", 0) for r in mine) / n, 1),
            "avg_output_tokens": round(sum(r.get("output_tokens", 0) for r in mine) / n, 1),
            "model_cost_per_request_usd": round(cost / n, 8),
            "model_cost_total_usd": round(cost, 6),
        }
    return {"requests_total": total, **out}


if __name__ == "__main__":
    print(json.dumps(report(read_records(sys.stdin.read())), indent=2))
