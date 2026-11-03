# Phase guide: from your laptop to the canary on Google Cloud

Each phase ends with a **"done when"** check. Run the commands from the project
folder (`reco-api/`), in macOS Terminal or WSL Ubuntu: they are the same.

---

## Phase 2: your machine + GitHub

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r catalog-service/requirements.txt -r recommendation-service/requirements.txt \
            -r facade/requirements.txt -r requirements-dev.txt
(cd catalog-service && pytest -q) && (cd recommendation-service && pytest -q) \
  && (cd facade && pytest -q) && pytest -q tests          # 15, 22, 3, 3 passed

docker compose up --build -d
curl -s "localhost:8080/api/v1/users/u42/recommendations?limit=3" | python3 -m json.tool
docker compose down
```

Then create an **empty** GitHub repo (no README, no .gitignore), and:

```bash
git init -b main
git add .
git commit -m "Option A baseline: catalog + recommendation services, OpenAPI contract, canary tooling

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Add your 3 teammates under **Settings → Collaborators**.

**Done when:** the tests pass, compose answers, and the repo's **Actions** tab shows a green check.

---

## Phase 3: SwaggerHub (now named *Swagger Studio*, at app.swaggerhub.com)

1. Sign in, or create a free account.
2. Click **Create New → Import and Document API** (or the **Import API** tile).
3. Upload `openapi.yaml`. Name: `product-recommendation-api`. Visibility: **Public**, so the professor can open it without an account.
4. Click **Import**. The version comes from `info.version` in the file.
5. Copy the page URL into `README.md`, after "published on SwaggerHub".

After Phase 4 you'll know the real Cloud Run URLs. Edit the two `REPLACE` server
entries in the file (in the repo and on SwaggerHub) and click **Save**.

**Done when:** the public link opens the API docs, with no errors in the editor.

---

## Phase 4: Google Cloud, catalog + v1

### 4a. One-time laptop setup

| | macOS | WSL Ubuntu |
| --- | --- | --- |
| install gcloud | `brew install --cask gcloud-cli` | follow "Install the gcloud CLI → Debian/Ubuntu" on cloud.google.com |

```bash
gcloud init                                   # log in, pick or create the project
gcloud auth application-default login         # lets seed_firestore.py use your login
```

### 4b. Project, free trial, budget (before anything runs)

1. In the console, activate the **$300 free trial**. It creates a billing account.
2. Create a project, for example `coen424-reco-<yourname>`, and put its id in `deploy/config.sh` (`PROJECT_ID=`).
3. Set up the budget:

```bash
gcloud billing accounts list                       # copy the ACCOUNT_ID
BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX deploy/00_budget.sh
```

Check in **Billing → Budgets & alerts** that `coen424-reco-budget` appears with 4 thresholds. Take a screenshot for the report.

### 4c. Deploy

```bash
source deploy/config.sh
deploy/01_setup_project.sh                    # APIs, Firestore, service accounts, log metrics
deploy/02_deploy_catalog.sh                   # first build takes ~3-5 min
pip install google-cloud-firestore && python deploy/seed_firestore.py
deploy/03_deploy_v1.sh
```

Smoke test (the URLs are printed by the scripts):

```bash
CAT=$(gcloud run services describe catalog-service --region $REGION --format='value(status.url)')
RECO=$(gcloud run services describe recommendation-service --region $REGION --format='value(status.url)')
curl -s "$CAT/api/v1/products?limit=2"
curl -s -X POST "$CAT/api/v1/users/u42/events" -H "Content-Type: application/json" \
     -d '{"productId":"p001","type":"purchase"}'
curl -s "$RECO/api/v1/users/u42/recommendations?limit=3"
```

**Done when:** v1 answers on its public URL with kitchen picks that skip the Mug.

---

## Phase 5: v2 with real Gemini

1. In the Vertex AI pricing page, find `gemini-2.5-flash` and copy the input and output prices per 1M tokens into `PRICE_INPUT_PER_M` and `PRICE_OUTPUT_PER_M` in `deploy/config.sh`.
2. Optional: try real Gemini locally first, at a cost of a few cents:
   `GOOGLE_CLOUD_PROJECT=$PROJECT_ID AGENT_MODEL=gemini docker compose -f docker-compose.yml -f docker-compose.gemini.yml up --build`
3. Deploy v2 with no traffic: `deploy/04_deploy_v2.sh`. Call v2 on its **tag URL** (printed by the script) a few times.
4. Baseline: `deploy/canary.sh 10`, run the load test for 5 minutes against `$RECO`, then `deploy/report.sh 6`.
   Use the numbers to set **X** (p95 latency) and **Y** (cost per request) in `docs/canary-runbook.md`.

**Done when:** the runbook's criteria table has real numbers, and v2 shows `source: agent` with tokens and cost in the logs.

Phases 6 (canary + rollback demo) and 7 (report + slides) follow `docs/canary-runbook.md`.
