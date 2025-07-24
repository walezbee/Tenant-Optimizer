# Tenant Optimizer — Architecture

## Overview
Multi-tenant SaaS for Azure cost/resource optimization with AI-powered agents.

## Key Components
- **Frontend (React):** User dashboard, approvals, reports
- **Backend (FastAPI):** API, agent orchestration, OpenAI integration
- **Azure OpenAI:** LLM for resource classification
- **Cosmos DB:** State, approvals, audit logs
- **Key Vault:** Secrets
- **Azure AD:** Multi-tenant authentication
- **Resource Graph:** Inventory and resource queries

## Flow
1. User logs in (Azure AD)
2. Triggers a scan (or scheduled)
3. Agent queries Azure Resource Graph, sends data to OpenAI for analysis
4. Results shown in dashboard; user can approve recommended actions
5. Approved actions are executed (delete/upgrade) and logged

## Extensibility
- Prompts, rules, and resource patterns are updatable to keep pace with Azure changes.