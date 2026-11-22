# D4 live demo: one canary step and one rollback

Goal (project requirement): show a canary step and a rollback **live**, in about 5 of the
15 minutes. Nothing is built during the talk: both v2 versions are deployed beforehand
under their own tags, so every live command only moves traffic (seconds).

| Tag | Revision | Role |
| --- | --- | --- |
| `rules-v1` | v1, rules | the old version, always kept |
| `agent-v2` | v2, Gemini agent, healthy | the canary step |
| `faulty-v2` | v2 with `FAULT_MODE=invalid_ids` (last pick replaced by a non-existent id) | the rollback |

## Once, before the rehearsals (one build, a few minutes)

```bash
cd coen424-project
unset GEMINI_MODEL VERTEX_LOCATION PRICE_INPUT_PER_M PRICE_OUTPUT_PER_M AGENT_TIMEOUT_SECONDS
source deploy/config.sh
FAULT_MODE=invalid_ids V2_TAG=faulty-v2 deploy/04_deploy_v2.sh   # agent-v2 is left untouched
deploy/canary.sh 0                                                # v1 100%, both v2 tags 0%
```

Check the table it prints: `rules-v1` 100%, `agent-v2` and `faulty-v2` at 0%, each with
its own URL. Tags and revisions stay in place between sessions; this is not repeated.

## 10 minutes before the talk

```bash
source deploy/config.sh
CAT=$(gcloud run services describe catalog-service --region $REGION --format='value(status.url)')
RECO=$(gcloud run services describe recommendation-service --region $REGION --format='value(status.url)')
BASE=recommendation-service-pxxbzokq2a-nn.a.run.app
for t in agent-v2 faulty-v2; do for i in 1 2 3; do
  curl -s -o /dev/null -w "$t %{http_code} %{time_total}s\n" "https://$t---$BASE/api/v1/users/cloud-v2/recommendations?limit=3"
done; done                                                        # wake both revisions (cold starts)
tail -1 canary-history.log                                        # must say v1=100%
```

Open the dashboard ("Recommendation canary (v1 vs v2)") and set it to the last 30 minutes.
Put the commands below in a text file to paste from.

## Live (about 5 minutes)

| # | Say | Run | Expect |
| --- | --- | --- | --- |
| 1 | "v1 serves everyone; v2 is deployed but gets 0%." | `deploy/canary.sh 10` | traffic table: `rules-v1` 90%, `agent-v2` 10% |
| 2 | "Same load at every step." | `python3 loadtest/loadtest.py --catalog-url "$CAT" --reco-url "$RECO" --duration 120 --concurrency 4` | clients: 0 errors, 100% correct |
| 3 | "The decision comes from inside the service, not from the clients." | `deploy/report.sh step` | v2: ~10% share, correct ≥ 99%, p95 ~2 s, ~$0.0008/request → **pass** |
| 4 | "Now a v2 with a bug: it returns a product that does not exist." | `deploy/canary.sh 25 faulty-v2` | `faulty-v2` 25%, `agent-v2` 0% |
| 5 | "Same load." | load test as in 2 (`--duration 90` is enough here) | **clients still 0 errors, 100% correct** |
| 6 | "Clients see nothing wrong. The service's own validator does." | `deploy/report.sh step` | v2 correct **~0%**, fallbacks ≈ all v2 requests → **criterion violated** |
| 7 | "So we roll back." | `deploy/canary.sh 0` | `rules-v1` 100% within seconds |
| 8 | Dashboard tile 4: v2 invalid answers rise to meet v2 requests, then traffic returns to v1. | (dashboard) | |

Notes:
- `deploy/report.sh step` counts only requests since the last `deploy/canary.sh`, so the
  warm-up requests (including the deliberately broken `faulty-v2` ones) and the previous
  step are never mixed in. Run it right after the load test.
- Step 1 is short (~110-150 v2 requests): one Gemini hiccup that the retry cannot save puts
  correctness under 99%, and a minute of slow Gemini calls (each saved by a 4-6 s retry) can
  push p95 over 4,000 ms (the latter happened in rehearsal). If a criterion fails live, say so: the
  canary is doing its job, and the full canary (`docs/canary-runbook.md`: 10/25/50% passed)
  is the evidence.
- Budget: about $0.10 in Gemini per run of this demo.

## If something goes wrong on stage

| Problem | Do |
| --- | --- |
| A command hangs or the network fails | Show the recorded results: `docs/canary-runbook.md` (both canaries and the rollback demo) and the dashboard screenshots |
| `report.sh` shows 0 requests | Logs arrive up to a minute late: wait 30 s and run `deploy/report.sh step` again |
| Traffic is in a wrong state | `deploy/canary.sh 0` always returns everything to v1 |

## After the talk

`deploy/canary.sh 0` (if not already), then `tail -1 canary-history.log`.
