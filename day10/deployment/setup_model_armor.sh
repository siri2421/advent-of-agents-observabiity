#!/usr/bin/env bash
# ==============================================================================
# Advent of Agents Season 3 - Day 10: Setup Model Armor
# Project: siri-adventofagents | Region: us-central1
# ==============================================================================

set -euo pipefail

export PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-siri-adventofagents}"
export LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
export TEMPLATE_ID="agent-prompt-shield"

echo "=== [1/3] Target Project Configuration ==="
echo "Project ID: $PROJECT_ID"
echo "Location:   $LOCATION"
echo "Template:   $TEMPLATE_ID"
echo ""

echo "=== [2/3] Enabling Required APIs ==="
gcloud services enable \
  modelarmor.googleapis.com \
  networkservices.googleapis.com \
  aiplatform.googleapis.com \
  logging.googleapis.com \
  --project="$PROJECT_ID"

echo "=== [3/3] Creating / Verifying Model Armor Template ==="
if gcloud model-armor templates describe "$TEMPLATE_ID" --project="$PROJECT_ID" --location="$LOCATION" >/dev/null 2>&1; then
  echo "Template [$TEMPLATE_ID] already exists and is active."
else
  gcloud model-armor templates create "$TEMPLATE_ID" \
    --project="$PROJECT_ID" \
    --location="$LOCATION" \
    --pi-and-jailbreak-filter-settings-enforcement=enabled \
    --pi-and-jailbreak-filter-settings-confidence-level=medium-and-above \
    --malicious-uri-filter-settings-enforcement=enabled
  echo "Template [$TEMPLATE_ID] created successfully."
fi

echo ""
echo "=== Model Armor Setup Complete! ==="
gcloud model-armor templates describe "$TEMPLATE_ID" \
  --project="$PROJECT_ID" \
  --location="$LOCATION" \
  --format="yaml(name,filterConfig.piAndJailbreakFilterSettings)"
