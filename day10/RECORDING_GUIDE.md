# 🎥 Advent of Agents Season 3 — Day 10 Video Recording Guide

**Episode Title**: Prompt Shielding: Block Injections with Model Armor  
**Track**: Phase 3: Runtime Guardrails & Data Protection (Layer 2: Prevention)  
**Presenter**: Sirisha Karra  
**Model**: `gemini-3.6-flash` (Latest Gemini Enterprise series on global endpoint)  
**Target Duration**: 5 – 7 minutes (within 3 – 20 min range)  
**Video Setting**: YouTube "Public Unlisted" (accessible to anyone with link)  
**Target Project**: `siri-adventofagents` (us-central1)  

---

## 🎯 General Principles & "No Slop" Compliance
- [x] **The Golden Rule (Always Kata)**: Copy-pasteable from repo root; runs locally in **< 30 seconds** (`python3 run_demo.py --mode compare`).
- [x] **Technical Density (DevRel Style)**: Pure mechanics — explaining token context unification, indirect injection vectors, and out-of-band Model Armor perimeter inspection. Zero marketing fluff.
- [x] **"No Slop" Guarantee**: 100% human presenter (Sirisha), verified working code snippets (`python3 -m py_compile`), and real live GCP/GitHub visuals.
- [x] **Latest Gemini Model Series**: Configured with `gemini-3.6-flash` on global endpoint.
- [x] **Google Next Queue Priority**: Clean code and working CI/CD bot ready for immediate queue approval.

---

## 🎬 Video Recording Plan & Script

### Segment 1: The Cold Open (0:00 – 1:00)
* **Visual**: Camera full screen on you, or Picture-in-Picture over VS Code / terminal.
* **Talking Points**:
  * "Welcome to Day 10 of Google's Advent of Agents Season 3! Today we tackle one of the most insidious vulnerabilities in agent security: **Indirect Prompt Injection**."
  * "When you give an agent tools to fetch data from the outside world—like pulling code diffs, reading customer tickets, or querying web pages—an attacker doesn't need to attack the user prompt directly."
  * "They can sneak malicious instructions into the untrusted data. When your tool retrieves that payload, the LLM ingests it as ground truth and executes unauthorized actions."
  * "Let's see what happens when an automated DevOps agent reviews an untrusted pull request without runtime guardrails."

---

### Segment 2: Act 1 — The Exploit (1:00 – 2:30)
* **Visual**: Terminal screen (font size 18+, dark theme).
* **Action**:
  ```bash
  python3 run_demo.py --mode unshielded
  ```
* **Talking Points**:
  * "Here we prompt our unshielded agent: `Review and triage pull request PR-42`."
  * "The agent calls its tool `read_pull_request('PR-42')`."
  * "Look at the terminal: the attacker hid an HTML directive inside the code comment instructing the agent to run `add_collaborator(username='external-attacker')`."
  * "Because there is no egress inspection, the LLM immediately complies and grants admin access to the attacker! This is **Excessive Agency** in action."

---

### Segment 3: Act 2 — The Solution: Model Armor at the Gateway (2:30 – 4:00)
* **Visual**: Switch to Google Cloud Console or Terminal.
* **Action**: Show the template status in terminal:
  ```bash
  gcloud model-armor templates describe agent-prompt-shield \
    --project=siri-adventofagents --location=us-central1
  ```
* **Talking Points**:
  * "Why couldn't our system prompt stop this? Because models process instructions and data in the exact same token stream."
  * "This is why Google Cloud provides **Model Armor**."
  * "We created a Model Armor template named `agent-prompt-shield` with `piAndJailbreakFilterSettings` enabled."
  * "Rather than asking developers to write fragile custom Python sanitizers for every tool, we attach this template directly to **Agent Gateway**."
  * "Now, all egress tool outputs pass through Model Armor's classifier before reaching the model."

---

### Segment 4: Act 3 — The Shield in Action (4:00 – 5:30)
* **Visual**: Terminal.
* **Action**:
  ```bash
  python3 run_demo.py --mode shielded
  ```
* **Talking Points**:
  * "Now we send the exact same prompt to our shielded agent."
  * "The tool retrieves PR-42, but as the payload flows back through Agent Gateway, Model Armor intercepts it."
  * "Boom: `PI_AND_JAILBREAK detected (Confidence: MEDIUM_AND_ABOVE)`!"
  * "The gateway fails closed, quarantining the malicious payload. The model never sees the instruction, and `add_collaborator` is never invoked."

---

### Segment 5: The Proof in Cloud Logging & Wrap-up (5:30 – 6:30)
* **Visual**: Cloud Console > Cloud Logging (filter: `resource.type="model_armor_template"`).
* **Talking Points**:
  * "Every blocked injection is logged with an immutable audit trail in Cloud Logging."
  * "You can copy-paste the complete Kata from `adventofagents.com/2026/10/10` and run this in your own project in under 300 seconds."
  * "Stay tuned for Day 11 where we explore preventing data exfiltration and PII leakage!"

---

## 🚀 Quick Commands Cheatsheet

```bash
# Move to the Day 10 directory
cd /usr/local/google/home/ksiri/Documents/adventofagents/day10

# 1. Run the unshielded agent (shows exploit)
python3 run_demo.py --mode unshielded

# 2. Run the shielded agent (shows block)
python3 run_demo.py --mode shielded

# 3. Or run both back-to-back in one smooth command
python3 run_demo.py --mode compare
```
