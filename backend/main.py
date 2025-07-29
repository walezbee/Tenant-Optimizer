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

app = FastAPI(title="Azure Tenant Optimizer")

# Security configuration
security = HTTPBearer()

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

# Serve assets directly for frontend compatibility  
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

@app.get("/")
def read_root():
    return FileResponse('static/index.html')

@app.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0-working",
        "message": "Application fully restored with asset serving"
    }

async def verify_azure_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Verify Azure AD JWT token and extract user information.
    """
    token = credentials.credentials
    
    try:
        # Decode token without signature verification for testing
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        logger.info(f"Token decoded successfully. Audience: {decoded.get('aud')}")
        
        # Check basic token structure
        if not decoded.get("aud") or not decoded.get("iss"):
            logger.error("Token missing required audience or issuer")
            raise HTTPException(status_code=401, detail="Invalid token structure")
        
        # Check issuer is from Microsoft
        issuer = decoded.get("iss", "")
        if not ("login.microsoftonline.com" in issuer or "sts.windows.net" in issuer):
            logger.error(f"Invalid token issuer: {issuer}")
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        
        # Return user info
        return {
            "user_id": decoded.get("oid", decoded.get("sub", "unknown")),
            "username": decoded.get("unique_name", decoded.get("upn", "unknown")),
            "tenant_id": decoded.get("tid", "unknown"),
            "token": token,
            "decoded": decoded
        }
        
    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@app.get("/api/subscriptions")
async def get_subscriptions(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Get Azure subscriptions accessible to the user."""
    try:
        token = user_info['token']
        
        # Azure Management API endpoint for subscriptions
        url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                subscriptions = result.get("value", [])
                
                # Format subscriptions for frontend
                formatted_subscriptions = []
                for sub in subscriptions:
                    formatted_subscriptions.append({
                        "subscriptionId": sub.get("subscriptionId", ""),
                        "displayName": sub.get("displayName", ""),
                        "state": sub.get("state", ""),
                        "tenantId": sub.get("tenantId", "")
                    })
                
                logger.info(f"Successfully fetched {len(formatted_subscriptions)} subscriptions")
                return {
                    "success": True,
                    "subscriptions": formatted_subscriptions,
                    "count": len(formatted_subscriptions)
                }
            
            elif response.status_code == 403:
                logger.error("Insufficient permissions to list subscriptions")
                return {
                    "success": False,
                    "error": "Insufficient permissions",
                    "message": "User does not have permission to list subscriptions",
                    "subscriptions": []
                }
            
            else:
                logger.error(f"Failed to fetch subscriptions: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API Error {response.status_code}",
                    "message": response.text,
                    "subscriptions": []
                }
                
    except Exception as e:
        logger.error(f"Error fetching subscriptions: {str(e)}")
        return {
            "success": False,
            "error": "Request failed",
            "message": str(e),
            "subscriptions": []
        }

@app.get("/api/test/upgrade-agents")
def test_upgrade_agents():
    """Test endpoint to show system status."""
    return {
        "status": "test_completed",
        "system_mode": "manual_guidance_mode",
        "upgrade_agents": {
            "public_ip_agent": {
                "loaded": False,
                "status": "Manual guidance available"
            },
            "load_balancer_agent": {
                "loaded": False,
                "status": "Manual guidance available"
            },
            "storage_account_agent": {
                "loaded": False,
                "status": "Manual guidance available"
            },
            "orchestrator": {
                "loaded": False,
                "status": "Manual guidance available"
            }
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

@app.post("/api/scan/orphaned")
async def scan_orphaned_resources(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Scan for orphaned Azure resources."""
    try:
        token = user_info['token']
        
        # Extract subscriptions from payload
        subscriptions = payload.get("subscriptions", [])
        
        # Basic query for orphaned disks
        query = """
        Resources
        | where type == "microsoft.compute/disks"
        | where isnull(properties.managedBy)
        | project id, name, resourceGroup, location, type, properties.diskSizeGB, subscriptionId
        | limit 50
        """
        
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Build request data
        data = {"query": query}
        if subscriptions:
            data["subscriptions"] = subscriptions
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                resources = result.get("data", [])
                
                # Format resources for frontend
                formatted_resources = []
                for resource in resources:
                    formatted_resources.append({
                        "id": resource.get("id", ""),
                        "name": resource.get("name", ""),
                        "type": resource.get("type", ""),
                        "resourceGroup": resource.get("resourceGroup", ""),
                        "location": resource.get("location", ""),
                        "subscriptionId": resource.get("subscriptionId", ""),
                        "priority": "Medium",
                        "cost_impact": f"${resource.get('properties_diskSizeGB', 0) * 0.05:.2f}/month estimated",
                        "analysis": "Orphaned disk - not attached to any VM"
                    })
                
                return {
                    "success": True,
                    "message": f"Found {len(formatted_resources)} orphaned resources",
                    "resources": formatted_resources,
                    "total_resources": len(formatted_resources),
                    "scan_timestamp": datetime.now().isoformat(),
                    "subscriptions_scanned": len(subscriptions) if subscriptions else "all"
                }
            else:
                return {
                    "success": False,
                    "message": f"Resource Graph API error: {response.status_code} - {response.text}",
                    "resources": [],
                    "total_resources": 0
                }
                
    except Exception as e:
        logger.error(f"Orphaned scan failed: {e}")
        return {
            "success": False,
            "message": f"Scan failed: {str(e)}",
            "resources": [],
            "total_resources": 0
        }

@app.post("/api/scan/deprecated")
async def scan_deprecated_resources(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Scan for deprecated Azure resources."""
    try:
        token = user_info['token']
        
        # Extract subscriptions from payload
        subscriptions = payload.get("subscriptions", [])
        
        # Basic query for deprecated resources
        query = """
        Resources
        | where type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers")
        | where properties.sku.name == "Basic"
        | project id, name, resourceGroup, location, type, subscriptionId
        | limit 50
        """
        
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Build request data
        data = {"query": query}
        if subscriptions:
            data["subscriptions"] = subscriptions
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                resources = result.get("data", [])
                
                # Format resources for frontend
                formatted_resources = []
                for resource in resources:
                    resource_type = resource.get("type", "")
                    if "publicipaddresses" in resource_type:
                        upgrade_type = "public_ip"
                        description = "Basic SKU Public IP (deprecated)"
                    elif "loadbalancers" in resource_type:
                        upgrade_type = "load_balancer"
                        description = "Basic SKU Load Balancer (deprecated)"
                    else:
                        upgrade_type = "unknown"
                        description = "Deprecated configuration"
                    
                    formatted_resources.append({
                        "id": resource.get("id", ""),
                        "name": resource.get("name", ""),
                        "type": resource.get("type", ""),
                        "resourceGroup": resource.get("resourceGroup", ""),
                        "location": resource.get("location", ""),
                        "subscriptionId": resource.get("subscriptionId", ""),
                        "priority": "High",
                        "upgrade_type": upgrade_type,
                        "analysis": description,
                        "recommendation": "Upgrade to Standard SKU for better performance"
                    })
                
                return {
                    "success": True,
                    "message": f"Found {len(formatted_resources)} deprecated resources",
                    "resources": formatted_resources,
                    "total_resources": len(formatted_resources),
                    "scan_timestamp": datetime.now().isoformat(),
                    "subscriptions_scanned": len(subscriptions) if subscriptions else "all"
                }
            else:
                return {
                    "success": False,
                    "message": f"Resource Graph API error: {response.status_code} - {response.text}",
                    "resources": [],
                    "total_resources": 0
                }
                
    except Exception as e:
        logger.error(f"Deprecated scan failed: {e}")
        return {
            "success": False,
            "message": f"Scan failed: {str(e)}",
            "resources": [],
            "total_resources": 0
        }

@app.post("/api/resources/delete")
async def delete_resource(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Delete an Azure resource."""
    try:
        resource_id = payload.get("resourceId")
        if not resource_id:
            raise HTTPException(status_code=400, detail="Resource ID is required")
        
        logger.info(f"🗑️ Deleting resource: {resource_id}")
        
        # Use Azure Resource Manager API to delete the resource
        url = f"https://management.azure.com{resource_id}?api-version=2021-04-01"
        headers = {"Authorization": f"Bearer {user_info['token']}"}
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.delete(url, headers=headers)
            
            if response.status_code in [200, 202, 204]:
                logger.info("✅ Resource deletion initiated successfully")
                return {
                    "success": True,
                    "message": "Resource deletion initiated",
                    "status": "deleted" if response.status_code == 200 else "deletion_initiated",
                    "resourceId": resource_id
                }
            else:
                logger.error(f"❌ Failed to delete resource: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "message": f"Failed to delete resource: {response.status_code} - {response.text}",
                    "resourceId": resource_id
                }
                
    except Exception as e:
        logger.error(f"Delete resource error: {str(e)}")
        return {
            "success": False,
            "message": f"Delete failed: {str(e)}",
            "resourceId": payload.get("resourceId", "unknown")
        }

@app.post("/api/resources/upgrade")
async def upgrade_resource(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Provide manual upgrade guidance for Azure resources."""
    try:
        resource_id = payload.get("resourceId", "")
        
        if not resource_id:
            raise HTTPException(status_code=400, detail="Resource ID is required")
        
        # Determine resource type from ID
        resource_name = resource_id.split('/')[-1] if resource_id else "your-resource"
        
        if "publicipaddresses" in resource_id.lower():
            instructions = {
                "title": "Public IP Address Upgrade (Basic to Standard SKU)",
                "estimated_time": "5-10 minutes",
                "resource_name": resource_name,
                "steps": [
                    {
                        "step": 1,
                        "action": "Navigate to Azure Portal",
                        "details": "Open Azure Portal (portal.azure.com) and search for 'Public IP addresses'"
                    },
                    {
                        "step": 2,
                        "action": "Locate your Public IP",
                        "details": f"Find and click on: {resource_name}"
                    },
                    {
                        "step": 3,
                        "action": "Check associations",
                        "details": "Note any associated resources (VMs, Load Balancers, etc.)"
                    },
                    {
                        "step": 4,
                        "action": "Dissociate if needed",
                        "details": "If attached, dissociate from resources first"
                    },
                    {
                        "step": 5,
                        "action": "Upgrade SKU",
                        "details": "Go to Configuration → Change SKU from Basic to Standard → Save"
                    },
                    {
                        "step": 6,
                        "action": "Re-associate",
                        "details": "Re-attach to original resources"
                    }
                ],
                "warnings": [
                    "⚠️  This will cause temporary downtime",
                    "⚠️  Standard SKU has different pricing"
                ]
            }
        else:
            instructions = {
                "title": "Manual Resource Upgrade",
                "steps": [
                    {
                        "step": 1,
                        "action": "Navigate to Azure Portal",
                        "details": "Open Azure Portal and locate your resource"
                    },
                    {
                        "step": 2,
                        "action": "Review upgrade options",
                        "details": "Check available configuration upgrades"
                    },
                    {
                        "step": 3,
                        "action": "Apply upgrades",
                        "details": "Follow Azure portal guidance to upgrade"
                    }
                ]
            }
        
        return {
            "success": True,
            "method": "manual_guidance",
            "message": "Providing manual upgrade guidance",
            "instructions": instructions,
            "timestamp": datetime.now().isoformat(),
            "resourceId": resource_id,
            "portalUrl": f"https://portal.azure.com/#@/resource{resource_id}"
        }
        
    except Exception as e:
        logger.error(f"Upgrade endpoint failed: {e}")
        return {
            "success": False,
            "message": f"Upgrade failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
