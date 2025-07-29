#!/usr/bin/env python3
"""
Local test server for Tenant Optimizer authentication
Run this locally to test authentication without deployment issues
"""
import os
import logging
import httpx
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Dict, Any
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tenant-optimizer-local")

# Security configuration
security = HTTPBearer()

async def verify_azure_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Verify Azure AD JWT token and extract user information.
    Accepts ARM tokens with proper audience validation for multi-tenant scenarios.
    """
    token = credentials.credentials
    
    try:
        # Decode token without signature verification for testing
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
app = FastAPI(title="Tenant Optimizer Local Test API", version="1.0.0")

# CORS middleware - Allow local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Local Tenant Optimizer API is running",
        "version": "1.0.0-local",
        "timestamp": "2025-07-29"
    }

@app.get("/user")
async def get_user_info(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Get current user information from token."""
    return {
        "user_id": user_info.get("user_id"),
        "email": user_info.get("user_email"),
        "name": user_info.get("name"),
        "tenant_id": user_info.get("tenant_id"),
        "audience": user_info.get("audience"),
        "issuer": user_info.get("issuer")
    }

@app.get("/subscriptions")
async def list_subscriptions(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """List user's Azure subscriptions using their token."""
    try:
        url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
        headers = {"Authorization": f"Bearer {user_info['token']}"}
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
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
        
        return {"subscriptions": subscriptions}
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Azure API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail="Failed to fetch subscriptions")
    except Exception as e:
        logger.error(f"Subscription fetch error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    print("🚀 Starting Tenant Optimizer Local Test Server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("🔍 Health check: http://localhost:8000/health")
    print("👤 User info: http://localhost:8000/user (requires auth)")
    print("📋 Subscriptions: http://localhost:8000/subscriptions (requires auth)")
    print()
    print("💡 To test with frontend:")
    print("   1. Update frontend API_BASE to 'http://localhost:8000'")
    print("   2. Run this server: python local_test_server.py")
    print("   3. Open frontend and test authentication")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
