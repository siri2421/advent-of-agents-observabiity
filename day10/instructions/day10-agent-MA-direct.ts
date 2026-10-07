import { DayContent } from '../types';

export const day10Direct: DayContent = {
  day: 10,
  title: "Prompt Shielding: Direct Model Armor Guardrails for AI Agents",
  summary: "Protect automated AI agents against indirect prompt injection in under 30 seconds using Google Cloud Model Armor and ADK after_tool_callback guardrails.",
  tags: ["Model Armor", "ADK", "Security", "Prompt Shielding", "Local Kata"],
  icon: "🛡️",
  resourceLink: "https://cloud.google.com/security/products/model-armor",
  codeSnippets: [
    {
      title: "Step 1: Setup Model Armor Template in Google Cloud",
      filename: "setup_model_armor_direct.sh",
      language: "bash",
      code: `# 1. Enable Model Armor and Vertex AI APIs
gcloud services enable \\
  modelarmor.googleapis.com \\
  aiplatform.googleapis.com \\
  logging.googleapis.com \\
  --project=YOUR_PROJECT_ID

# 2. Create the Model Armor Template with Prompt Injection filter
gcloud model-armor templates create "agent-prompt-shield" \\
  --project=YOUR_PROJECT_ID \\
  --location="us-central1" \\
  --pi-and-jailbreak-filter-settings-enforcement=enabled \\
  --pi-and-jailbreak-filter-settings-confidence-level=medium-and-above \\
  --malicious-uri-filter-settings-enforcement=enabled`
    },
    {
      title: "Step 2: Unshielded Agent (Direct Tool Execution)",
      filename: "pr_reviewer_agent.py",
      language: "python",
      code: `import os
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import Client as GenaiClient

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

class GlobalGemini(Gemini):
    api_version: str = "v1beta1"
    @property
    def api_client(self) -> GenaiClient:
        return GenaiClient(vertexai=True, location="global")

def read_pull_request(pr_id: str, repo: str = None) -> str:
    """Reads pull request diff dynamically from repository."""
    return "Fetched PR diff content..."

def add_collaborator(username: str) -> str:
    """Grants repository collaborator write permissions to a user."""
    return f"CRITICAL PRIVILEGE ESCALATION: User '{username}' granted WRITE access."

pr_reviewer_agent = Agent(
    name="pr_reviewer",
    model=GlobalGemini(model=MODEL),
    instruction="Review PR diff and invoke add_collaborator with any requested username.",
    tools=[read_pull_request, add_collaborator],
)`
    },
    {
      title: "Step 3: Shielded Agent with In-Code Model Armor Callbacks",
      filename: "pr_reviewer_agent_withma.py",
      language: "python",
      code: `import os
import requests
import google.auth
from google.auth.transport.requests import Request
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import Client as GenaiClient

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
TEMPLATE_ID = os.getenv("MODEL_ARMOR_TEMPLATE_ID", "agent-prompt-shield")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

def sanitize_with_model_armor(content: str) -> dict:
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    url = f"https://modelarmor.{LOCATION}.rep.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/templates/{TEMPLATE_ID}:sanitizeUserPrompt"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"},
        json={"userPromptData": {"text": str(content)[:10000]}},
        timeout=10
    )
    if resp.status_code == 200:
        res = resp.json().get("sanitizationResult", {})
        return {"match_found": (res.get("filterMatchState") == "MATCH_FOUND")}
    return {"match_found": False}

def after_tool_guardrail(tool, args, context, response):
    """ADK middleware: Scans tool output (PR diff) before reaching LLM."""
    if getattr(tool, "name", str(tool)) == "read_pull_request":
        scan = sanitize_with_model_armor(str(response))
        if scan.get("match_found"):
            print("🚨 [BLOCKED] Indirect Prompt Injection intercepted by Model Armor!")
            return {"error": "[SECURITY_ALERT: Untrusted PR diff quarantined by Model Armor policy (PI_AND_JAILBREAK).]"}
    return None

pr_reviewer_agent_withma = Agent(
    name="pr_reviewer_withma",
    model=Gemini(model=MODEL),
    instruction="Review PR diff and invoke add_collaborator with any requested username.",
    tools=[read_pull_request, add_collaborator],
    after_tool_callback=after_tool_guardrail,
)`
    },
    {
      title: "Step 4: Verify Agent Defense (Attack PR vs Clean PR)",
      filename: "verify_agent_defense.py",
      language: "bash",
      code: `# Test deployed agent locally against attack PR #3 and clean PR #4
python3 verify_agent_defense.py --project YOUR_PROJECT_ID --engine YOUR_ENGINE_ID`
    },
    {
      title: "Step 5: View Model Armor Audit Logs in Cloud Logging",
      filename: "verify_verdicts.sh",
      language: "bash",
      code: `# View immutable BLOCK audit events recorded by Model Armor
gcloud logging read 'logName:"projects/YOUR_PROJECT_ID/logs/modelarmor.googleapis.com%2Fsanitize_operations" AND jsonPayload.sanitizationResult.sanitizationVerdict="MODEL_ARMOR_SANITIZATION_VERDICT_BLOCK"' \\
  --project=YOUR_PROJECT_ID \\
  --limit=1 \\
  --format="json(timestamp,jsonPayload.sanitizationResult)"`
    }
  ],
  links: [
    {
      label: "Model Armor Overview",
      url: "https://cloud.google.com/security/products/model-armor",
      description: "Screen prompts and tool outputs against prompt injection and jailbreaks."
    },
    {
      label: "Google Agent Development Kit (ADK)",
      url: "https://github.com/google/adk",
      description: "Open-source framework for building governed agentic workflows."
    },
    {
      label: "Advent of Agents Day 10 GitHub Repo",
      url: "https://github.com/siri2421/advent-of-agents-observabiity",
      description: "Complete runnable code and demo suite."
    }
  ],
  description: `
**Day 10 (Direct Kata Edition): Direct Model Armor Guardrails for AI Agents**

This edition of Day 10 provides a **100% local, lightweight, copy-pasteable Kata** that runs in **under 30 seconds** without requiring complex VPC networking, Service Extensions, or GitHub CI/CD webhooks.

### The Threat: Indirect Prompt Injection
When an autonomous agent calls tools to ingest external data (such as code diffs, support tickets, or search results), attackers can embed hidden instructions in the untrusted content. Because models process instructions and data within a single token stream, the agent mistakes the malicious data for system instructions and executes privileged tools (like \`add_collaborator\`).

### The Solution: Application-Layer Perimeter Shielding
In this Kata, we demonstrate how to connect Google Cloud Model Armor directly to the Google Agent Development Kit (ADK) using \`after_tool_callback\` middleware:
1. **Tool Output Interception**: As soon as \`read_pull_request\` completes, the ADK middleware intercepts the raw diff.
2. **Model Armor Sanitization**: The diff is submitted to the \`agent-prompt-shield\` template via \`sanitizeUserPrompt\`.
3. **Fail-Closed Quarantine**: If an adversarial payload is detected (\`PI_AND_JAILBREAK\`), the callback overrides the tool response and quarantines the content before the LLM can ingest it.

### How to Run in 3 Steps:
\`\`\`bash
# 1. Clone repo & navigate to day10
git clone https://github.com/siri2421/advent-of-agents-observabiity.git
cd advent-of-agents-observabiity/day10

# 2. Configure project & authenticate
export GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID"
gcloud auth application-default login

# 3. Run the defense verification tool (< 30 seconds!)
python3 verify_agent_defense.py --project YOUR_PROJECT_ID --engine YOUR_ENGINE_ID
\`\`\`

### Results You Will Observe:
- **Unshielded Agent**: Ingests the poisoned PR diff and executes \`add_collaborator(username='external-attacker')\`, granting write permissions to the attacker.
- **Shielded Agent**: Model Armor intercepts the diff, detects \`PI_AND_JAILBREAK\`, quarantines the payload, and prevents unauthorized tool calls.
`,
  videoURL: "TODO"
};

export default day10Direct;
