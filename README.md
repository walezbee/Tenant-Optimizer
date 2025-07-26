## Tenant Optimizer

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

## Azure App Service Deployment

### Startup Command Configuration

When deploying the backend to Azure App Service (Python Linux), set the **Startup Command** in the App Service configuration to:

```bash
/home/site/wwwroot/backend/startup.sh
```

### Deployment Structure

After deployment, your files should be organized as:
```
/home/site/wwwroot/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── startup.sh
│   └── ... (other backend files)
└── ... (other project files)
```

### Troubleshooting Deployment Issues

1. **Check Application Logs**: Use Azure Portal > App Service > Log stream to view startup logs
2. **Verify File Structure**: Ensure `backend/requirements.txt` exists in the deployment
3. **Environment Variables**: Configure necessary Azure AD and OpenAI environment variables in App Service settings
4. **Startup Command**: Confirm the startup command points to `/home/site/wwwroot/backend/startup.sh`

The startup script includes comprehensive logging to help debug deployment issues. Check the Application Logs for detailed startup information.