"""Model Armor Client Helper using gcloud / ADC access token."""

import os
import json
import subprocess
import requests

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "siri-adventofagents")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
TEMPLATE_ID = os.getenv("MODEL_ARMOR_TEMPLATE_ID", "agent-prompt-shield")

def get_access_token() -> str:
    """Retrieves access token via gcloud or ADC."""
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        if token:
            return token
    except Exception:
        pass
    
    import google.auth
    from google.auth.transport.requests import Request
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())
    return creds.token

def sanitize_text(text: str) -> dict:
    """Inspects text using Model Armor template in Google Cloud."""
    token = get_access_token()
    url = (
        f"https://modelarmor.{LOCATION}.rep.googleapis.com/v1/"
        f"projects/{PROJECT_ID}/locations/{LOCATION}/templates/{TEMPLATE_ID}:sanitizeUserPrompt"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "userPromptData": {
            "text": text
        }
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    res = data.get("sanitizationResult", {})
    match_found = (res.get("filterMatchState") == "MATCH_FOUND")
    
    pi_filter = res.get("filterResults", {}).get("pi_and_jailbreak", {}).get("piAndJailbreakFilterResult", {})
    confidence = pi_filter.get("confidenceLevel", "NONE")
    
    return {
        "match_found": match_found,
        "confidence": confidence,
        "filter_type": "PI_AND_JAILBREAK" if match_found else "NONE",
        "raw_result": res
    }

if __name__ == "__main__":
    from pr_data import POISONED_PR_42, CLEAN_PR_10
    print("=== Testing Clean PR ===")
    res_clean = sanitize_text(CLEAN_PR_10["diff"])
    print(f"Match Found: {res_clean['match_found']} | Confidence: {res_clean['confidence']}")

    print("\n=== Testing Poisoned PR-42 ===")
    res_poison = sanitize_text(POISONED_PR_42["diff"])
    print(f"Match Found: {res_poison['match_found']} | Filter: {res_poison['filter_type']} | Confidence: {res_poison['confidence']}")
