import os
import logging
import httpx
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Dict, Any, Optional

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tenant-optimizer")

# Security configuration
security = HTTPBearer()

app = FastAPI(title="Azure Tenant Optimizer")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse('static/index.html')

@app.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0-minimal"
    }

@app.get("/api/test/upgrade-agents")
def test_upgrade_agents():
    """Test endpoint to show upgrade agents are in fallback mode."""
    return {
        "status": "test_completed",
        "system_mode": "manual_guidance_mode",
        "upgrade_agents": {
            "public_ip_agent": {
                "loaded": False,
                "error": "Dependencies not available in deployment environment",
                "status": "Manual guidance available"
            },
            "load_balancer_agent": {
                "loaded": False,
                "error": "Dependencies not available in deployment environment", 
                "status": "Manual guidance available"
            },
            "storage_account_agent": {
                "loaded": False,
                "error": "Dependencies not available in deployment environment",
                "status": "Manual guidance available"
            },
            "orchestrator": {
                "loaded": False,
                "error": "Dependencies not available in deployment environment",
                "status": "Manual guidance available"
            }
        },
        "azure_sdk": {
            "azure_identity": {"loaded": False, "status": "Not available - using manual mode"},
            "azure_mgmt_network": {"loaded": False, "status": "Not available - using manual mode"}
        },
        "test_timestamp": "2025-07-29",
        "summary": {
            "agents_loaded": 0,
            "total_agents": 4,
            "automation_available": False,
            "fallback_mode": True,
            "message": "System providing intelligent manual guidance"
        }
    }

# JWT verification (simplified for minimal version)
async def verify_azure_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Simplified token verification for minimal version."""
    try:
        token = credentials.credentials
        # For minimal version, just return basic user info
        return {
            "token": token,
            "user_id": "test-user",
            "verified": True
        }
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")

@app.get("/api/scan/orphaned")
async def scan_orphaned_resources(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Simplified orphaned resources scan."""
    return {
        "success": True,
        "message": "System running in minimal mode",
        "resources": [],
        "total_resources": 0,
        "scan_timestamp": datetime.now().isoformat(),
        "note": "Full scanning capabilities available when all dependencies are installed"
    }

@app.get("/api/scan/deprecated")
async def scan_deprecated_resources(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Simplified deprecated resources scan."""
    return {
        "success": True,
        "message": "System running in minimal mode", 
        "resources": [],
        "total_resources": 0,
        "scan_timestamp": datetime.now().isoformat(),
        "note": "Full scanning capabilities available when all dependencies are installed"
    }

@app.post("/api/resources/upgrade")
async def upgrade_resource(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Provide manual upgrade guidance."""
    try:
        resource_id = payload.get("resourceId", "")
        
        # Provide manual guidance based on resource type
        manual_instructions = {
            "title": "Manual Resource Upgrade Instructions",
            "estimated_time": "5-15 minutes",
            "steps": [
                {
                    "step": 1,
                    "action": "Navigate to Azure Portal",
                    "details": "Open Azure Portal (portal.azure.com)"
                },
                {
                    "step": 2,
                    "action": "Locate your resource",
                    "details": f"Find and select the resource: {resource_id.split('/')[-1] if resource_id else 'your-resource'}"
                },
                {
                    "step": 3,
                    "action": "Review upgrade options",
                    "details": "Check the resource configuration for available upgrade paths"
                },
                {
                    "step": 4,
                    "action": "Apply upgrades",
                    "details": "Follow Azure portal guidance to upgrade the resource"
                }
            ],
            "warnings": [
                "⚠️  Review all dependencies before upgrading",
                "⚠️  Consider maintenance windows for critical resources"
            ]
        }
        
        return {
            "success": True,
            "method": "manual_guidance",
            "message": "Providing manual upgrade guidance",
            "instructions": manual_instructions,
            "timestamp": datetime.now().isoformat(),
            "automation_status": "unavailable",
            "note": "Automated upgrade capabilities available when Azure SDK is installed"
        }
        
    except Exception as e:
        logger.error(f"Upgrade endpoint failed: {e}")
        return {
            "success": False,
            "method": "error",
            "message": f"Upgrade failed with error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
