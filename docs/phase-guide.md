# Phase guide: from your laptop to the canary on Google Cloud

Each phase ends with a **"done when"** check. Run the commands from the project
folder, in macOS Terminal or WSL Ubuntu: they are the same. The **command log**
at the end records what we actually ran, session by session.

## Progress

| Phase | Status |
| --- | --- |
| 1. Verify locally (Claude's workspace, Docker) | done 2026-10-29 |
| 2. Your machine + GitHub | **done 2026-11-03**: github.com/Salsalata/coen424-project, CI green (test 33 s, docker 27 s) |
| 3. SwaggerHub | **done 2026-11-03** (unpublished until the Cloud Run URLs are in): https://app.swaggerhub.com/apis/concordiauniversity-6d6/product-recommendation-api/1.0.0 |
| 4. Google Cloud: catalog + v1 | **done 2026-11-05**: catalog + v1 live on Cloud Run, products in Firestore (URLs in the README) |
| 5. v2 with real Gemini | **in progress** (2026-11-20): v2 deployed at 0% (tag `agent-v2`), `gemini-3.5-flash-lite` on `global`; 10% baseline 100% correct, p95 2.1 s; X/Y set. Remaining: quality comparison |
| 6. Canary + rollback demo | not started |
| 7. Report + slides + rehearsal | not started |

---

## Phase 2: your machine + GitHub

First check the folder: hidden files present, and is it already a git repo?

```bash
ls -a                       # must show .github and .gitignore
git status 2>&1 | head -3   # "not a git repository" = fresh folder
git remote -v               # if it shows the old Online Boutique fork, stop and decide
python3 --version           # need 3.10 or newer (3.12 recommended)
```

On a Mac with an older Python: `brew install python@3.12`, then use `python3.12` instead of `python3` below.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r catalog-service/requirements.txt -r recommendation-service/requirements.txt \
            -r facade/requirements.txt -r requirements-dev.txt
(cd catalog-service && python -m pytest -q) && (cd recommendation-service && python -m pytest -q) \
  && (cd facade && python -m pytest -q) && python -m pytest -q tests          # 16, 23, 3, 3 passed

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

1. In the Vertex AI pricing page, find the pinned model (now `gemini-3.5-flash-lite`; `gemini-2.5-flash` was retired on Vertex AI on 2026-10-20) and copy the input and output prices per 1M tokens into `PRICE_INPUT_PER_M` and `PRICE_OUTPUT_PER_M` in `deploy/config.sh`.
2. Optional: try real Gemini locally first, at a cost of a few cents:
   `GOOGLE_CLOUD_PROJECT=$PROJECT_ID AGENT_MODEL=gemini docker compose -f docker-compose.yml -f docker-compose.gemini.yml up --build`
3. Deploy v2 with no traffic: `deploy/04_deploy_v2.sh`. Call v2 on its **tag URL** (printed by the script) a few times.
4. Baseline: `deploy/canary.sh 10`, run the load test for 5 minutes against `$RECO`, then `deploy/report.sh 6`.
   Use the numbers to set **X** (p95 latency) and **Y** (cost per request) in `docs/canary-runbook.md`.

**Done when:** the runbook's criteria table has real numbers, and v2 shows `source: agent` with tokens and cost in the logs.

Phases 6 (canary + rollback demo) and 7 (report + slides) follow `docs/canary-runbook.md`.

---

## Command log

What we actually ran, in order. Machine in brackets.

### 2026-10-29: Phase 1 (Claude's workspace, Linux + Docker)

| Command | What it does | Result |
| --- | --- | --- |
| `docker compose build` | builds the 4 images from their Dockerfiles | all 4 built (with a local stand-in base image; Docker Hub blocked there) |
| `docker compose up -d` | starts catalog, reco-v1, reco-v2, facade in the background | 4 containers up, ports 8080-8083 |
| `curl -s localhost:8080/api/v1/...` | calls the API through the facade | 200 / 201 / 400 / 404 / 415 as designed |
| `V2_PERCENT=10 docker compose up -d reco-v2 facade` | restarts v2 and the facade with 10% of traffic to v2 | split measured 10.2% |
| `python3 loadtest/loadtest.py ... --duration 40` | the same load at every canary step | 0 errors, 100% correct for clients |
| `docker compose logs ... \| python3 scripts/split_report.py` | per-version numbers from the log lines | see `docs/canary-runbook.md` |
| `FAULT_MODE=invalid_ids V2_PERCENT=25 ...` | breaks v2 on purpose | v2 0% correct, 1997/1997 fell back |
| `V2_PERCENT=0 ...` | rollback | 100% to v1 |
| `docker compose down` | stops and removes the containers | |

### 2026-10-29: Phase 2 (Salah's Mac)

| Command | What it does | Result |
| --- | --- | --- |
| unzip `reco-api.zip` into `coen424-project`, `ls` | puts the project on the Mac | all folders present |
| `python3 -m venv .venv`, `pip install -r ...`, `pytest -q` | create the environment, install, run tests | **error**: `No module named 'google.genai'`. The traceback showed the global Python 3.14 running, not `.venv` (plain `pytest` found a global copy). Fix: always `python -m pytest`, and check that `pip install` finished; if a package fails on 3.14, rebuild `.venv` with `python3.12` |
| `python -m pytest -q` (in each folder) | runs the tests with the venv's Python 3.14 | **15, 22, 3, 3 passed**. One harmless DeprecationWarning from inside google-genai on 3.14 |
| old `coen424-project` folder deleted; new folder opened in VS Code | fresh start, no old git history | not a git repo yet |
| `docker compose up --build -d` + 3 `curl` calls + `docker compose down` | builds the 4 images with the real `python:3.12-slim`, starts them, calls the API, stops them | **all 4 built (17 s) and started**; products list, 201 event, kitchen picks without the Mug |
| `git init -b main`, `git status --short`, `git add .` | makes the folder a repo; checks `.venv` is not listed | 15 entries, no `.venv` |
| `git commit -m "..."` | first snapshot, with the `Co-Authored-By` line | `5fd3275`, 71 files. Tip: `-m` with an opening quote and no closing quote leaves zsh waiting at `dquote>`; press Ctrl+C and retype |
| `git remote add origin https://github.com/Salsalata/coen424-project` / `git push -u origin main` | links and uploads | **pushed**; CI started |
| `git push` (docs commit `40a6c8d`) | second push | **CI: all checks passed**: `ci / test` 33 s, `ci / docker` 27 s |
| `cp ~/Downloads/phase-guide.md .` (by mistake into the top folder) then `mv phase-guide.md docs/phase-guide.md` | `cp`/`mv` copy or move a file; the destination path decides where it lands | fixed |
| SwaggerHub: Create New → Import and Document API → `openapi.yaml` | puts the contract online as browsable docs (REST lecture, step 6: document) | imported as `product-recommendation-api` 1.0.0; first private, then switched to public with the lock icon |

### 2026-11-03 / 11-05: Phase 4 (Salah's Mac)

| Command | What it does | Result |
| --- | --- | --- |
| `gcloud init` → "Create a new project" `coen424-project` | logs in and tries to create a project | **409 ALREADY_EXISTS**: project IDs are global across all users; config stayed on the old `asn1-coen424` |
| `gcloud projects create coen424-reco-sal --name="COEN424 Reco API"` | creates our project | created |
| `gcloud config set project coen424-reco-sal` | makes it the default | checked with `gcloud config list --format="value(core.project)"` |
| `gcloud auth application-default login` | login for local Python scripts | first try: **"cloud-platform scope not consented"**; tick every box on the consent page and retry |
| `gcloud billing accounts list` | lists billing accounts | 1 account, `OPEN True` |
| `sed -i '' 's/REPLACE-with-your-project-id/coen424-reco-sal/' deploy/config.sh` | sets our project in the deploy config (macOS sed needs `''`) | |
| `source deploy/config.sh`; `BILLING_ACCOUNT=$(gcloud billing accounts list --filter=open=true --format="value(name.basename())" --limit=1)` | loads our settings; stores the billing account id in a variable | id found |
| `deploy/00_budget.sh` (first run) | links billing, enables the Budgets API, creates the budget | link and API OK; **budget INVALID_ARGUMENT**: `100USD` but the account is in CAD. Fix: `--budget-amount=100` (account's own currency) |
| `source deploy/config.sh`; `BILLING_ACCOUNT=$(gcloud billing accounts list --filter=open=true --format="value(name.basename())" --limit=1)` | loads settings; saves the billing account ID in a variable (kept out of the repo) | found |
| `deploy/00_budget.sh` (first try, `--budget-amount=100USD`) | links billing, enables the Budgets API, creates the budget | link + API OK; **budget: INVALID_ARGUMENT**, because the account is in **CAD** and the currency must match |
| `deploy/00_budget.sh` (fixed: `--budget-amount=100`, no currency) | same | **budget `coen424-reco-budget` created: 100 CAD**, alerts 25/50/75/90% |
| `deploy/01_setup_project.sh` | step 1/4 enabled the APIs; step 2/4 creates Firestore | **seemed stuck at 2/4**: the script hid that command's output (`2>/dev/null`), so a prompt or a slow create was invisible. Script fixed to check first and show output |
| `gcloud firestore databases create --location=northamerica-northeast1 --type=firestore-native` | the Firestore step on its own, output visible | the hidden question was **"API firestore.googleapis.com not enabled… enable and retry? (y/N)"** (step 1 had just enabled it; it hadn't propagated yet). Answered `y`: **database `(default)` created**, FIRESTORE_NATIVE, Montréal, `freeTier: true` |
| `deploy/01_setup_project.sh` (re-run) | APIs, Firestore (skipped: exists), 2 service accounts + roles, 2 log metrics | all 4 steps done |
| `gcloud firestore databases list` / `gcloud iam service-accounts list` / `gcloud logging metrics list` | checks | `(default)` Montréal FIRESTORE_NATIVE; `catalog-sa`, `reco-sa` (+ Google's automatic `…-compute@developer` account); `reco_v2_invalid`, `reco_v2_requests` |
| `gcloud projects add-iam-policy-binding … --role=roles/run.builder` | lets Google's build account (`…-compute@developer`) build from source | done before the first deploy |
| `deploy/02_deploy_catalog.sh` | Cloud Build builds the image; Cloud Run runs it | **deployed**: `https://catalog-service-187893550568.northamerica-northeast1.run.app`. But `/healthz` returned **Google's** 404: Cloud Run reserves paths ending in `z`. Renamed to **`/health`** everywhere |
| `gcloud auth application-default login` (all boxes ticked) / `python deploy/seed_firestore.py` | local login; writes the products | **Seeded 24 products** into Firestore |
| `deploy/03_deploy_v1.sh` | deploys v1 with tag `v1` | **failed**: `tag: must be at least 3 characters long`. Tags renamed **`rules-v1`** / **`agent-v2`** in `03`, `04` and `canary.sh` |
| `unzip -o ~/Downloads/reco-api-update.zip -d .`; tests; `git add -A`; commit `15f3b0b`; `git push` | updates every file in place, then saves and uploads | 15/22/3/3 passed; pushed. A stray sed backup `deploy/config.shcoen424-reco-sal` got committed too: removed with `git rm` |
| `deploy/02_deploy_catalog.sh` (again) | catalog revision with `/health` | `{"status":"ok"}` |
| `deploy/03_deploy_v1.sh` | recommendation-service, tag `rules-v1` | **live**: https://recommendation-service-187893550568.northamerica-northeast1.run.app, 100% on `rules-v1`; tag URL `https://rules-v1---recommendation-service-pxxbzokq2a-nn.a.run.app` |
| `curl` products / POST event / GET recommendations on the live URLs | end-to-end test in the cloud | products from Firestore; event id `dYBagKBu…` (a Firestore auto id); recommendations: Chef Knife, Bamboo Glass Jar, Cutting Board, without the Mug |
| (Claude) real URLs in `openapi.yaml` + README; CORS headers in both services (+2 tests) | lets SwaggerHub's "Try it out" call the live API | 16, 23, 3, 3 tests pass |

### 2026-11-20: Phase 5 start (teammate's MacBook, macOS)

| Command | What it does | Result |
| --- | --- | --- |
| `gcloud run services list --region northamerica-northeast1` | read-only check of the new `roles/editor` access | both services listed; last deployed 2026-11-06, no v2 yet |
| `python probe_model.py gemini-3.8-flash global` (our `GeminiModel`, 2 tiny requests) | tool-call turn, then a tool-result turn | **OK**: no change needed for `temperature=0` or function-response ids |
| same, `us-central1` and `northamerica-northeast1` | same probe in other locations | **404 NOT_FOUND**: model only reachable on `global` |
| (Claude) `GEMINI_MODEL=gemini-3.8-flash`, `VERTEX_LOCATION=global` in `deploy/config.sh`, `config.py`, `docker-compose.gemini.yml` | `gemini-2.5-flash` retired on Vertex AI 2026-10-20 (per Google's model-versions page) | recommendation-service tests pass |
| (Claude) `PRICE_INPUT_PER_M=0.75`, `PRICE_OUTPUT_PER_M=3.75` in `deploy/config.sh` | USD per 1M tokens, read from the Vertex AI pricing page by the teammate | cost_usd in the logs will use these |
| `docker compose -f docker-compose.yml -f docker-compose.gemini.yml up --build -d` + `GET localhost:8083/…/recommendations` (local smoke test, real Gemini) | first try: v2 used `gemini-2.5-flash` @ `us-central1` | **404, fallback**: `source: fallback, valid: false`. Cause: the shell still had `GEMINI_MODEL`/`VERTEX_LOCATION`/`PRICE_*` exported from an earlier `source deploy/config.sh`, which override defaults (`${VAR:-default}`). Fix: `unset` them, re-source, recreate |
| same, after the fix: 1st request | cold request | **timed out after 8.0 s → fallback** (`valid: false`) |
| same: 2nd request | warm request | **OK**: `model gemini-3.8-flash`, 3 turns (`get_user_events`, `search_products`, `submit_recommendations`), 1428 in / 414 out tokens, `source: agent`, `valid: true`, **6.6 s** (close to the 8 s deadline; `cost_usd` is 0 locally because compose passes no prices) |
| `AGENT_TIMEOUT_SECONDS=30 deploy/04_deploy_v2.sh` then 5 requests on the `agent-v2` tag URL | measure v2 without the 8 s cut-off | 2 succeeded (4-5 turns, **15.3 s and 20.7 s**, ~$0.006), then 4 timed out at 30 s. Found: a timed-out agent kept calling Gemini in the background (unlogged spend) |
| (Claude) agent stops at the deadline; per-call HTTP timeout; `thinking_level=LOW`; prompt asks for events + products in one turn; tool results carry the call `id` | make v2 faster and stop abandoned agents | tests: 16, 25 (+2 new), 3, 3 pass |
| `python measure_agent.py DEFAULT 3` / `LOW 3` (laptop, real Gemini, live catalog read-only) | compare thinking levels | both 2 turns. DEFAULT: 8.0-11.9 s, $0.004-0.007. **LOW: 2.7-4.6 s, $0.0013** |
| `AGENT_TIMEOUT_SECONDS=10 deploy/04_deploy_v2.sh` then 5 requests on the tag URL | v2 with the changes, 0% traffic | **all 5 `source: agent`, `valid: true`, 2 turns**; first (cold) 6.5 s / $0.0038, then **2.7-3.1 s / ~$0.0013**. Timeout default raised to 10 s in `04_deploy_v2.sh`, `config.py`, `docker-compose.yml` |
| `canary.sh 10` + `loadtest.py ... --duration 180 --concurrency 4` + `report.sh 5` (first try) | 10% baseline | typo `--reco-url "RECO"` (no `$`): every request failed locally, nothing reached the cloud; 20 shoppers seeded in Firestore |
| same, fixed | 10% baseline with `gemini-3.8-flash` | v1: 874 req, p95 86 ms, 100% correct. **v2: 90 req, 62% correct, 34 fallbacks, p95 = 10,059 ms (the timeout)**, $0.0010/req. Reasons: 26 x `504 DEADLINE_EXCEEDED` from Gemini, 8 x timeout, 1 x invalid answer (empty product ids, caught by the validator). `canary.sh 0` after |
| `measure_agent.py --runs 4 --parallel 1` / `--parallel 4` (laptop, live catalog read-only) | is it concurrency or the model? | `gemini-3.8-flash`: 4.1-24.6 s alone; **3 of 4 failed (504) with 4 at once**. `gemini-3.5-flash-lite`: 1.5-2.5 s alone, 2.6-2.8 s with 4 at once, all valid, **but picks were just the most popular products** (ignored history) |
| (Claude) system prompt: explicit rule to personalise from the user's activity | smaller models follow instructions literally | tests pass; Flash-Lite with 4 at once: 2.9-3.1 s, all valid, kitchen picks with reasons mentioning the Mug |
| `measure_agent.py --model gemini-3.5-flash` / `gemini-4-hydrogen`, 4 at once | other candidates | 3.5 Flash: 5.7-13.0 s, valid, best reasons, ~5x the output tokens. 4 Hydrogen: **429 RESOURCE_EXHAUSTED** on all 4 (quota) |
| (Claude) `GEMINI_MODEL=gemini-3.5-flash-lite`, prices **0.30 / 2.50** USD per 1M tokens (`deploy/config.sh`, `config.py`, `docker-compose.gemini.yml`) | chosen: fast, stable under concurrency, personalised, cheapest | redeploy + new 10% baseline next |
| `deploy/04_deploy_v2.sh` (after `unset` + re-`source`), warm-up, `canary.sh 10`, `loadtest.py --duration 180 --concurrency 4`, `report.sh 5`, `canary.sh 0` | 10% baseline with `gemini-3.5-flash-lite` | **v2: 248 req (9.2%), 100% correct, 0 fallbacks, 0 errors, p95 2,069 ms, $0.00084/req**; v1: 2,454 req, p95 79 ms. Total v2 model cost $0.21 |
| (Claude) X = 4,000 ms and Y = $0.002 in `docs/canary-runbook.md`, with the baseline table | thresholds fixed before the next canary steps | Phase 5 done except the quality comparison |

### 2026-11-21: Phase 6 cloud canary (teammate's MacBook)

| Command | What it does | Result |
| --- | --- | --- |
| `deploy/canary.sh 100` + `loadtest.py --duration 180 --concurrency 4 --out step-100.json` + `report.sh 5` | full promotion | **failed 2 criteria → rolled back**: v2 p95 **4,874 ms** (> X = 4,000) and correct **97.83%** (< 99%, 7 of 322 fell back); 0 errors; $0.00082/req. Clients: 0 errors, 100% correct (p99 8.7 s). Throughput fell to 1.8 req/s (every request waits on Gemini) |
| `FAULT_MODE=invalid_ids deploy/04_deploy_v2.sh` → `canary.sh 25` → load 180 s → `report.sh 5` → `canary.sh 0` → `FAULT_MODE=none deploy/04_deploy_v2.sh` | **rollback demo** | v2 25.4% of 1,112 requests, **correct 0%, 282 of 282 fell back**; clients **0 errors, 100% correct**. Rolled back to v1 100%; healthy v2 redeployed as revision `00020` at 0%. 2 of the failures were real `504 DEADLINE_EXCEEDED` from Gemini (8.6 s, 9.3 s), not the injected fault |
| (Claude) `gcloud logging read` per step window + `scripts/split_report.py` | per-version numbers for 10/25/50/100% (the `step-*.json` files are client-side only) | v2 correct: 10% **99.58%**, 25% **94.76%** (p95 4,984 ms), 50% **98.83%**, 100% **97.84%**. Failures are almost all Gemini `504 DEADLINE_EXCEEDED`. By the runbook the canary should have stopped at 25%; table in `docs/canary-runbook.md` |

| (Claude) retry fix: one Gemini call is cut off after `GEMINI_CALL_TIMEOUT_SECONDS=4` (the SDK sends it to Google as `X-Server-Timeout`, so the 504s were Google enforcing our old 10 s per-call limit) and retried once (`GEMINI_CALL_RETRIES=1`) if ≥ 2 s remain before the 10 s deadline; 500/503/504 and network timeouts only; new log field `model_retries` | turn the rare hanging Gemini calls into successful retries | tests: 16, 30 (+5 new), 3, 3 pass |
