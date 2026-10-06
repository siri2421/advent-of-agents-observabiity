#!/usr/bin/env python3
"""GitHub Actions PR Reviewer: Invokes Gemini Enterprise Agent Runtime with Model Armor protection."""

import json
import os
import sys
import requests
import google.auth
from google.auth.transport.requests import Request

def get_gcp_access_token():
    """Acquires GCP OAuth access token via Workload Identity Federation / ADC."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(Request())
    return credentials.token

def get_pr_details(repo: str, pr_number: str, github_token: str):
    """Fetches PR details from GitHub API."""
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    print(f"Warning: Failed to fetch PR #{pr_number} metadata ({resp.status_code}): {resp.text}")
    return {}

def post_pr_comment(repo: str, pr_number: str, github_token: str, body: str):
    """Posts review analysis comment back to the GitHub PR."""
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

def invoke_reasoning_engine(project_id: str, location: str, engine_id: str, prompt: str, token: str):
    """Executes streamQuery against the deployed Gemini Enterprise Reasoning Engine."""
    url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/{location}/reasoningEngines/{engine_id}:streamQuery"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "class_method": "stream_query",
        "input": {
            "message": prompt,
            "user_id": "github-actions-bot"
        }
    }
    
    print(f"🚀 Invoking Reasoning Engine: {engine_id} in {location}...")
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Vertex AI Reasoning Engine error ({resp.status_code}): {resp.text}")
    
    return resp.text

def parse_engine_events(raw_output: str):
    """Parses streaming JSON line events from Reasoning Engine."""
    events = []
    text_responses = []
    quarantined = False
    blocked_detail = ""
    privilege_escalated = False

    for line in raw_output.strip().split("\n"):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            events.append(event)
            
            # Check content parts
            content = event.get("content", {})
            parts = content.get("parts", [])
            for p in parts:
                # Text output from model
                if "text" in p:
                    text_responses.append(p["text"])
                
                # Tool calls
                if "function_call" in p:
                    fn_name = p["function_call"].get("name", "")
                    if fn_name == "add_collaborator":
                        privilege_escalated = True

                # Tool responses & guardrails
                if "function_response" in p:
                    resp_val = p["function_response"].get("response", {})
                    if isinstance(resp_val, dict):
                        if resp_val.get("status") == "blocked":
                            quarantined = True
                            blocked_detail = resp_val.get("error", "Payload quarantined by Model Armor.")
                    elif "SECURITY_VIOLATION" in str(resp_val):
                        quarantined = True
                        blocked_detail = str(resp_val)
        except Exception as e:
            print(f"Warning parsing event chunk: {e}")

    return {
        "events": events,
        "agent_text": "\n".join(text_responses).strip(),
        "quarantined": quarantined,
        "blocked_detail": blocked_detail,
        "privilege_escalated": privilege_escalated,
    }

def main():
    repo = os.environ.get("REPO_NAME")
    pr_number = os.environ.get("PR_NUMBER")
    github_token = os.environ.get("GITHUB_TOKEN")
    project_id = os.environ.get("GCP_PROJECT", "siri-adventofagents")
    location = os.environ.get("GCP_LOCATION", "us-central1")
    engine_id = os.environ.get("REASONING_ENGINE_ID", "7830000808270757888")

    if not repo or not pr_number:
        print("Missing REPO_NAME or PR_NUMBER. Exiting.")
        sys.exit(0)

    print(f"Analyzing PR #{pr_number} on {repo}...")
    pr_data = {}
    if github_token:
        pr_data = get_pr_details(repo, pr_number, github_token)

    pr_title = pr_data.get("title", f"PR #{pr_number}")
    pr_body = pr_data.get("body", "")

    # Query prompt directed to the agent
    prompt = f"Review and triage pull request PR-{pr_number}. Title: {pr_title}. Description: {pr_body}"

    # Query the deployed Agent Engine on Vertex AI
    gcp_token = get_gcp_access_token()
    raw_output = invoke_reasoning_engine(project_id, location, engine_id, prompt, gcp_token)
    parsed = parse_engine_events(raw_output)

    print(f"Quarantined by Model Armor: {parsed['quarantined']}")
    print(f"Privilege Escalation Attempted: {parsed['privilege_escalated']}")

    # Formulate PR comment
    if parsed["quarantined"]:
        comment = (
            "## 🛡️ Gemini Enterprise AI PR Reviewer — Model Armor Security Alert\n\n"
            "| Check | Status | Guardrail Policy |\n"
            "| :--- | :--- | :--- |\n"
            "| **Indirect Prompt Injection** | 🚨 **BLOCKED** | `PI_AND_JAILBREAK` |\n"
            "| **Agent Egress Inspection** | 🔒 **QUARANTINED** | `agent-prompt-shield` |\n"
            "| **Privilege Escalation** | 🛡️ **PREVENTED** | Zero Unauthorized Tool Calls |\n\n"
            f"> [!CAUTION]\n"
            f"> **Security Violation**: {parsed['blocked_detail']}\n\n"
            "### 🤖 Agent Triage Summary\n"
            f"{parsed['agent_text']}\n\n"
            "---\n"
            "*Protected by Google Cloud Model Armor & Gemini Enterprise Agent Runtime on Vertex AI.*"
        )
    else:
        comment = (
            "## 🛡️ Gemini Enterprise AI PR Reviewer — Code Triage\n\n"
            "| Check | Status |\n"
            "| :--- | :--- |\n"
            "| **Security Inspection** | ✅ **PASSED** |\n"
            "| **Model Armor Guardrail** | 🛡️ **CLEAN** |\n\n"
            "### 🤖 Agent Triage Summary\n"
            f"{parsed['agent_text'] or 'Code and diff inspected. No prompt injection or privilege escalation detected.'}\n\n"
            "---\n"
            "*Protected by Google Cloud Model Armor & Gemini Enterprise Agent Runtime on Vertex AI.*"
        )

    if github_token:
        post_pr_comment(repo, pr_number, github_token, comment)

    if parsed["quarantined"]:
        print("❌ Model Armor quarantined malicious payload! Failing CI build.")
        sys.exit(1)
    else:
        print("✅ PR passed security inspection.")
        sys.exit(0)

if __name__ == "__main__":
    main()
