"""Deploy PR Reviewer Agent with native AGENT_IDENTITY to Vertex AI Reasoning Engine.

Attaches Model Armor Agent Gateway (agentToAnywhereConfig) for outbound inspection.
"""

import os
import subprocess
import requests
import google.oauth2.credentials
import google.auth
import google.cloud.storage
import vertexai
from vertexai.preview import reasoning_engines
from vertexai._genai.client import Client
from vertexai._genai import types

import sys
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(CURRENT_DIR, "pr_reviewer_agent.py")):
    DAY10_DIR = CURRENT_DIR
elif os.path.exists(os.path.join(CURRENT_DIR, "day10", "pr_reviewer_agent.py")):
    DAY10_DIR = os.path.join(CURRENT_DIR, "day10")
else:
    DAY10_DIR = os.path.dirname(CURRENT_DIR)

if DAY10_DIR not in sys.path:
    sys.path.insert(0, DAY10_DIR)

from pr_reviewer_agent import pr_reviewer_agent

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "siri-adventofagents")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = f"gs://{PROJECT_ID}-staging"
DISPLAY_NAME = "pr-reviewer-agent-identity"

# Setup Google Cloud credentials
token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
creds = google.oauth2.credentials.Credentials(token)
google.auth.default = lambda *args, **kwargs: (creds, PROJECT_ID)
_orig_storage = google.cloud.storage.Client
google.cloud.storage.Client = lambda *args, **kwargs: _orig_storage(*args, **{**kwargs, 'credentials': creds, 'project': PROJECT_ID})

vertexai.init(
    project=PROJECT_ID,
    location=LOCATION,
    credentials=creds,
    staging_bucket=STAGING_BUCKET,
)

# Patch _upload_extra_packages so files in dependencies.tar.gz are stored with their basename,
# ensuring `import pr_reviewer_agent` succeeds in the deployed Reasoning Engine container.
import io
import tarfile
from vertexai._genai import _agent_engines_utils

def _patched_upload_extra_packages(*, extra_packages, gcs_bucket, gcs_dir_name):
    tar_fileobj = io.BytesIO()
    with tarfile.open(fileobj=tar_fileobj, mode="w|gz") as tar:
        for file in extra_packages:
            arcname = os.path.basename(file)
            print(f"📦 Packaging extra file: {file} -> {arcname}")
            tar.add(file, arcname=arcname)
    tar_fileobj.seek(0)
    blob = gcs_bucket.blob(f"{gcs_dir_name}/{_agent_engines_utils._EXTRA_PACKAGES_FILE}")
    blob.upload_from_string(tar_fileobj.read())

_agent_engines_utils._upload_extra_packages = _patched_upload_extra_packages


def main():
    unshielded = "--unshielded" in sys.argv
    force = "--force" in sys.argv

    display_name = "pr-reviewer-unshielded" if unshielded else DISPLAY_NAME
    description = (
        "PR Reviewer Agent without Model Armor or Agent Gateway guardrails"
        if unshielded
        else "PR Reviewer Agent with native AGENT_IDENTITY and Model Armor Agent Gateway"
    )

    print("============================================================")
    print(f"🚀 DEPLOYING {'UNSHIELDED' if unshielded else 'SHIELDED'} PR REVIEWER AGENT 🚀")
    print("============================================================")
    print(f"👉 Project: {PROJECT_ID}")
    print(f"👉 Location: {LOCATION}")
    print(f"👉 Staging: {STAGING_BUCKET}")
    print(f"👉 Display Name: {display_name}")
    print("────────────────────────────────────────────────────────────")

    client = Client(project=PROJECT_ID, location=LOCATION, credentials=creds)

    # Fast-Path Engine Re-Use Shield (Rule 2)
    if not force:
        try:
            url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines"
            resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
            for engine in resp.json().get("reasoningEngines", []):
                if engine.get("displayName") == display_name:
                    engine_urn = engine.get("name")
                    engine_id = engine_urn.split("/")[-1]
                    print(f"🚀 Bypassing slow re-creation and reusing existing engine runtime instantaneously!")
                    print(f"👉 Engine URN: {engine_urn}")
                    print(f"👉 Engine ID: {engine_id}")
                    id_file = f"/tmp/{display_name}_id.txt"
                    with open(id_file, "w") as f:
                        f.write(engine_id)
                    return engine_id
        except Exception as e:
            print(f"⚠️ Check for existing engine encountered: {e}")

    app = reasoning_engines.AdkApp(agent=pr_reviewer_agent, enable_tracing=True)

    runtime_env = {
        "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
        "TARGET_PROJECT_ID": PROJECT_ID,
        "GOOGLE_CLOUD_LOCATION": "global",
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_SERVICE_NAME": display_name,
        "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "EVENT_ONLY",
    }
    if not unshielded:
        runtime_env["MODEL_ARMOR_LOCATION"] = "us-central1"
        runtime_env["MODEL_ARMOR_TEMPLATE_ID"] = "agent-prompt-shield"

    requirements = [
        "google-cloud-aiplatform[reasoningengine,adk]>=1.75.0",
        "google-adk==2.2.0",
        "cloudpickle",
        "pydantic>=2.10.0,<3.0.0",
        "requests>=2.31.0",
    ]

    agent_source_file = os.path.join(DAY10_DIR, "pr_reviewer_agent.py")

    gateway_config = None
    if not unshielded:
        gateway_config = {
            "agent_to_anywhere_config": {
                "agent_gateway": f"projects/{PROJECT_ID}/locations/{LOCATION}/agentGateways/agent-egress-gateway"
            }
        }

    config = types.AgentEngineConfig(
        display_name=display_name,
        description=description,
        identity_type="AGENT_IDENTITY",
        staging_bucket=STAGING_BUCKET,
        requirements=requirements,
        extra_packages=[agent_source_file],
        env_vars=runtime_env,
        agent_gateway_config=gateway_config,
    )

    print("⏳ Calling client.agent_engines.create(agent=app, config=config)...")
    try:
        remote_agent = client.agent_engines.create(agent=app, config=config)
        engine_urn = remote_agent.api_resource.name
        engine_id = engine_urn.split("/")[-1]
        effective_identity = getattr(remote_agent.api_resource.spec, "effective_identity", None)
        print(f"\n============================================================")
        print(f"🎉 SUCCESS! Agent Deployed ({display_name})!")
        print(f"============================================================")
        print(f"👉 Engine URN: {engine_urn}")
        print(f"👉 Engine ID: {engine_id}")
        print(f"👉 Effective Identity: {effective_identity}")
        if not unshielded:
            print(f"👉 Egress Gateway: agent-egress-gateway")
        print("────────────────────────────────────────────────────────────")
        with open(f"/tmp/{display_name}_id.txt", "w") as f:
            f.write(engine_id)
        return engine_id
    except Exception as e:
        if unshielded:
            print(f"❌ Failed to create unshielded engine: {e}")
            raise e
        print(f"❌ Direct creation with agent_gateway_config failed: {e}")
        print("🔄 Retrying with two-step provisioning (create with AGENT_IDENTITY, then PATCH agent_gateway_config)...")
        config.agent_gateway_config = None
        remote_agent = client.agent_engines.create(agent=app, config=config)
        engine_urn = remote_agent.api_resource.name
        engine_id = engine_urn.split("/")[-1]
        effective_identity = getattr(remote_agent.api_resource.spec, "effective_identity", None)
        print(f"✅ Step 1 complete: Deployed with AGENT_IDENTITY!")
        print(f"👉 Engine URN: {engine_urn}")
        print(f"👉 Effective Identity: {effective_identity}")

        # Step 2: PATCH agentGatewayConfig
        print("⏳ Step 2: Patching agentGatewayConfig...")
        patch_url = f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/{engine_urn}?updateMask=spec.deploymentSpec.agentGatewayConfig"
        patch_payload = {
            "spec": {
                "deploymentSpec": {
                    "agentGatewayConfig": {
                        "agentToAnywhereConfig": {
                            "agentGateway": f"projects/{PROJECT_ID}/locations/{LOCATION}/agentGateways/agent-egress-gateway"
                        }
                    }
                }
            }
        }
        patch_resp = requests.patch(
            patch_url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=patch_payload
        )
        print(f"👉 Patch response ({patch_resp.status_code}): {patch_resp.text}")
        with open(f"/tmp/{display_name}_id.txt", "w") as f:
            f.write(engine_id)
        return engine_id


if __name__ == "__main__":
    main()
