# Canary runbook

The strangler facade is **Cloud Run's traffic split** between two revisions of
`recommendation-service`: tag `v1` (rules) and tag `v2` (Gemini agent). Same API,
same image; the `RECOMMENDER` environment variable picks the decision-maker.
Steps follow the REST lecture (slide 35) and the project's canary criteria.

## Criteria table (defined before the canary starts)

Thresholds `X` and `Y` are set after measuring v1 and a first v2 baseline (week 10).

| Metric | How it is measured | Threshold | Action if violated |
| --- | --- | --- | --- |
| Availability | 5xx and timeouts of the v2 revision (dashboard tile 2; `error_rate_pct` in `deploy/report.sh`) | ≤ 1% | `deploy/canary.sh 0` (roll back) |
| Latency | p95 latency of the v2 revision (dashboard tile 3; `latency_ms_p95`) | ≤ X ms | roll back |
| Correctness | share of v2 requests whose own answer passed the validator; a fallback counts as a failure (dashboard tile 4; `correct_pct`) | ≥ 99% | roll back |
| Cost | model cost per v2 request from logged tokens × Vertex AI price (`model_cost_per_request_usd`), compared with v1 and the budget | ≤ $Y per request | hold the step or roll back |

## Steps

Same load at every step: `python loadtest/loadtest.py --catalog-url $CATALOG_URL --reco-url $RECO_URL --duration 300 --concurrency 4`.

| Step | Command | Then |
| --- | --- | --- |
| 0. v2 deployed with no traffic | `deploy/04_deploy_v2.sh` | try v2 on its own tag URL |
| 1. 10% | `deploy/canary.sh 10` | load 5 min → `deploy/report.sh 6` → compare with the table |
| 2. 25% | `deploy/canary.sh 25` | same |
| 3. 50% | `deploy/canary.sh 50` | same |
| 4. 100% | `deploy/canary.sh 100` | v2 serves everyone |
| Rollback, at any step | `deploy/canary.sh 0` | everything back to v1 within seconds |

## Rollback demo (required in D4)

1. Promote to 10%, show the dashboard healthy.
2. Inject a fault into v2: `FAULT_MODE=invalid_ids deploy/04_deploy_v2.sh`, then `deploy/canary.sh 25`.
3. Load for 3 minutes; `deploy/report.sh 4` shows v2 `correct_pct` near 0 while
   clients still see correct answers (the fallback protects them).
4. The correctness threshold is violated → `deploy/canary.sh 0`.
5. Fix: `FAULT_MODE=none deploy/04_deploy_v2.sh`, and restart at 10%.

Rehearsed locally on 2026-10-27 with the scripted stand-in model: at 10%, v2 was
100% valid; at 25% with `invalid_ids`, v2 was 0% valid (718 of 718 fell back)
while the load generator still measured 100% correct answers and 0 errors. That
is why error rate alone is not enough (Inference as a Utility, slide 15).

Repeated on 2026-10-29 **in Docker** (`docker compose`, 4 containers, 40 s of
load per step, 4 threads):

| Step | v2 share | v2 correct | v2 fallbacks | v2 p95 | clients: errors / correct |
| --- | --- | --- | --- | --- | --- |
| 10%, healthy | 10.2% of 9063 | 100% | 0 | 27.8 ms | 0% / 100% |
| 25%, `FAULT_MODE=invalid_ids` | 24.4% of 8198 | **0%** | **1997** | 29.2 ms | 0% / 100% |
| 0% (rollback) | 0 of 9196 | n/a | n/a | n/a | 0% / 100% |

Deadline check: with `FAULT_MODE=slow`, v2 answered in 8.0 s with
`source: fallback`, `valid: false`, `reason: agent timed out after 8.0s`.
