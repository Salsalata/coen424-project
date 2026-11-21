# Shared settings for every deploy script. Edit PROJECT_ID once; the rest has defaults.
# Load it in your terminal with:  source deploy/config.sh
export PROJECT_ID="${PROJECT_ID:-coen424-reco-sal}"
export REGION="${REGION:-northamerica-northeast1}"          # Montreal, as in the REST lecture (slide 34)
export VERTEX_LOCATION="${VERTEX_LOCATION:-global}"          # probed 2026-11-20: the Gemini 3.x models answered on "global" only (404 in us-central1 and northamerica-northeast1)
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash-lite}" # chosen 2026-11-21: ~3 s and stable with 4 concurrent requests; 3.8-flash gave 504s under load (see docs/phase-guide.md)
# USD per 1M tokens for GEMINI_MODEL, copied from the Agent Platform pricing page (for the cost report)
export PRICE_INPUT_PER_M="${PRICE_INPUT_PER_M:-0.30}"
export PRICE_OUTPUT_PER_M="${PRICE_OUTPUT_PER_M:-2.50}"

export CATALOG_SERVICE=catalog-service
export RECO_SERVICE=recommendation-service
export CATALOG_SA="catalog-sa@${PROJECT_ID}.iam.gserviceaccount.com"
export RECO_SA="reco-sa@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true
