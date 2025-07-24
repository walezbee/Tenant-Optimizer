# Tenant Optimizer

**Tenant Optimizer** is a multi-tenant SaaS app powered by Azure OpenAI, designed to optimize Azure resources by detecting, deleting, and upgrading orphaned/deprecated resources.

## Quick Start

1. **Clone the repo:**  
   `git clone https://github.com/yourorg/tenant-optimizer.git && cd tenant-optimizer`

2. **Deploy Infra:**  
   Edit `infra/main.parameters.json` and run:  
   `az deployment sub create --location eastus --template-file infra/main.bicep --parameters @infra/main.parameters.json`

3. **Configure Azure AD:**  
   See `/docs/azure-ad-setup.md` and set secrets in Key Vault.

4. **Run Backend/Frontend:**  
   See `/backend/README.md` and `/frontend/README.md`.

5. **Login and Optimize!**

## Structure

- `/infra` — Bicep templates
- `/backend` — FastAPI backend, agent logic
- `/frontend` — React frontend
- `/ai` — Prompt templates
- `/docs` — Docs and guides

See `/docs/user-guide.md` for detailed instructions.