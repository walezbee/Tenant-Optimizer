from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
load_dotenv()

from agents.detect_orphaned import detect_orphaned_resources
from agents.delete_orphaned import delete_orphaned_resources
from agents.detect_deprecated import detect_deprecated_resources
from agents.upgrade_deprecated import upgrade_deprecated_resources

app = FastAPI()

# --- CORS Middleware ---
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

# Mount static files at /static
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount(
    "/static", 
    StaticFiles(directory=STATIC_DIR, html=True),
    name="static"
)

@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}

@app.get("/scan/orphaned")
async def scan_orphaned(token: str = Depends(oauth2_scheme)):
    return detect_orphaned_resources(token)

@app.post("/delete/orphaned")
async def delete_orphaned(approval_payload: dict, token: str = Depends(oauth2_scheme)):
    return delete_orphaned_resources(token, approval_payload)

@app.get("/scan/deprecated")
async def scan_deprecated(token: str = Depends(oauth2_scheme)):
    return detect_deprecated_resources(token)

@app.post("/upgrade/deprecated")
async def upgrade_deprecated(approval_payload: dict, token: str = Depends(oauth2_scheme)):
    return upgrade_deprecated_resources(token, approval_payload)

# --- Serve SPA index.html at root ---
@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

# --- SPA catch-all for client-side routing ---
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_catch_all(full_path: str, request: Request):
    file_candidate = os.path.join(STATIC_DIR, full_path)
    if os.path.exists(file_candidate) and os.path.isfile(file_candidate):
        return FileResponse(file_candidate)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))