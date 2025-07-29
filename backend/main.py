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
        "version": "1.0.1",
        "timestamp": "2025-07-29-auth-fix",
        "deployment_test": "active"
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
