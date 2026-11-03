#!/usr/bin/env bash
# Step 0, BEFORE any deployment (project requirement 5): a $100 budget with
# e-mail alerts at 25/50/75/90% of actual spend, limited to this project.
#
# Usage:  BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX deploy/00_budget.sh
#   find the id with:  gcloud billing accounts list
#
# Why exclude-all-credits: with the $300 free trial, spend is paid by credits,
# so a budget that subtracts credits would stay near $0 and never alert. We want
# to see the real (gross) cost of what we run.
# A budget only WARNS; it never stops services. Watching the numbers is our job.
set -euo pipefail
source "$(dirname "$0")/config.sh"
: "${BILLING_ACCOUNT:?set BILLING_ACCOUNT (see: gcloud billing accounts list)}"

gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
gcloud services enable billingbudgets.googleapis.com

gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT" \
  --display-name="coen424-reco-budget" \
  --budget-amount=100USD \
  --filter-projects="projects/$PROJECT_ID" \
  --credit-types-treatment=exclude-all-credits \
  --threshold-rule=percent=0.25 \
  --threshold-rule=percent=0.50 \
  --threshold-rule=percent=0.75 \
  --threshold-rule=percent=0.90

echo "Budget created. Alerts go to the billing account's admins by e-mail."
gcloud billing budgets list --billing-account="$BILLING_ACCOUNT" \
  --format="table(displayName, amount.specifiedAmount.units:label=USD)"
