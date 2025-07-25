## Backend (FastAPI) — Tenant Optimizer

## Overview
This backend is a FastAPI app exposing endpoints to:
- Scan for orphaned/deprecated resources
- Delete or upgrade resources (with approval)
- Integrate with Azure OpenAI for classification

## Structure
- `main.py` — API routes
- `agents/` — Logic for each agent
- `azure/` — Azure Resource Graph utilities
- `openai/` — Prompt templates

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Configuration
- Use environment variables for secrets (see `infra/` for Key Vault setup)
- Requires Azure AD app registration for OAuth