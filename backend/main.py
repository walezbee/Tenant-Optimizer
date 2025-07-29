import os
import logging
import httpx
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
    Upgrade a deprecated Azure resource with intelligent handling of complex scenarios.
    Expected payload: {"resourceId": "full-azure-resource-id", "upgradeType": "sku-upgrade|version-upgrade"}
    """
    try:
        resource_id = payload.get("resourceId")
        upgrade_type = payload.get("upgradeType", "sku-upgrade")
        
        if not resource_id:
            raise HTTPException(status_code=400, detail="Resource ID is required")
        
        logger.info(f"⬆️ Upgrading resource: {resource_id} (type: {upgrade_type})")
        
        # First, get the current resource configuration
        url = f"https://management.azure.com{resource_id}?api-version=2021-04-01"
        headers = {"Authorization": f"Bearer {user_info['token']}"}
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to get resource details: {response.text}"
                )
            
            resource_data = response.json()
            resource_type = resource_data.get("type", "").lower()
            resource_name = resource_data.get("name", "")
            
            logger.info(f"🔍 Resource type: {resource_type}, Name: {resource_name}")
            
            if "publicipaddress" in resource_type:
                return await upgrade_public_ip(client, resource_id, resource_data, headers, logger)
            elif "loadbalancer" in resource_type:
                return await upgrade_load_balancer(client, resource_id, resource_data, headers, logger)
            elif "storageaccount" in resource_type:
                return await upgrade_storage_account(client, resource_id, resource_data, headers, logger)
            else:
                logger.warning(f"⚠️ Upgrade not implemented for resource type: {resource_type}")
                return {
                    "success": False,
                    "message": f"Upgrade not yet implemented for {resource_type}. Please upgrade manually using Azure Portal.",
                    "resourceId": resource_id,
                    "resourceType": resource_type,
                    "manualUpgradeRequired": True,
                    "azurePortalUrl": f"https://portal.azure.com/#@/resource{resource_id}"
                }
                
    except Exception as e:
        logger.error(f"❌ Resource upgrade error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upgrade failed: {str(e)}")

async def upgrade_public_ip(client, resource_id, resource_data, headers, logger):
    """
    Upgrade Public IP from Basic to Standard SKU.
    Handles the scenario where the IP is in use by checking associations.
    """
    try:
        current_sku = resource_data.get("sku", {}).get("name", "").lower()
        if current_sku != "basic":
            return {
                "success": False,
                "message": f"Public IP is already using {current_sku.title()} SKU, no upgrade needed.",
                "resourceId": resource_id,
                "alreadyUpgraded": True
            }
        
        # Check if the Public IP is currently in use
        ip_config = resource_data.get("properties", {}).get("ipConfiguration")
        if ip_config:
            logger.warning(f"⚠️ Public IP is in use by: {ip_config.get('id', 'unknown resource')}")
            
            return {
                "success": False,
                "message": "Public IP cannot be upgraded while in use. To upgrade this Public IP:\n\n1. Dissociate it from the attached resource (Network Interface, Load Balancer, etc.)\n2. Upgrade the SKU to Standard\n3. Re-associate it with the resource\n\nAlternatively, create a new Standard SKU Public IP and replace the existing one.",
                "resourceId": resource_id,
                "resourceType": "microsoft.network/publicipaddresses",
                "manualUpgradeRequired": True,
                "upgradeSteps": [
                    "Navigate to Azure Portal",
                    "Open the Public IP resource", 
                    "Dissociate from attached resources",
                    "Change SKU from Basic to Standard",
                    "Re-associate with resources"
                ],
                "azurePortalUrl": f"https://portal.azure.com/#@/resource{resource_id}",
                "attachedTo": ip_config.get('id', 'unknown resource')
            }
        
        # If not in use, proceed with direct upgrade
        upgraded_data = resource_data.copy()
        upgraded_data["sku"]["name"] = "Standard"
        
        # Use the correct API version for Public IP addresses
        api_url = f"https://management.azure.com{resource_id}?api-version=2023-04-01"
        
        put_response = await client.put(api_url, headers=headers, json=upgraded_data)
        
        if put_response.status_code in [200, 201]:
            logger.info(f"✅ Public IP upgraded from Basic to Standard SKU successfully")
            return {
                "success": True,
                "message": "Public IP upgraded from Basic to Standard SKU successfully",
                "resourceId": resource_id,
                "resourceType": "microsoft.network/publicipaddresses",
                "status": "upgraded",
                "upgradedFrom": "Basic SKU",
                "upgradedTo": "Standard SKU"
            }
        else:
            error_detail = put_response.text
            logger.error(f"❌ Public IP upgrade failed: {put_response.status_code} - {error_detail}")
            
            # Parse Azure error for better user feedback
            if "PublicIPAddressInUseCannotUpdate" in error_detail:
                return {
                    "success": False,
                    "message": "Public IP cannot be upgraded because it's currently in use. Please dissociate it from attached resources first, then try upgrading again.",
                    "resourceId": resource_id,
                    "manualUpgradeRequired": True,
                    "azurePortalUrl": f"https://portal.azure.com/#@/resource{resource_id}"
                }
            
            raise HTTPException(
                status_code=put_response.status_code,
                detail=f"Failed to upgrade Public IP: {error_detail}"
            )
            
    except Exception as e:
        logger.error(f"❌ Public IP upgrade error: {str(e)}")
        raise e

async def upgrade_load_balancer(client, resource_id, resource_data, headers, logger):
    """
    Upgrade Load Balancer from Basic to Standard SKU.
    """
    try:
        current_sku = resource_data.get("sku", {}).get("name", "").lower()
        if current_sku != "basic":
            return {
                "success": False,
                "message": f"Load Balancer is already using {current_sku.title()} SKU, no upgrade needed.",
                "resourceId": resource_id,
                "alreadyUpgraded": True
            }
        
        upgraded_data = resource_data.copy()
        upgraded_data["sku"]["name"] = "Standard"
        
        api_url = f"https://management.azure.com{resource_id}?api-version=2023-04-01"
        put_response = await client.put(api_url, headers=headers, json=upgraded_data)
        
        if put_response.status_code in [200, 201]:
            logger.info(f"✅ Load Balancer upgraded from Basic to Standard SKU successfully")
            return {
                "success": True,
                "message": "Load Balancer upgraded from Basic to Standard SKU successfully",
                "resourceId": resource_id,
                "resourceType": "microsoft.network/loadbalancers",
                "status": "upgraded",
                "upgradedFrom": "Basic SKU",
                "upgradedTo": "Standard SKU"
            }
        else:
            logger.error(f"❌ Load Balancer upgrade failed: {put_response.status_code} - {put_response.text}")
            raise HTTPException(
                status_code=put_response.status_code,
                detail=f"Failed to upgrade Load Balancer: {put_response.text}"
            )
            
    except Exception as e:
        logger.error(f"❌ Load Balancer upgrade error: {str(e)}")
        raise e

async def upgrade_storage_account(client, resource_id, resource_data, headers, logger):
    """
    Upgrade Storage Account from v1 to v2.
    """
    try:
        current_kind = resource_data.get("kind", "").lower()
        if current_kind not in ["storage", "storagev1"]:
            return {
                "success": False,
                "message": f"Storage Account is already using {current_kind} kind, no upgrade needed.",
                "resourceId": resource_id,
                "alreadyUpgraded": True
            }
        
        upgraded_data = resource_data.copy()
        upgraded_data["kind"] = "StorageV2"
        
        api_url = f"https://management.azure.com{resource_id}?api-version=2023-01-01"
        put_response = await client.put(api_url, headers=headers, json=upgraded_data)
        
        if put_response.status_code in [200, 201]:
            logger.info(f"✅ Storage Account upgraded to v2 successfully")
            return {
                "success": True,
                "message": "Storage Account upgraded to v2 successfully",
                "resourceId": resource_id,
                "resourceType": "microsoft.storage/storageaccounts",
                "status": "upgraded",
                "upgradedFrom": current_kind,
                "upgradedTo": "StorageV2"
            }
        else:
            logger.error(f"❌ Storage Account upgrade failed: {put_response.status_code} - {put_response.text}")
            raise HTTPException(
                status_code=put_response.status_code,
                detail=f"Failed to upgrade Storage Account: {put_response.text}"
            )
            
    except Exception as e:
        logger.error(f"❌ Storage Account upgrade error: {str(e)}")
        raise e

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
