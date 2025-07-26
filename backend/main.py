from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from dotenv import load_dotenv
load_dotenv()

from agents.detect_orphaned import detect_orphaned_resources
from agents.delete_orphaned import delete_orphaned_resources
from agents.detect_deprecated import detect_deprecated_resources
from agents.upgrade_deprecated import upgrade_deprecated_resources

app = FastAPI()
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    tokenUrl="https://login.microsoftonline.com/common/oauth2/v2.0/token"
)

# Mount static files at /static (NOT at "/")
app.mount(
    "/static", 
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True),
    name="static"
)

@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
def root():
    """Serve the React app index.html at the root path"""
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))

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

@app.get("/{full_path:path}", include_in_schema=False)
def catch_all(full_path: str):
    """
    Catch-all route for React Router SPA support.
    Serves static files if they exist, otherwise serves index.html for client-side routing.
    """
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    file_path = os.path.join(static_dir, full_path)
    
    # If the requested file exists in static directory, let StaticFiles handle it
    # This shouldn't happen often since StaticFiles is mounted at /static/
    # But this is a safety check
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    # For all other routes (like /dashboard, /reports), serve index.html for React Router
    return FileResponse(os.path.join(static_dir, "index.html"))