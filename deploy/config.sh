# Shared settings for every deploy script. Edit PROJECT_ID once; the rest has defaults.
# Load it in your terminal with:  source deploy/config.sh
export PROJECT_ID="${PROJECT_ID:-coen424-reco-sal}"
export REGION="${REGION:-northamerica-northeast1}"          # Montreal, as in the REST lecture (slide 34)
export VERTEX_LOCATION="${VERTEX_LOCATION:-us-central1}"     # where Gemini is called; check model availability
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"      # pinned version; confirm it is offered in your region
# USD per 1M tokens for GEMINI_MODEL, copied from the Vertex AI pricing page (for the cost report)
export PRICE_INPUT_PER_M="${PRICE_INPUT_PER_M:-0}"
export PRICE_OUTPUT_PER_M="${PRICE_OUTPUT_PER_M:-0}"

export CATALOG_SERVICE=catalog-service
export RECO_SERVICE=recommendation-service
export CATALOG_SA="catalog-sa@${PROJECT_ID}.iam.gserviceaccount.com"
export RECO_SA="reco-sa@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID" >/dev/null 2>&1 || true
