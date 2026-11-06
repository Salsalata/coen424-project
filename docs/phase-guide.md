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
| 4. Google Cloud: catalog + v1 | in progress: project `coen424-reco-sal`, billing linked, budget 100 CAD, APIs + Firestore + service accounts + log metrics ready; next: `02_deploy_catalog.sh` |
| 5. v2 with real Gemini | not started |
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
  && (cd facade && python -m pytest -q) && python -m pytest -q tests          # 15, 22, 3, 3 passed

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
