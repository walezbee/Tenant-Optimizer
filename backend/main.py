import os
import logging
import jwt
import httpx
import json
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from agents.detect_orphaned import detect_orphaned_resources
from agents.delete_orphaned import delete_orphaned_resources
from agents.detect_deprecated import detect_deprecated_resources
from agents.upgrade_deprecated import upgrade_deprecated_resources

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("tenant-optimizer")

app = FastAPI()

origins = [
    "https://tenant-optimizer-web.azurewebsites.net",
    "http://localhost:3000",  # For development
    "http://localhost:5173"   # For Vite dev server
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use HTTPBearer for proper token extraction
security = HTTPBearer()

# Expected audience (your backend API client ID)
EXPECTED_AUDIENCE = os.getenv("AZURE_CLIENT_ID", "b0a762fa-2904-4726-b991-871dbfe84f28")

async def validate_azure_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates Azure AD JWT token and extracts user information.
    For production, implement proper JWT validation with signing key verification.
    """
    token = credentials.credentials
    
    try:
        # For development - decode without verification (NOT for production!)
        # In production, you should verify the signature using Azure AD's public keys
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        # Basic validation
        now = datetime.now(timezone.utc).timestamp()
        if decoded.get('exp', 0) < now:
            raise HTTPException(status_code=401, detail="Token expired")
            
        # Validate audience if present
        aud = decoded.get('aud')
        if aud and aud not in [EXPECTED_AUDIENCE, "https://management.azure.com/"]:
            logger.warning(f"Token audience mismatch: {aud}")
        
        logger.info(f"Token validated for user: {decoded.get('name', 'unknown')}")
        return token
        
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(status_code=401, detail="Token validation failed")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount(
    "/static", 
    StaticFiles(directory=STATIC_DIR, html=True),
    name="static"
)

@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}

@app.get("/subscriptions")
async def list_subscriptions(token: str = Depends(validate_azure_token)):
    """
    Uses the user's token to list all visible subscriptions.
    """
    headers = {
        "Authorization": f"Bearer {token}"
    }
    url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.error(f"/subscriptions: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = resp.json()
        return [
            {
                "subscriptionId": sub["subscriptionId"],
                "displayName": sub["displayName"]
            }
            for sub in data.get("value", [])
        ]

@app.post("/scan/orphaned")
async def scan_orphaned(payload: dict, token: str = Depends(validate_azure_token)):
    logger.info("scan_orphaned: called")
    try:
        subscriptions = payload.get("subscriptions")
        if not subscriptions:
            raise HTTPException(status_code=400, detail="subscriptions are required")
        result = await detect_orphaned_resources(token, subscriptions)
        logger.info(f"scan_orphaned: result: {result}")
        return result
    except Exception as e:
        logger.error(f"scan_orphaned: exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scan/deprecated")
async def scan_deprecated(payload: dict, token: str = Depends(validate_azure_token)):
    logger.info("scan_deprecated: called")
    try:
        subscriptions = payload.get("subscriptions")
        if not subscriptions:
            raise HTTPException(status_code=400, detail="subscriptions are required")
        result = await detect_deprecated_resources(token, subscriptions)
        logger.info(f"scan_deprecated: result: {result}")
        return result
    except Exception as e:
        logger.error(f"scan_deprecated: exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete/orphaned")
async def delete_orphaned(approval_payload: dict, token: str = Depends(validate_azure_token)):
    logger.info("delete_orphaned: called")
    logger.info(f"delete_orphaned: payload: {approval_payload}")
    try:
        result = await delete_orphaned_resources(token, approval_payload)
        logger.info(f"delete_orphaned: result: {result}")
        return result
    except Exception as e:
        logger.error(f"delete_orphaned: exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upgrade/deprecated")
async def upgrade_deprecated(approval_payload: dict, token: str = Depends(validate_azure_token)):
    logger.info("upgrade_deprecated: called")
    logger.info(f"upgrade_deprecated: payload: {approval_payload}")
    try:
        result = await upgrade_deprecated_resources(token, approval_payload)
        logger.info(f"upgrade_deprecated: result: {result}")
        return result
    except Exception as e:
        logger.error(f"upgrade_deprecated: exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/{full_path:path}", include_in_schema=False)
async def spa_catch_all(full_path: str, request: Request):
    file_candidate = os.path.join(STATIC_DIR, full_path)
    if os.path.exists(file_candidate) and os.path.isfile(file_candidate):
        return FileResponse(file_candidate)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))