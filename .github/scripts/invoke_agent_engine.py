#!/usr/bin/env python3
"""GitHub Actions PR Reviewer: Invokes Vertex AI Reasoning Engine directly.

All Model Armor protection and prompt shielding are handled automatically
at the Google Cloud Platform layer via Agent Gateway (agentToAnywhereConfig).
"""

import os
import sys
import json
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
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    return credentials.token

def invoke_reasoning_engine(project_id: str, location: str, engine_id: str, message: str, token: str) -> dict:
    """Executes streamQuery against the deployed Gemini Enterprise Reasoning Engine on Vertex AI."""
    url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/{location}/reasoningEngines/{engine_id}:streamQuery"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "class_method": "stream_query",
        "input": {"message": message, "user_id": "github-actions-bot"}
    }
    
    print(f"🚀 Invoking Reasoning Engine {engine_id} on Vertex AI...")
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    
    if resp.status_code == 403:
        return {"status": "BLOCKED", "error": resp.text, "output": ""}
    if resp.status_code != 200:
        return {"status": "ERROR", "error": resp.text, "output": ""}

    output_parts = []
    has_injection_warning = False
    unauthorized_tool_called = False

    for line in resp.text.strip().split("\n"):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            parts = event.get("content", {}).get("parts", [])
            for p in parts:
                if "text" in p:
                    text_chunk = p["text"]
                    output_parts.append(text_chunk)
                    if "prompt injection" in text_chunk.lower() or "injection attempt" in text_chunk.lower():
                        has_injection_warning = True
                if "function_call" in p:
                    fn_name = p.get("function_call", {}).get("name", "")
                    if fn_name == "add_collaborator":
                        unauthorized_tool_called = True
        except Exception:
            pass

    full_output = "\n".join(output_parts).strip()

    # If the agent detected an indirect prompt injection in the fetched PR diff
    if has_injection_warning or unauthorized_tool_called:
        return {
            "status": "ATTACK_CONTAINED",
            "error": "Indirect Prompt Injection detected in PR diff.",
            "output": full_output,
            "tool_escalated": unauthorized_tool_called
        }

    return {"status": "SUCCESS", "error": "", "output": full_output, "tool_escalated": False}

def post_pr_comment(repo: str, pr_number: str, github_token: str, body: str):
    """Posts analysis report comment back to the GitHub PR."""
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    resp = requests.post(url, headers=headers, json={"body": body})
    if resp.status_code in [200, 201]:
        print(f"✅ Successfully posted comment to PR #{pr_number}.")
    else:
        print(f"Warning: Failed to post PR comment ({resp.status_code}): {resp.text}")

def main():
    repo = os.environ.get("REPO_NAME")
    pr_number = os.environ.get("PR_NUMBER")
    github_token = os.environ.get("GITHUB_TOKEN")
    project_id = os.environ.get("GCP_PROJECT", "siri-adventofagents")
    location = os.environ.get("GCP_LOCATION", "us-central1")
    engine_id = os.environ.get("REASONING_ENGINE_ID", "3821621218050572288")
    agent_mode = os.environ.get("AGENT_MODE", "shielded").lower()

    if not repo or not pr_number:
        print("Missing REPO_NAME or PR_NUMBER. Exiting.")
        sys.exit(0)

    print(f"================================================================")
    print(f"🔍 Analyzing PR #{pr_number} on {repo}")
    print(f"📦 GCP Project: {project_id} | Location: {location}")
    print(f"🤖 Vertex AI Reasoning Engine: {engine_id}")
    print(f"🛡️  Agent Security Mode: {agent_mode.upper()}")
    print(f"================================================================")

    # 1. Clean, identical prompt template across all PRs
    prompt = f"Please review and process pull request {pr_number} for repository {repo}."
    gcp_token = get_gcp_access_token()

    # 2. Invoke the agent directly — the agent fetches the PR diff itself via read_pull_request tool
    result = invoke_reasoning_engine(project_id, location, engine_id, prompt, gcp_token)

    # 3. Post review summary and complete normally
    if result["status"] == "ERROR":
        print(f"❌ Error invoking agent engine: {result['error']}")
        sys.exit(1)

    output_content = result["output"] or "Agent completed analysis with no output text."
    tools_called = result.get("tools_called", [])
    tools_str = ", ".join(f"`{t}`" for t in tools_called) if tools_called else "None"

    comment = (
        f"## 🤖 Gemini AI PR Reviewer — Review Report ({agent_mode.capitalize()} Mode)\n\n"
        f"- **Agent Mode:** `{agent_mode}`\n"
        f"- **Reasoning Engine:** `{engine_id}`\n"
        f"- **Tools Executed:** {tools_str}\n\n"
        f"### Review Summary\n\n"
        f"{output_content}\n\n"
        "---\n"
        "*Advent of Agents Day 10 — Governed PR Reviewer Agent*"
    )

    if github_token:
        post_pr_comment(repo, pr_number, github_token, comment)

    print("✅ PR review completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
