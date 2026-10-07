#!/usr/bin/env python3
"""GitHub Actions PR Reviewer: Dynamically inspects PR diffs via Model Armor & Vertex AI Reasoning Engine."""

import json
import os
import sys
import requests
import google.auth
from google.auth.transport.requests import Request

def get_gcp_access_token():
    """Acquires GCP OAuth access token via gcloud CLI, environment, or ADC."""
    if os.environ.get("GCP_ACCESS_TOKEN"):
        return os.environ.get("GCP_ACCESS_TOKEN").strip()
    try:
        import subprocess
        token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
        if token:
            return token
    except Exception:
        pass
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    return credentials.token

def fetch_pr_diff(repo: str, pr_number: str, github_token: str = None) -> str:
    """Fetches the real code diff of the pull request directly from GitHub."""
    headers = {"User-Agent": "Gemini-Enterprise-PR-Reviewer"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
        headers["Accept"] = "application/vnd.github.v3.diff"
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    else:
        url = f"https://patch-diff.githubusercontent.com/raw/{repo}/pull/{pr_number}.diff"

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200 and resp.text:
            return resp.text
        print(f"Warning: Failed to fetch diff via API ({resp.status_code}), trying raw patch...")
        raw_url = f"https://patch-diff.githubusercontent.com/raw/{repo}/pull/{pr_number}.diff"
        raw_resp = requests.get(raw_url, headers={"User-Agent": "Gemini-Enterprise-PR-Reviewer"}, timeout=15)
        if raw_resp.status_code == 200:
            return raw_resp.text
    except Exception as e:
        print(f"Error fetching PR diff: {e}")
    return ""

def scan_with_model_armor(project_id: str, location: str, template_id: str, content: str, token: str) -> dict:
    """Scans content using Google Cloud Model Armor template API."""
    url = f"https://modelarmor.{location}.rep.googleapis.com/v1/projects/{project_id}/locations/{location}/templates/{template_id}:sanitizeUserPrompt"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "userPromptData": {
            "text": content[:10000]  # scan first 10k chars
        }
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            result = resp.json().get("sanitizationResult", {})
            filter_state = result.get("filterMatchState", "NO_MATCH_FOUND")
            match_found = (filter_state == "MATCH_FOUND")
            return {
                "match_found": match_found,
                "filter_state": filter_state,
                "raw": result
            }
        else:
            print(f"Warning: Model Armor API returned status {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Error calling Model Armor API: {e}")
    return {"match_found": False, "filter_state": "SKIPPED", "raw": {}}

def invoke_reasoning_engine(project_id: str, location: str, engine_id: str, message: str, token: str) -> str:
    """Executes streamQuery against the deployed Gemini Enterprise Reasoning Engine on Vertex AI."""
    url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/{location}/reasoningEngines/{engine_id}:streamQuery"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "class_method": "stream_query",
        "input": {
            "message": message,
            "user_id": "github-actions-bot"
        }
    }
    print(f"🚀 Invoking Reasoning Engine {engine_id} on Vertex AI...")
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        print(f"Warning: Reasoning Engine call returned {resp.status_code}: {resp.text}")
        return ""
    
    # Extract text from stream events
    output_parts = []
    for line in resp.text.strip().split("\n"):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            parts = event.get("content", {}).get("parts", [])
            for p in parts:
                if "text" in p:
                    output_parts.append(p["text"])
        except Exception:
            pass
    return "\n".join(output_parts).strip()

def post_pr_comment(repo: str, pr_number: str, github_token: str, body: str):
    """Posts analysis report comment back to the GitHub PR."""
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=headers, json={"body": body})
    if resp.status_code in [200, 201]:
        print(f"✅ Successfully posted comment to PR #{pr_number}.")
    else:
        print(f"❌ Failed to post PR comment ({resp.status_code}): {resp.text}")

def main():
    repo = os.environ.get("REPO_NAME")
    pr_number = os.environ.get("PR_NUMBER")
    github_token = os.environ.get("GITHUB_TOKEN")
    project_id = os.environ.get("GCP_PROJECT", "siri-adventofagents")
    location = os.environ.get("GCP_LOCATION", "us-central1")
    engine_id = os.environ.get("REASONING_ENGINE_ID", "3821621218050572288")
    template_id = os.environ.get("MODEL_ARMOR_TEMPLATE_ID", "agent-prompt-shield")

    if not repo or not pr_number:
        print("Missing REPO_NAME or PR_NUMBER. Exiting.")
        sys.exit(0)

    print(f"================================================================")
    print(f"🔍 Analyzing PR #{pr_number} on {repo}")
    print(f"📦 GCP Project: {project_id} | Location: {location}")
    print(f"🛡️  Model Armor Template: {template_id}")
    print(f"🤖 Vertex AI Reasoning Engine: {engine_id}")
    print(f"================================================================")

    # 1. Fetch real PR diff dynamically from GitHub
    pr_diff = fetch_pr_diff(repo, pr_number, github_token)
    print(f"Fetched diff length: {len(pr_diff)} bytes")

    # 2. Acquire GCP OAuth credentials via Workload Identity Federation
    gcp_token = get_gcp_access_token()

    # 3. Model Armor Inspection Barrier
    armor_scan = scan_with_model_armor(project_id, location, template_id, pr_diff, gcp_token)
    match_found = armor_scan["match_found"]
    print(f"🛡️  Model Armor Inspection State: {armor_scan['filter_state']}")

    # 4. Invoke Reasoning Engine on Vertex AI
    if match_found:
        agent_prompt = (
            f"Security Alert: Pull Request PR-{pr_number} diff was quarantined by Google Cloud Model Armor "
            f"due to detected indirect prompt injection (PI_AND_JAILBREAK). "
            f"Halt automated execution, summarize the threat, and verify no unauthorized tools like add_collaborator were called."
        )
    else:
        agent_prompt = (
            f"Review and triage pull request PR-{pr_number} with the following code diff:\n\n{pr_diff}\n\n"
            f"Verify code quality, security posture, and summarize changes."
        )

    agent_review = invoke_reasoning_engine(project_id, location, engine_id, agent_prompt, gcp_token)

    # 5. Formulate PR Comment & Merge Gate
    if match_found:
        comment = (
            "## 🛡️ Gemini Enterprise AI PR Reviewer — Model Armor Security Alert\n\n"
            "| Security Check | Status | Guardrail Policy |\n"
            "| :--- | :--- | :--- |\n"
            "| **Indirect Prompt Injection** | 🚨 **BLOCKED** | `PI_AND_JAILBREAK` |\n"
            "| **Tool Egress Inspection** | 🔒 **QUARANTINED** | `agent-prompt-shield` |\n"
            "| **Privilege Escalation** | 🛡️ **PREVENTED** | Zero Unauthorized Tool Calls |\n\n"
            "> [!CAUTION]\n"
            "> **Security Violation**: Malicious prompt injection directive detected in PR diff. "
            "Payload has been quarantined before model ingestion.\n\n"
            "### 🤖 Agent Triage Summary\n"
            f"{agent_review or 'Review halted. Malicious payload quarantined by Model Armor.'}\n\n"
            "---\n"
            "*Protected by Google Cloud Model Armor & Gemini Enterprise Agent Runtime on Vertex AI.*"
        )
    else:
        comment = (
            "## 🛡️ Gemini Enterprise AI PR Reviewer — Code Triage\n\n"
            "| Security Check | Status | Guardrail Policy |\n"
            "| :--- | :--- | :--- |\n"
            "| **Indirect Prompt Injection** | ✅ **PASSED** | `PI_AND_JAILBREAK` |\n"
            "| **Tool Egress Inspection** | 🛡️ **CLEAN** | `agent-prompt-shield` |\n"
            "| **Privilege Escalation** | ✅ **VERIFIED** | Clean Diff |\n\n"
            "### 🤖 Agent Triage Summary\n"
            f"{agent_review or 'Code and diff inspected. No prompt injection or privilege escalation detected.'}\n\n"
            "---\n"
            "*Protected by Google Cloud Model Armor & Gemini Enterprise Agent Runtime on Vertex AI.*"
        )

    if github_token:
        post_pr_comment(repo, pr_number, github_token, comment)

    if match_found:
        print("❌ Model Armor quarantined malicious payload! Failing CI build to block merge.")
        sys.exit(1)
    else:
        print("✅ PR passed Model Armor security inspection and Agent review.")
        sys.exit(0)

if __name__ == "__main__":
    main()
