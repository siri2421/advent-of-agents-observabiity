# System Architecture

## Overview
This repository provides an enterprise AI code review pipeline with real-time prompt shielding.

## Key Components
- **GitHub Actions**: Triggers on Pull Requests and fetches dynamic diffs.
- **Google Cloud Model Armor**: Scans egress payloads for Prompt Injection & Jailbreaks.
- **Gemini Enterprise Agent Runtime**: Analyzes code changes on Vertex AI.
