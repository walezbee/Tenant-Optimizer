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
from typing import Dict, Any

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tenant-optimizer")

# Security configuration
security = HTTPBearer()

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
            logger.warning(f"Unexpected token audience: {audience}. Expected: https://management.azure.com/")
            # Don't fail hard - log for debugging but continue
        
        # Extract user information
        user_info = {
            "user_id": decoded.get("oid"),
            "user_email": decoded.get("upn") or decoded.get("email") or decoded.get("preferred_username"),
            "tenant_id": decoded.get("tid"),
            "name": decoded.get("name"),
            "token": token,
            "audience": audience,
            "issuer": issuer
        }
        
        logger.info(f"User authenticated: {user_info.get('user_email')} from tenant {user_info.get('tenant_id')}")
        return user_info
        
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

# Create FastAPI app
app = FastAPI(title="Tenant Optimizer API", version="1.0.0")

# CORS middleware
origins = [
    "https://tenant-optimizer-web.azurewebsites.net",
    "http://localhost:3000",
    "http://localhost:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")

@app.get("/api/test")
def api_test():
    """Test endpoint to verify API routing works."""
    return {"message": "API routing works!", "timestamp": "2025-07-29", "routing": "fixed"}

@app.get("/direct-test")
def direct_test():
    """Direct test endpoint without API prefix."""
    return {"message": "Direct endpoint works!", "timestamp": "2025-07-29", "deployment": "active"}

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "ok",
        "message": "Tenant Optimizer API is running",
        "version": "1.0.2",
        "timestamp": "2025-07-29-openai-fix",
        "deployment_test": "active",
        "openai_configured": bool(os.getenv("OPENAI_KEY"))
    }

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

@app.get("/user")
async def get_user_info(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Get current user information from token."""
    return {
        "user_id": user_info.get("user_id"),
        "email": user_info.get("user_email"),
        "name": user_info.get("name"),
        "tenant_id": user_info.get("tenant_id")
    }

# API endpoints that require authentication
@app.get("/api/subscriptions")
async def list_subscriptions(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """
    List user's Azure subscriptions using their token.
    """
    logger.info(f"📋 Subscription request from user: {user_info.get('user_email')}")
    logger.info(f"🔑 Token audience: {user_info.get('audience')}")
    logger.info(f"🏢 Tenant ID: {user_info.get('tenant_id')}")
    
    try:
        url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
        headers = {"Authorization": f"Bearer {user_info['token']}"}
        
        logger.info(f"📡 Calling Azure API: {url}")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            logger.info(f"📡 Azure API response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"❌ Azure API error response: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            
        subscriptions = [
            {
                "subscriptionId": sub["subscriptionId"],
                "displayName": sub["displayName"],
                "state": sub["state"]
            }
            for sub in data.get("value", [])
        ]
        
        logger.info(f"✅ Found {len(subscriptions)} subscriptions")
        return {"subscriptions": subscriptions}
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Azure API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch subscriptions: {e.response.text}")
    except Exception as e:
        logger.error(f"Subscription fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/test-resource-graph")
async def test_resource_graph(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Test Resource Graph API connectivity."""
    try:
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
        headers = {"Authorization": f"Bearer {user_info['token']}", "Content-Type": "application/json"}
        
        # Simple test query
        payload = {
            "subscriptions": [],  # Empty to query all accessible subscriptions
            "query": "Resources | limit 1"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=payload)
            
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "error": response.text if response.status_code != 200 else None
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/scan/orphaned")
async def scan_orphaned(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """
    Scan for orphaned Azure resources.
    """
    try:
        from agents.detect_orphaned import detect_orphaned_resources
        
        subscriptions = payload.get("subscriptions", [])
        if not subscriptions:
            raise HTTPException(status_code=400, detail="No subscriptions provided")
            
        result = await detect_orphaned_resources(user_info["token"], subscriptions)
        return {"orphaned": result}
        
    except Exception as e:
        logger.error(f"Orphaned scan error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")

@app.post("/api/scan/deprecated")
async def scan_deprecated(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """
    Scan for deprecated Azure resources.
    """
    try:
        from agents.detect_deprecated import detect_deprecated_resources
        
        subscriptions = payload.get("subscriptions", [])
        if not subscriptions:
            raise HTTPException(status_code=400, detail="No subscriptions provided")
            
        result = await detect_deprecated_resources(user_info["token"], subscriptions)
        return {"deprecated": result}
        
    except Exception as e:
        logger.error(f"Deprecated scan error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")

@app.post("/api/resources/delete")
async def delete_resource(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """
    Delete an orphaned Azure resource.
    Expected payload: {"resourceId": "full-azure-resource-id"}
    """
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
            
            if response.status_code == 200 or response.status_code == 202:
                logger.info(f"✅ Resource deletion initiated successfully")
                return {
                    "success": True,
                    "message": "Resource deletion initiated successfully",
                    "resourceId": resource_id,
                    "status": "deletion_initiated"
                }
            elif response.status_code == 404:
                logger.warning(f"⚠️ Resource not found (may already be deleted)")
                return {
                    "success": True,
                    "message": "Resource not found (may already be deleted)",
                    "resourceId": resource_id,
                    "status": "not_found"
                }
            else:
                logger.error(f"❌ Delete failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to delete resource: {response.text}"
                )
                
    except Exception as e:
        logger.error(f"❌ Resource deletion error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")

@app.post("/api/resources/upgrade")
async def upgrade_resource(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """
    Automated upgrade of Azure resources with graceful fallback to manual guidance.
    Attempts automated upgrade if agents are available, otherwise provides intelligent manual instructions.
    Expected payload: {"resourceId": "full-azure-resource-id", "upgradeType": "sku-upgrade|version-upgrade"}
    """
    try:
        resource_id = payload.get("resourceId")
        upgrade_type = payload.get("upgradeType", "sku-upgrade")
        
        if not resource_id:
            raise HTTPException(status_code=400, detail="Resource ID is required")
        
        logger.info(f"🔧 Starting upgrade for resource: {resource_id} (type: {upgrade_type})")
        
        # Check if automated agents are available
        automation_available = False
        
        try:
            # Try to import the orchestrator
            from agents.upgrade_orchestrator import upgrade_resource_automated
            automation_available = True
            logger.info("✅ Automated upgrade agents available - attempting automated upgrade")
        except ImportError as e:
            logger.warning(f"⚠️  Automated upgrade agents not available: {e}")
            logger.info("🔄 Falling back to intelligent manual guidance mode")
        except Exception as e:
            logger.error(f"❌ Error importing automated upgrade system: {e}")
            logger.info("🔄 Falling back to intelligent manual guidance mode")
        
        # Attempt automated upgrade if available
        if automation_available:
            try:
                # Extract subscription ID from token or resource ID
                subscription_id = await extract_subscription_id(user_info['token'], resource_id)
                if not subscription_id:
                    raise HTTPException(status_code=400, detail="Could not determine subscription ID")
                
                logger.info("🤖 Attempting automated upgrade...")
                
                # Set up Azure credentials using the user's token
                import os
                os.environ['AZURE_ACCESS_TOKEN'] = user_info['token']
                
                upgrade_result = await upgrade_resource_automated(subscription_id, resource_id)
                
                if upgrade_result.get('success', False):
                    logger.info(f"✅ Automated upgrade completed successfully: {resource_id}")
                    
                    # Enhanced response for successful automated upgrades
                    response = {
                        "success": True,
                        "method": "automated",
                        "message": "🎉 Automated upgrade completed successfully!",
                        "resourceId": resource_id,
                        "automationDetails": {
                            "agent_used": upgrade_result.get('orchestration', {}).get('agent_used', 'Unknown'),
                            "automation_level": "Full",
                            "steps_completed": upgrade_result.get('steps_completed', []),
                            "manual_intervention_required": False
                        },
                        "upgradeDetails": upgrade_result.get('upgrade_details', {}),
                        "status": "automated_upgrade_completed",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Add specific messaging based on resource type
                    resource_type = upgrade_result.get('orchestration', {}).get('resource_type', '')
                    if 'publicIPAddresses' in resource_type:
                        response["message"] = "🎉 Public IP automatically upgraded! All associations preserved."
                    elif 'loadBalancers' in resource_type:
                        response["message"] = "🎉 Load Balancer automatically upgraded! All configurations preserved."
                    elif 'storageAccounts' in resource_type:
                        response["message"] = "🎉 Storage Account automatically optimized! Performance improved."
                        
                    return response
                    
                elif upgrade_result.get('skipped', False):
                    logger.info(f"⏭️ Upgrade skipped (already optimal): {resource_id}")
                    return {
                        "success": True,
                        "method": "automated",
                        "message": upgrade_result.get('message', 'Resource is already optimally configured'),
                        "resourceId": resource_id,
                        "skipped": True,
                        "status": "no_upgrade_needed",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                else:
                    # Automated upgrade failed, fall back to manual guidance
                    error_message = upgrade_result.get('error', 'Unknown error')
                    logger.warning(f"⚠️ Automated upgrade failed, falling back to manual guidance: {error_message}")
                    # Continue to manual guidance fallback
                    
            except Exception as e:
                logger.error(f"❌ Automated upgrade failed with error: {e}")
                logger.info("🔄 Falling back to intelligent manual guidance")
                # Continue to manual guidance fallback
        
        # Manual guidance fallback (always available)
        logger.info("📋 Providing intelligent manual guidance")
        return await provide_manual_upgrade_guidance(resource_id, user_info['token'], 
                                                   "Automated upgrade unavailable - providing manual guidance")
                
    except Exception as e:
        logger.error(f"❌ Upgrade endpoint failed: {e}")
        
        # Final fallback - basic manual guidance
        try:
            return await provide_manual_upgrade_guidance(resource_id, user_info.get('token', ''), str(e))
        except:
            return {
                "success": False,
                "method": "error",
                "message": f"Upgrade failed with error: {str(e)}",
                "resourceId": resource_id,
                "timestamp": datetime.now().isoformat(),
                "support_note": "Please contact Azure Support for assistance"
            }

async def extract_subscription_id(token: str, resource_id: str) -> Optional[str]:
    """Extract subscription ID from resource ID or validate with Azure."""
    try:
        # First, try to extract from resource ID
        parts = resource_id.strip('/').split('/')
        if len(parts) >= 2 and parts[0] == 'subscriptions':
            return parts[1]
        
        # If not found in resource ID, return None to trigger error
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract subscription ID: {str(e)}")
        return None

async def provide_manual_upgrade_guidance(resource_id: str, token: str, error_context: str) -> Dict[str, Any]:
    """Provide detailed manual upgrade guidance when automation fails."""
    try:
        # Get resource details for context
        url = f"https://management.azure.com{resource_id}?api-version=2021-04-01"
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                resource_data = response.json()
                resource_type = resource_data.get("type", "").lower()
                resource_name = resource_data.get("name", "")
                
                if "publicipaddress" in resource_type:
                    return {
                        "success": False,
                        "message": "Manual upgrade required!",
                        "resourceId": resource_id,
                        "resourceType": "microsoft.network/publicipaddresses",
                        "manualUpgradeRequired": True,
                        "reason": "Public IP cannot be upgraded while in use. To upgrade this Public IP:",
                        "upgradeSteps": [
                            "1. Dissociate it from the attached resource (Network Interface, Load Balancer, etc.)",
                            "2. Upgrade the SKU to Standard", 
                            "3. Re-associate it with the resource"
                        ],
                        "detailedSteps": [
                            "Navigate to Azure Portal",
                            "Open the Public IP resource",
                            "Dissociate from attached resources", 
                            "Change SKU from Basic to Standard",
                            "Re-associate with resources"
                        ],
                        "alternativeOption": "Alternatively, create a new Standard SKU Public IP and replace the existing one.",
                        "azurePortalUrl": f"https://portal.azure.com/#@/resource{resource_id}",
                        "errorContext": error_context
                    }
                
                elif "loadbalancer" in resource_type:
                    return {
                        "success": False,
                        "message": "Manual Load Balancer upgrade guidance",
                        "resourceId": resource_id,
                        "resourceType": "microsoft.network/loadbalancers",
                        "manualUpgradeRequired": True,
                        "upgradeSteps": [
                            "1. Ensure all associated Public IPs are Standard SKU",
                            "2. Upgrade the Load Balancer SKU to Standard",
                            "3. Verify all frontend and backend configurations"
                        ],
                        "azurePortalUrl": f"https://portal.azure.com/#@/resource{resource_id}",
                        "errorContext": error_context
                    }
        
        # Generic fallback
        return {
            "success": False,
            "message": "Manual upgrade required - automated system encountered constraints",
            "resourceId": resource_id,
            "manualUpgradeRequired": True,
            "azurePortalUrl": f"https://portal.azure.com/#@/resource{resource_id}",
            "errorContext": error_context,
            "recommendation": "Please review the resource in Azure Portal and apply upgrades manually"
        }
        
    except Exception as e:
        logger.error(f"Failed to provide manual guidance: {str(e)}")
        return {
            "success": False,
            "message": "Upgrade guidance unavailable",
            "resourceId": resource_id,
            "error": str(e)
        }

@app.post("/api/resources/upgrade-batch")
async def upgrade_multiple_resources(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """
    Automated batch upgrade of multiple Azure resources with dependency resolution.
    Expected payload: {"resources": [{"id": "resource-id", "type": "optional-type"}]}
    """
    try:
        resources = payload.get("resources", [])
        if not resources:
            raise HTTPException(status_code=400, detail="No resources provided for batch upgrade")
        
        logger.info(f"🚀 Starting batch automated upgrade for {len(resources)} resources")
        
        # Extract subscription ID from first resource
        first_resource_id = resources[0].get("id", "")
        subscription_id = await extract_subscription_id(user_info['token'], first_resource_id)
        if not subscription_id:
            raise HTTPException(status_code=400, detail="Could not determine subscription ID")
        
        # Use the automated upgrade orchestrator for batch processing
        from agents.upgrade_orchestrator import upgrade_multiple_resources_automated
        
        # Set up Azure credentials using the user's token
        import os
        os.environ['AZURE_ACCESS_TOKEN'] = user_info['token']
        
        batch_result = await upgrade_multiple_resources_automated(subscription_id, resources)
        
        if batch_result.get('success', False):
            logger.info(f"✅ Batch automated upgrade completed: {batch_result['successful_upgrades']}/{batch_result['total_resources']} successful")
            
            return {
                "success": True,
                "message": f"🎉 Batch upgrade completed! {batch_result['successful_upgrades']} of {batch_result['total_resources']} resources upgraded successfully.",
                "batchResults": {
                    "total_resources": batch_result['total_resources'],
                    "successful_upgrades": batch_result['successful_upgrades'],
                    "failed_upgrades": batch_result['failed_upgrades'],
                    "skipped_upgrades": batch_result['skipped_upgrades'],
                    "individual_results": batch_result['individual_results']
                },
                "automationDetails": {
                    "dependency_resolution": "Enabled",
                    "automation_level": "Full",
                    "batch_processing": True
                },
                "status": "batch_upgrade_completed"
            }
        else:
            logger.warning(f"⚠️ Batch upgrade had issues: {batch_result.get('error', 'Unknown error')}")
            return {
                "success": False,
                "message": f"Batch upgrade encountered issues: {batch_result.get('error', 'Unknown error')}",
                "batchResults": batch_result,
                "partialSuccess": batch_result.get('successful_upgrades', 0) > 0
            }
                
    except Exception as e:
        logger.error(f"❌ Batch automated upgrade system error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch upgrade system failed: {str(e)}")

@app.post("/api/test/simulate-upgrade")
async def simulate_upgrade(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """
    Simulate an automated upgrade without actually modifying resources.
    This allows testing the upgrade logic safely.
    Expected payload: {"resourceId": "full-azure-resource-id", "upgradeType": "sku-upgrade"}
    """
    try:
        resource_id = payload.get("resourceId")
        upgrade_type = payload.get("upgradeType", "sku-upgrade")
        
        if not resource_id:
            raise HTTPException(status_code=400, detail="Resource ID is required")
        
        logger.info(f"🧪 Simulating automated upgrade: {resource_id} (type: {upgrade_type})")
        
        # Extract resource type for simulation
        resource_type = None
        if "/publicIPAddresses/" in resource_id:
            resource_type = "Microsoft.Network/publicIPAddresses"
        elif "/loadBalancers/" in resource_id:
            resource_type = "Microsoft.Network/loadBalancers"
        elif "/storageAccounts/" in resource_id:
            resource_type = "Microsoft.Storage/storageAccounts"
        
        if not resource_type:
            return {
                "success": False,
                "message": "Could not determine resource type for simulation",
                "resourceId": resource_id,
                "simulation": True
            }
        
        # Simulate the upgrade process
        simulation_result = {
            "success": True,
            "message": f"🧪 SIMULATION: Automated upgrade would complete successfully!",
            "resourceId": resource_id,
            "simulation": True,
            "automationDetails": {
                "agent_used": f"upgrade_{resource_type.split('/')[-1].lower()}",
                "automation_level": "Full",
                "manual_intervention_required": False,
                "steps_completed": []
            },
            "upgradeDetails": {
                "resource_type": resource_type,
                "simulation_mode": True
            },
            "status": "simulation_completed"
        }
        
        # Add resource-specific simulation details
        if "publicIPAddresses" in resource_type:
            simulation_result["automationDetails"]["steps_completed"] = [
                "✅ [SIMULATED] Retrieved Public IP configuration",
                "✅ [SIMULATED] Identified attached resources",
                "✅ [SIMULATED] Would dissociate from attached resources",
                "✅ [SIMULATED] Would upgrade SKU from Basic to Standard",
                "✅ [SIMULATED] Would re-associate with resources"
            ]
            simulation_result["upgradeDetails"].update({
                "original_sku": "Basic (simulated)",
                "new_sku": "Standard (simulated)",
                "attached_resources_count": 1,
                "dissociation_success": True,
                "upgrade_success": True,
                "re_association_success": True
            })
            
        elif "loadBalancers" in resource_type:
            simulation_result["automationDetails"]["steps_completed"] = [
                "✅ [SIMULATED] Validated upgrade compatibility",
                "✅ [SIMULATED] Would preserve frontend IP configurations",
                "✅ [SIMULATED] Would preserve backend address pools",
                "✅ [SIMULATED] Would preserve load balancing rules",
                "✅ [SIMULATED] Would upgrade SKU from Basic to Standard"
            ]
            simulation_result["upgradeDetails"].update({
                "original_sku": "Basic (simulated)",
                "new_sku": "Standard (simulated)",
                "frontend_configs_count": 1,
                "backend_pools_count": 1,
                "rules_count": 2
            })
            
        elif "storageAccounts" in resource_type:
            simulation_result["automationDetails"]["steps_completed"] = [
                "✅ [SIMULATED] Analyzed storage account configuration",
                "✅ [SIMULATED] Would identify optimization opportunities",
                "✅ [SIMULATED] Would apply performance and efficiency upgrades",
                "✅ [SIMULATED] Would validate new configuration"
            ]
            simulation_result["upgradeDetails"].update({
                "original_sku": "Standard_LRS (simulated)",
                "new_sku": "Standard_ZRS (simulated)",
                "upgrades_applied": ["Zone redundancy upgrade"],
                "performance_improvements": ["Higher availability with zone redundancy"]
            })
        
        logger.info(f"✅ Simulation completed successfully: {resource_id}")
        return simulation_result
        
    except Exception as e:
        logger.error(f"❌ Simulation error: {str(e)}")
        return {
            "success": False,
            "error": f"Simulation failed: {str(e)}",
            "resourceId": resource_id,
            "simulation": True
        }

# Automated upgrade system integrated above - old manual functions removed
# The new system uses specialized agents for each resource type with full automation

@app.get("/")
def serve_index():
    """Serve the main index page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Welcome to Tenant Optimizer API"}

# Static catch-all route must be LAST to avoid catching API routes
@app.get("/{full_path:path}")
async def spa_catch_all(full_path: str):
    """Catch-all route for SPA - MUST BE LAST."""
    # Skip API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    file_candidate = os.path.join(STATIC_DIR, full_path)
    if os.path.exists(file_candidate) and os.path.isfile(file_candidate):
        return FileResponse(file_candidate)
    
    # Return index.html for SPA routes
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    
    return {"message": "File not found", "requested": full_path}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
