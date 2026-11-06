# Product Recommendation API (COEN 424, Option A)

A REST service that answers "what should this shopper see next?". Two
microservices on Google Cloud Run, data in Firestore, and one component built
twice: **v1** (rules) and **v2** (an AI agent where Gemini decides which tools
to call), released with a canary.

- Contract: [`openapi.yaml`](openapi.yaml) - on SwaggerHub: [product-recommendation-api 1.0.0](https://app.swaggerhub.com/apis/concordiauniversity-6d6/product-recommendation-api/1.0.0)
- Data model: [`docs/data-model.md`](docs/data-model.md)
- Canary criteria and steps: [`docs/canary-runbook.md`](docs/canary-runbook.md)
- Step-by-step from laptop to cloud: [`docs/phase-guide.md`](docs/phase-guide.md)

## Layout

```
openapi.yaml                 the API contract (written first)
catalog-service/             products + user events  (Flask, Firestore)
recommendation-service/      recommendations: v1 rules or v2 agent (same image)
facade/                      local-only router that splits traffic v1/v2
loadtest/loadtest.py         the same load at every canary step
scripts/split_report.py      per-version numbers from the logs
deploy/                      Google Cloud scripts: setup, deploy, canary, report, dashboard
tests/                       end-to-end tests against the OpenAPI contract
.github/workflows/ci.yml     tests + image builds on every push
```

## Run everything locally (Docker)

```bash
docker compose up --build          # catalog, v1, v2, facade
curl -s localhost:8080/api/v1/products | python3 -m json.tool
curl -s -X POST localhost:8080/api/v1/users/u42/events \
     -H "Content-Type: application/json" -d '{"productId":"p001","type":"purchase"}'
curl -s "localhost:8080/api/v1/users/u42/recommendations?limit=5" | python3 -m json.tool
```

Locally, v2 uses an offline **scripted stand-in** (not AI) unless you start it
with `docker-compose.gemini.yml`. Rehearse a canary step:

```bash
V2_PERCENT=25 docker compose up -d facade
python3 loadtest/loadtest.py --catalog-url http://localhost:8080 --reco-url http://localhost:8080 --duration 60
docker compose logs --no-log-prefix --since 2m reco-v1 reco-v2 | python3 scripts/split_report.py
```

## Run the tests without Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r catalog-service/requirements.txt -r recommendation-service/requirements.txt \
            -r facade/requirements.txt -r requirements-dev.txt
(cd catalog-service && python -m pytest -q) && (cd recommendation-service && python -m pytest -q) \
  && (cd facade && python -m pytest -q) && python -m pytest -q tests
```

## Deploy to Google Cloud

Order matters: **create the budget alert first** (project requirement 5).

```bash
source deploy/config.sh            # after setting PROJECT_ID inside it
BILLING_ACCOUNT=... deploy/00_budget.sh   # $100 budget, alerts 25/50/75/90%
deploy/01_setup_project.sh         # APIs, Firestore, service accounts, log metrics
deploy/02_deploy_catalog.sh
python deploy/seed_firestore.py    # once
deploy/03_deploy_v1.sh             # 100% v1
deploy/04_deploy_v2.sh             # v2 revision, 0% traffic
deploy/05_create_dashboard.sh
deploy/canary.sh 10                # then 25, 50, 100;  0 = rollback
deploy/report.sh 10                # per-version numbers for the last 10 minutes
```

No API key exists anywhere: each Cloud Run service runs as its own service
account (`catalog-sa`, `reco-sa`) with only the permission it needs.

## AI-assisted development

Code, configuration and documentation were drafted with Claude Opus 5.5
(Anthropic) in guided sessions and run, tested and reviewed by the group.
Commits credit it with a `Co-Authored-By` line. v2 uses Gemini on Vertex AI
(model pinned in `deploy/config.sh`).
