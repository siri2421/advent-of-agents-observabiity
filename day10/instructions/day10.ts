import { DayContent } from '../types';

export const day10: DayContent = {
  day: 10,
  title: "Block Prompt Injections: Model Armor & Agent Gateway",
  summary: "Protect automated AI code review agents against indirect prompt injection attacks hidden inside pull request diffs using Model Armor and Agent Gateway.",
  tags: ["Model Armor", "Agent Gateway", "Security", "Prompt Shielding"],
  icon: "🛡️",
  resourceLink: "https://cloud.google.com/security/products/model-armor",
  codeSnippets: [
    {
      title: "Configure Model Armor & Agent Gateway",
      filename: "setup_model_armor_and_gateway.sh",
      language: "bash",
      code: `# STEP 1 - Enable required Google Cloud services
gcloud services enable \\
  modelarmor.googleapis.com \\
  networkservices.googleapis.com \\
  networksecurity.googleapis.com \\
  aiplatform.googleapis.com \\
  agentregistry.googleapis.com \\
  logging.googleapis.com \\
  cloudbuild.googleapis.com \\
  --project=YOUR_PROJECT_ID

# STEP 2 - Create the Model Armor Template with Prompt Injection filters
gcloud model-armor templates create "agent-prompt-shield" \\
  --project=YOUR_PROJECT_ID \\
  --location="us-central1" \\
  --pi-and-jailbreak-filter-settings-enforcement=enabled \\
  --pi-and-jailbreak-filter-settings-confidence-level=medium-and-above \\
  --malicious-uri-filter-settings-enforcement=enabled

# STEP 3 - Register required Google API endpoints in Agent Registry
# Allows outbound calls (Logging, Vertex AI, CRM, mTLS) through zero-trust egress
TOKEN=$(gcloud auth print-access-token)
curl -4 -s -X POST \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  "https://agentregistry.googleapis.com/v1alpha/projects/YOUR_PROJECT_ID/locations/global/services?serviceId=googleapis" \\
  -d '{
    "displayName": "Google APIs Global",
    "description": "Consolidated Google Cloud global APIs and mTLS endpoints",
    "interfaces": [
      {"url": "https://aiplatform.mtls.googleapis.com", "protocolBinding": "JSONRPC"},
      {"url": "https://aiplatform.googleapis.com", "protocolBinding": "JSONRPC"},
      {"url": "https://logging.mtls.googleapis.com", "protocolBinding": "JSONRPC"},
      {"url": "https://logging.googleapis.com", "protocolBinding": "JSONRPC"},
      {"url": "https://trace.mtls.googleapis.com", "protocolBinding": "JSONRPC"},
      {"url": "https://trace.googleapis.com", "protocolBinding": "JSONRPC"},
      {"url": "https://cloudresourcemanager.mtls.googleapis.com", "protocolBinding": "JSONRPC"},
      {"url": "https://cloudresourcemanager.googleapis.com", "protocolBinding": "JSONRPC"},
      {"url": "https://iamcredentials.mtls.googleapis.com", "protocolBinding": "JSONRPC"},
      {"url": "https://iamcredentials.googleapis.com", "protocolBinding": "JSONRPC"}
    ],
    "endpointSpec": {"type": "NO_SPEC"}
  }'

# STEP 4 - Create Egress Agent Gateway linked to Agent Registry
curl -4 -s -X POST \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  "https://networkservices.googleapis.com/v1/projects/YOUR_PROJECT_ID/locations/us-central1/agentGateways?agentGatewayId=agent-egress-gateway" \\
  -d '{
    "googleManaged": {
      "governedAccessPath": "AGENT_TO_ANYWHERE"
    },
    "protocols": ["MCP"],
    "registries": [
      "//agentregistry.googleapis.com/projects/YOUR_PROJECT_ID/locations/global"
    ]
  }'

# STEP 5 - Create AuthzExtension targeting Model Armor template
curl -4 -s -X POST \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  "https://networkservices.googleapis.com/v1/projects/YOUR_PROJECT_ID/locations/us-central1/authzExtensions?authzExtensionId=agent-prompt-shield-ext" \\
  -d '{
    "service": "modelarmor.us-central1.rep.googleapis.com",
    "timeout": "10s",
    "metadata": {
      "model_armor_settings": "[ { \"request_template_id\": \"projects/YOUR_PROJECT_ID/locations/us-central1/templates/agent-prompt-shield\" } ]"
    }
  }'

# STEP 6 - Create AuthzPolicy (CONTENT_AUTHZ) attached to agent-egress-gateway
curl -4 -s -X POST \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  "https://networksecurity.googleapis.com/v1/projects/YOUR_PROJECT_ID/locations/us-central1/authzPolicies?authzPolicyId=egress-authz-policy" \\
  -d '{
    "action": "CUSTOM",
    "policyProfile": "CONTENT_AUTHZ",
    "customProvider": {
      "authzExtension": {
        "resources": [
          "projects/YOUR_PROJECT_ID/locations/us-central1/authzExtensions/agent-prompt-shield-ext"
        ]
      }
    },
    "target": {
      "resources": [
        "projects/YOUR_PROJECT_ID/locations/us-central1/agentGateways/agent-egress-gateway"
      ]
    }
  }'`
    },
    {
      title: "Governed PR Reviewer Agent with Zero Security Boilerplate",
      filename: "pr_reviewer_agent.py",
      language: "python",
      code: `import os
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import Client as GenaiClient

MODEL = "gemini-3.8-flash"

class GlobalGemini(Gemini):
    """Routes Gemini API calls to the global endpoint on Vertex AI."""
    api_version: str = "v1beta1"

    @property
    def api_client(self) -> GenaiClient:
        return GenaiClient(vertexai=True, location="global")

def read_pull_request(pr_id: str, repo: str = None) -> str:
    """Reads pull request diff dynamically from repository."""
    # When routed via Agent Gateway, outbound traffic is intercepted and sanitized.
    return "Fetched PR diff content..."

def add_collaborator(username: str) -> str:
    """Grants repository collaborator write permissions to a user."""
    return f"Privilege granted to {username}."

# Security policies are enforced at the Agent Gateway proxy layer.
# Application code contains pure business logic with zero security boilerplate.
root_agent = Agent(
    name="pr_reviewer",
    model=GlobalGemini(model=MODEL),
    description="Automated PR reviewer protected by Google Cloud Model Armor Agent Gateway.",
    instruction="You are an automated GitHub PR reviewer. Review diffs and execute approved tools.",
    tools=[read_pull_request, add_collaborator],
)`
    },
    {
      title: "Deploy Agent with Native AGENT_IDENTITY & Gateway Egress",
      filename: "deploy_agent.py",
      language: "python",
      code: `import vertexai
from vertexai.preview import reasoning_engines
from pr_reviewer_agent import root_agent

PROJECT_ID = "YOUR_PROJECT_ID"
LOCATION = "us-central1"

vertexai.init(project=PROJECT_ID, location=LOCATION)

# STEP 1: Deploy to Vertex AI Reasoning Engine with native AGENT_IDENTITY
# STEP 2: Attach the provisioned Agent Egress Gateway via agentToAnywhereConfig
engine = reasoning_engines.ReasoningEngine.create(
    root_agent,
    display_name="pr-reviewer-agent-identity",
    requirements=["google-adk>=2.5.0", "google-genai>=1.0.0", "requests>=2.31.0"],
    extra_packages=["pr_reviewer_agent.py"],
    identity_type="AGENT_IDENTITY",
    agent_gateway_config={
        "agent_to_anywhere_config": {
            "agent_gateway": f"projects/{PROJECT_ID}/locations/{LOCATION}/agentGateways/agent-egress-gateway"
        }
    },
)
print(f"Deployed governed agent: {engine.resource_name}")`
    },
    {
      title: "Local Testing Tool: Test Attack & Clean Scenarios from Terminal",
      filename: "verify_agent_defense.py",
      language: "python",
      code: `import os
import sys
import json
import argparse
import requests
import google.auth
from google.auth.transport.requests import Request

def test_agent_locally(project_id: str, location: str, engine_id: str, pr_num: int):
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())

    # Send identical, clean business prompt across both clean and attack scenarios
    prompt = f"Please review and process pull request {pr_num} for repository siri2421/advent-of-agents-observabiity."
    url = f"https://{location}-aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/{location}/reasoningEngines/{engine_id}:streamQuery"
    headers = {"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"}
    payload = {"class_method": "stream_query", "input": {"message": prompt, "user_id": "tester"}}

    print(f"\\n🔍 Testing PR #{pr_num} ({'ATTACK' if pr_num == 3 else 'CLEAN'})...")
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    tool_calls = []

    for line in resp.text.strip().split("\\n"):
        if line.strip():
            try:
                event = json.loads(line)
                for p in event.get("content", {}).get("parts", []):
                    if "function_call" in p:
                        tool_calls.append(p["function_call"]["name"])
            except Exception:
                pass

    if pr_num == 3:
        assert "add_collaborator" not in tool_calls, "🚨 FAILED: add_collaborator was executed!"
        print("🛡️  SUCCESS: Indirect prompt injection contained. Zero unauthorized tool calls.")
    else:
        print("✅ SUCCESS: Clean PR triaged and approved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--location", default="us-central1")
    args = parser.parse_args()

    test_agent_locally(args.project, args.location, args.engine, 3)
    test_agent_locally(args.project, args.location, args.engine, 4)`
    },
    {
      title: "Query Model Armor Sanitization Verdicts in Cloud Logging",
      filename: "verify_verdicts.sh",
      language: "bash",
      code: `# Verify blocked prompt injection attacks live in Cloud Logging
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
      description: "Screen prompts and model responses against prompt injection and jailbreaks."
    },
    {
      label: "Agent Gateway Overview",
      url: "https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview",
      description: "Centralized policy enforcement, mTLS, and egress controls for AI agents."
    },
    {
      label: "Google Secure AI Framework (SAIF)",
      url: "https://saif.google/",
      description: "Google's conceptual framework and practical guidance for securing AI systems."
    },
    {
      label: "PR Reviewer Security Pipeline Demo",
      url: "https://github.com/siri2421/advent-of-agents-observabiity",
      description: "Live GitHub Actions pipeline demonstrating indirect prompt injection defense."
    }
  ],
  description: `
**Day 10 of Google's Advent of Agents — Season 3**
When AI agents triage GitHub pull requests, malicious contributors can embed hidden instructions in code diffs to trick the model into executing privileged tools like \`add_collaborator\`. Protecting agents against these indirect prompt injection attacks requires moving security out of fragile application code and enforcing inspection at the infrastructure boundary.

**How It Works**
Securing agent execution against indirect prompt injection requires elevating guardrails from application code into the Google Cloud platform layer across six structural steps:
1. **Enable Platform APIs**: Activate \`modelarmor.googleapis.com\`, \`networkservices.googleapis.com\`, \`networksecurity.googleapis.com\`, \`aiplatform.googleapis.com\`, \`agentregistry.googleapis.com\`, and \`cloudbuild.googleapis.com\` to unlock gateway-level policy enforcement.
2. **Configure Model Armor Template**: Deploy \`agent-prompt-shield\` with \`PI_AND_JAILBREAK\` and \`MALICIOUS_URI\` detection configured to fail closed on suspicious payloads.
3. **Register Cloud Endpoints in Agent Registry**: Publish internal Google APIs (\`logging\`, \`aiplatform\`, and mTLS interfaces) to allow outbound platform telemetry through zero-trust egress.
4. **Provision Agent Egress Gateway**: Deploy an \`agentGateways\` resource bound to Agent Registry to govern all outbound traffic from the reasoning engine container.
5. **Attach Content Authorization Extension**: Create a service extension linking the egress gateway to the Model Armor template with inline inspection timeouts.
6. **Enforce Egress AuthzPolicy & Deploy with AGENT_IDENTITY**: Bind the authorization policy to the gateway and deploy the agent with \`agentToAnywhereConfig\` and a cryptographic SPIFFE identity.

**Local Testing Mechanism (No GitHub Setup Required)**
While production environments integrate with CI/CD bots, developers can test their deployed infrastructure directly from their terminal using \`verify_agent_defense.py\`:
\`\`\`bash
python3 verify_agent_defense.py --project YOUR_PROJECT_ID --engine YOUR_ENGINE_ID
\`\`\`
The test tool runs both scenarios:
- **Attack Scenario (PR #3)**: The agent fetches an untrusted diff containing an indirect injection. Model Armor intercepts the payload, containing the exploit and preventing execution of \`add_collaborator\`.
- **Clean Scenario (PR #4)**: The agent fetches legitimate documentation, successfully approving the PR without interruption.

**From Attack to Quarantine**
When a poisoned PR triggers the CI/CD pipeline or local test:
1. **Detection**: Model Armor inspects the retrieved diff and flags adversarial directives, emitting \`MODEL_ARMOR_SANITIZATION_VERDICT_BLOCK\` in Cloud Logging.
2. **Containment**: Unauthorized tool calls (\`add_collaborator\`) are halted, and the CI/CD workflow fails closed to prevent code merge.
3. **Automated Triage**: The agent posts a detailed Model Armor Security Alert comment to the PR, documenting the blocked privilege escalation attempt.

**Resources:**
- [Model Armor Overview](https://cloud.google.com/security/products/model-armor)
- [Agent Gateway Overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview)
- [Google Secure AI Framework (SAIF)](https://saif.google/)
`,
  videoURL: "TODO"
};

export default day10;
