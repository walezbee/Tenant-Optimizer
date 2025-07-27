import os
import logging
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

import httpx

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
    "https://tenant-optimizer-web.azurewebsites.net"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    tokenUrl="https://login.microsoftonline.com/common/oauth2/v2.0/token"
)

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
async def list_subscriptions(token: str = Depends(oauth2_scheme)):
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
async def scan_orphaned(payload: dict, token: str = Depends(oauth2_scheme)):
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
async def scan_deprecated(payload: dict, token: str = Depends(oauth2_scheme)):
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
async def delete_orphaned(approval_payload: dict, token: str = Depends(oauth2_scheme)):
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
async def upgrade_deprecated(approval_payload: dict, token: str = Depends(oauth2_scheme)):
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