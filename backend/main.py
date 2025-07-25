from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2AuthorizationCodeBearer
from fastapi.staticfiles import StaticFiles
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

# Mount static files (your frontend build) at the root
app.mount(
    "/", 
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True),
    name="static"
)

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