# Shared settings for every deploy script. Edit PROJECT_ID once; the rest has defaults.
# Load it in your terminal with:  source deploy/config.sh
export PROJECT_ID="${PROJECT_ID:-coen424-reco-sal}"
export REGION="${REGION:-northamerica-northeast1}"          # Montreal, as in the REST lecture (slide 34)
export VERTEX_LOCATION="${VERTEX_LOCATION:-global}"          # probed 2026-11-20: gemini-3.8-flash answers on "global" only (404 in us-central1 and northamerica-northeast1)
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.8-flash}"      # gemini-2.5-flash was retired on Vertex AI on 2026-10-20
# USD per 1M tokens for GEMINI_MODEL, copied from the Agent Platform pricing page (for the cost report)
export PRICE_INPUT_PER_M="${PRICE_INPUT_PER_M:-0.75}"
export PRICE_OUTPUT_PER_M="${PRICE_OUTPUT_PER_M:-3.75}"

export CATALOG_SERVICE=catalog-service
export RECO_SERVICE=recommendation-service
export CATALOG_SA="catalog-sa@${PROJECT_ID}.iam.gserviceaccount.com"
export RECO_SA="reco-sa@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true
