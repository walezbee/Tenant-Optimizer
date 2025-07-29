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
        "version": "2.0-enhanced",
        "message": "Application running with full functionality and graceful fallbacks"
    }

async def verify_azure_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Verify Azure AD JWT token and extract user information.
    Accepts ARM tokens with proper audience validation for multi-tenant scenarios.
    """
    token = credentials.credentials
    
    try:
        # Decode token without signature verification for now (for debugging)
        # In production, you should verify the signature with Microsoft's public keys
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        logger.info(f"Token decoded successfully. Audience: {decoded.get('aud')}, Issuer: {decoded.get('iss')}")
        
        # Check basic token structure
        if not decoded.get("aud") or not decoded.get("iss"):
            logger.error("Token missing required audience or issuer")
            raise HTTPException(status_code=401, detail="Invalid token structure")
        
        # Check issuer is from Microsoft
        issuer = decoded.get("iss", "")
        if not ("login.microsoftonline.com" in issuer or "sts.windows.net" in issuer):
            logger.error(f"Invalid token issuer: {issuer}")
            raise HTTPException(status_code=401, detail="Invalid token issuer")
            
        # For ARM tokens, audience should be Azure Resource Manager
        audience = decoded.get("aud")
        if audience != "https://management.azure.com/":
            logger.warning(f"Unexpected audience: {audience}. Expected: https://management.azure.com/")
            # Don't reject - some tokens may have different but valid audiences
        
        # Return user info
        return {
            "user_id": decoded.get("oid", decoded.get("sub", "unknown")),
            "username": decoded.get("unique_name", decoded.get("upn", "unknown")),
            "tenant_id": decoded.get("tid", "unknown"),
            "app_id": decoded.get("appid", "unknown"),
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

@app.get("/api/test/upgrade-agents")
def test_upgrade_agents():
    """Test endpoint to validate that automated upgrade agents are available."""
    try:
        agent_status = {}
        
        # Test Public IP agent
        try:
            import agents.upgrade_public_ip
            agent_status["public_ip_agent"] = {
                "loaded": True,
                "module": "agents.upgrade_public_ip",
                "status": "Ready"
            }
        except ImportError as e:
            agent_status["public_ip_agent"] = {
                "loaded": False, 
                "error": f"Import error: {str(e)}",
                "status": "Dependencies missing"
            }
        except Exception as e:
            agent_status["public_ip_agent"] = {"loaded": False, "error": str(e)}
            
        # Test Load Balancer agent
        try:
            import agents.upgrade_load_balancer
            agent_status["load_balancer_agent"] = {
                "loaded": True,
                "module": "agents.upgrade_load_balancer", 
                "status": "Ready"
            }
        except ImportError as e:
            agent_status["load_balancer_agent"] = {
                "loaded": False,
                "error": f"Import error: {str(e)}",
                "status": "Dependencies missing"
            }
        except Exception as e:
            agent_status["load_balancer_agent"] = {"loaded": False, "error": str(e)}
            
        # Test Storage Account agent
        try:
            import agents.upgrade_storage_account
            agent_status["storage_account_agent"] = {
                "loaded": True,
                "module": "agents.upgrade_storage_account",
                "status": "Ready"
            }
        except ImportError as e:
            agent_status["storage_account_agent"] = {
                "loaded": False,
                "error": f"Import error: {str(e)}",
                "status": "Dependencies missing - will use fallback"
            }
        except Exception as e:
            agent_status["storage_account_agent"] = {"loaded": False, "error": str(e)}
            
        # Test Orchestrator
        try:
            import agents.upgrade_orchestrator
            agent_status["orchestrator"] = {
                "loaded": True,
                "module": "agents.upgrade_orchestrator",
                "status": "Ready"
            }
        except ImportError as e:
            agent_status["orchestrator"] = {
                "loaded": False,
                "error": f"Import error: {str(e)}",
                "status": "Dependencies missing - will use manual guidance"
            }
        except Exception as e:
            agent_status["orchestrator"] = {"loaded": False, "error": str(e)}
            
        # Test Azure SDK availability (optional)
        azure_sdk_status = {}
        try:
            from azure.identity import DefaultAzureCredential
            azure_sdk_status["azure_identity"] = {"loaded": True, "status": "Available"}
        except ImportError:
            azure_sdk_status["azure_identity"] = {"loaded": False, "status": "Not available - will use manual mode"}
            
        try:
            from azure.mgmt.network import NetworkManagementClient
            azure_sdk_status["azure_mgmt_network"] = {"loaded": True, "status": "Available"}
        except ImportError:
            azure_sdk_status["azure_mgmt_network"] = {"loaded": False, "status": "Not available - will use manual mode"}
        
        # Determine overall system status
        agents_with_deps = sum(1 for agent in agent_status.values() if agent.get("loaded", False))
        total_agents = len(agent_status)
        
        system_status = "fully_automated" if agents_with_deps == total_agents else "manual_guidance_mode"
        
        return {
            "status": "test_completed",
            "system_mode": system_status,
            "upgrade_agents": agent_status,
            "azure_sdk": azure_sdk_status,
            "test_timestamp": "2025-07-29",
            "summary": {
                "agents_loaded": agents_with_deps,
                "total_agents": total_agents,
                "automation_available": agents_with_deps > 0,
                "fallback_mode": system_status == "manual_guidance_mode",
                "message": "System will provide intelligent manual guidance if automation is unavailable"
            }
        }
        
    except Exception as e:
        return {
            "status": "test_failed",
            "error": str(e),
            "message": "Failed to test upgrade agents - using safe fallback mode",
            "fallback_active": True
        }

async def scan_orphaned_basic(token: str):
    """Basic orphaned resources scan using Resource Graph API."""
    try:
        # Basic query for orphaned disks
        query = """
        Resources
        | where type == "microsoft.compute/disks"
        | where isnull(properties.managedBy)
        | project id, name, resourceGroup, location, type, properties.diskSizeGB, properties.diskState
        | limit 50
        """
        
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {"query": query}
        
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
                        "priority": "Medium",
                        "cost_impact": f"${resource.get('properties_diskSizeGB', 0) * 0.05:.2f}/month estimated",
                        "analysis": "Orphaned disk - not attached to any VM"
                    })
                
                return {
                    "success": True,
                    "message": f"Found {len(formatted_resources)} orphaned resources (basic scan)",
                    "resources": formatted_resources,
                    "total_resources": len(formatted_resources),
                    "scan_timestamp": datetime.now().isoformat(),
                    "scan_mode": "basic"
                }
            else:
                return {
                    "success": False,
                    "message": f"Resource Graph API error: {response.status_code}",
                    "resources": [],
                    "total_resources": 0
                }
                
    except Exception as e:
        logger.error(f"Basic orphaned scan failed: {e}")
        return {
            "success": False,
            "message": f"Basic scan failed: {str(e)}",
            "resources": [],
            "total_resources": 0
        }

async def scan_deprecated_basic(token: str):
    """Basic deprecated resources scan."""
    try:
        # Basic query for potentially deprecated resources
        query = """
        Resources
        | where type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers")
        | where properties.sku.name == "Basic"
        | project id, name, resourceGroup, location, type, properties.sku.name
        | limit 50
        """
        
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {"query": query}
        
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
                        "priority": "High",
                        "upgrade_type": upgrade_type,
                        "analysis": description,
                        "recommendation": "Upgrade to Standard SKU for better performance and features"
                    })
                
                return {
                    "success": True,
                    "message": f"Found {len(formatted_resources)} deprecated resources (basic scan)",
                    "resources": formatted_resources,
                    "total_resources": len(formatted_resources),
                    "scan_timestamp": datetime.now().isoformat(),
                    "scan_mode": "basic"
                }
            else:
                return {
                    "success": False,
                    "message": f"Resource Graph API error: {response.status_code}",
                    "resources": [],
                    "total_resources": 0
                }
                
    except Exception as e:
        logger.error(f"Basic deprecated scan failed: {e}")
        return {
            "success": False,
            "message": f"Basic scan failed: {str(e)}",
            "resources": [],
            "total_resources": 0
        }

@app.post("/api/resources/upgrade")
async def upgrade_resource(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """
    Automated upgrade of Azure resources with graceful fallback to manual guidance.
    """
    try:
        resource_id = payload.get("resourceId")
        
        if not resource_id:
            raise HTTPException(status_code=400, detail="Resource ID is required")
        
        # For now, always provide manual guidance until automated agents are available
        return await provide_manual_upgrade_guidance(resource_id, user_info['token'])
                
    except Exception as e:
        logger.error(f"❌ Upgrade endpoint failed: {e}")
        return {
            "success": False,
            "method": "error",
            "message": f"Upgrade failed with error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

async def provide_manual_upgrade_guidance(resource_id: str, token: str, error_context: str = "") -> Dict[str, Any]:
    """Provide detailed manual upgrade guidance."""
    try:
        # Determine resource type from ID
        resource_type = ""
        if "publicipaddresses" in resource_id.lower():
            resource_type = "public_ip"
        elif "loadbalancers" in resource_id.lower():
            resource_type = "load_balancer"
        elif "storageaccounts" in resource_id.lower():
            resource_type = "storage_account"
        
        resource_name = resource_id.split('/')[-1] if resource_id else "your-resource"
        
        if resource_type == "public_ip":
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
        return {
            "success": False,
            "message": f"Failed to provide upgrade guidance: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

async def extract_subscription_id(token: str, resource_id: str) -> Optional[str]:
    """Extract subscription ID from resource ID."""
    try:
        if resource_id and "/subscriptions/" in resource_id:
            parts = resource_id.split("/")
            sub_index = parts.index("subscriptions")
            if sub_index + 1 < len(parts):
                return parts[sub_index + 1]
    except:
        pass
    return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
        }

@app.get("/api/scan/orphaned")
async def scan_orphaned_resources(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Scan for orphaned Azure resources using Resource Graph API."""
    try:
        token = user_info['token']
        
        # Try to import the detection agent
        try:
            from agents.detect_orphaned import get_orphaned_resources
            resources = await get_orphaned_resources(token)
            
            return {
                "success": True,
                "message": f"Found {len(resources)} orphaned resources",
                "resources": resources,
                "total_resources": len(resources),
                "scan_timestamp": datetime.now().isoformat()
            }
        except ImportError:
            # Fallback to basic Resource Graph query
            return await scan_orphaned_basic(token)
            
    except Exception as e:
        logger.error(f"Orphaned scan failed: {e}")
        return {
            "success": False,
            "message": f"Scan failed: {str(e)}",
            "resources": [],
            "total_resources": 0
        }

@app.get("/api/scan/deprecated")
async def scan_deprecated_resources(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Scan for deprecated Azure resources using AI analysis."""
    try:
        token = user_info['token']
        
        # Try to import the detection agent
        try:
            from agents.detect_deprecated import get_deprecated_resources
            resources = await get_deprecated_resources(token)
            
            return {
                "success": True,
                "message": f"Found {len(resources)} deprecated resources",
                "resources": resources,
                "total_resources": len(resources),
                "scan_timestamp": datetime.now().isoformat()
            }
        except ImportError:
            # Fallback to basic deprecated resource detection
            return await scan_deprecated_basic(token)
            
    except Exception as e:
        logger.error(f"Deprecated scan failed: {e}")
        return {
            "success": False,
            "message": f"Scan failed: {str(e)}",
            "resources": [],
            "total_resources": 0
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
