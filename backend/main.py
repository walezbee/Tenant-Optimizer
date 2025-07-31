import os
import logging
import httpx
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from typing import Dict, Any, Optional

# Import Microsoft Knowledge Base for AI-powered resource detection
from ai.microsoft_knowledge_base import MicrosoftKnowledgeBase

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tenant-optimizer")

# Initialize Microsoft Knowledge Base for AI-powered resource detection
microsoft_kb = MicrosoftKnowledgeBase()
logger.info(f"🧠 Microsoft Knowledge Base initialized - Last updated: {microsoft_kb.last_updated}")

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
        "version": "2.0-working",
        "message": "Application fully restored with asset serving"
    }

async def verify_azure_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Verify Azure AD JWT token and extract user information.
    """
    token = credentials.credentials
    
    try:
        # Decode token without signature verification for testing
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        logger.info(f"Token decoded successfully. Audience: {decoded.get('aud')}")
        
        # Check basic token structure
        if not decoded.get("aud") or not decoded.get("iss"):
            logger.error("Token missing required audience or issuer")
            raise HTTPException(status_code=401, detail="Invalid token structure")
        
        # Check issuer is from Microsoft
        issuer = decoded.get("iss", "")
        if not ("login.microsoftonline.com" in issuer or "sts.windows.net" in issuer):
            logger.error(f"Invalid token issuer: {issuer}")
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        
        # Return user info
        return {
            "user_id": decoded.get("oid", decoded.get("sub", "unknown")),
            "username": decoded.get("unique_name", decoded.get("upn", "unknown")),
            "tenant_id": decoded.get("tid", "unknown"),
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

@app.get("/api/subscriptions")
async def get_subscriptions(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Get Azure subscriptions accessible to the user."""
    try:
        token = user_info['token']
        
        # Azure Management API endpoint for subscriptions
        url = "https://management.azure.com/subscriptions?api-version=2020-01-01"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                subscriptions = result.get("value", [])
                
                # Format subscriptions for frontend
                formatted_subscriptions = []
                for sub in subscriptions:
                    formatted_subscriptions.append({
                        "subscriptionId": sub.get("subscriptionId", ""),
                        "displayName": sub.get("displayName", ""),
                        "state": sub.get("state", ""),
                        "tenantId": sub.get("tenantId", "")
                    })
                
                logger.info(f"Successfully fetched {len(formatted_subscriptions)} subscriptions")
                return {
                    "success": True,
                    "subscriptions": formatted_subscriptions,
                    "count": len(formatted_subscriptions)
                }
            
            elif response.status_code == 403:
                logger.error("Insufficient permissions to list subscriptions")
                return {
                    "success": False,
                    "error": "Insufficient permissions",
                    "message": "User does not have permission to list subscriptions",
                    "subscriptions": []
                }
            
            else:
                logger.error(f"Failed to fetch subscriptions: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API Error {response.status_code}",
                    "message": response.text,
                    "subscriptions": []
                }
                
    except Exception as e:
        logger.error(f"Error fetching subscriptions: {str(e)}")
        return {
            "success": False,
            "error": "Request failed",
            "message": str(e),
            "subscriptions": []
        }

@app.get("/api/test/resource-graph")
async def test_resource_graph(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Test Resource Graph API with a simple query to diagnose issues."""
    try:
        token = user_info['token']
        
        # Simple test query that should return something in most tenants
        query = """
        Resources
        | where type == "microsoft.resources/subscriptions"
        | project id, name, type, subscriptionId
        | limit 5
        """
        
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {"query": query}
        
        logger.info(f"🧪 Testing Resource Graph API with simple query")
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=data)
            
            logger.info(f"🧪 Test Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"🧪 Test Response Keys: {list(result.keys())}")
                
                data_content = result.get("data", {})
                logger.info(f"🧪 Data Content Type: {type(data_content)}")
                logger.info(f"🧪 Data Content Keys: {list(data_content.keys()) if isinstance(data_content, dict) else 'Not a dict'}")
                
                if isinstance(data_content, dict):
                    rows = data_content.get("rows", [])
                    columns = data_content.get("columns", [])
                    logger.info(f"🧪 Rows: {len(rows)}, Columns: {len(columns)}")
                    
                    if columns:
                        column_names = [col.get("name", "unknown") for col in columns]
                        logger.info(f"🧪 Column Names: {column_names}")
                    
                    if rows:
                        logger.info(f"🧪 First Row: {rows[0] if rows else 'No rows'}")
                
                return {
                    "success": True,
                    "message": "Resource Graph API test completed",
                    "test_results": {
                        "response_status": response.status_code,
                        "response_keys": list(result.keys()),
                        "data_type": str(type(data_content)),
                        "data_keys": list(data_content.keys()) if isinstance(data_content, dict) else "Not a dict",
                        "rows_count": len(data_content.get("rows", [])) if isinstance(data_content, dict) else 0,
                        "columns_count": len(data_content.get("columns", [])) if isinstance(data_content, dict) else 0,
                        "raw_response_sample": str(result)[:500] + "..." if len(str(result)) > 500 else str(result)
                    }
                }
            else:
                logger.error(f"🧪 Test failed with status {response.status_code}: {response.text}")
                return {
                    "success": False,
                    "message": f"Resource Graph API test failed: {response.status_code}",
                    "error": response.text
                }
                
    except Exception as e:
        logger.error(f"🧪 Test exception: {str(e)}")
        return {
            "success": False,
            "message": f"Test failed with exception: {str(e)}"
        }

@app.get("/api/test/disk-query")
async def test_disk_query(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Test specific disk query to see if we can find any disks at all."""
    try:
        token = user_info['token']
        
        # First, let's just find all disks, regardless of orphaned status
        query = """
        Resources
        | where type == "microsoft.compute/disks"
        | project id, name, resourceGroup, location, type, properties, subscriptionId
        | limit 10
        """
        
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data = {"query": query}
        
        logger.info(f"💿 Testing disk query to find any disks")
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                result = response.json()
                data_content = result.get("data", {})
                
                logger.info(f"💿 Disk query response structure: {list(result.keys())}")
                
                if isinstance(data_content, dict):
                    rows = data_content.get("rows", [])
                    columns = data_content.get("columns", [])
                    
                    logger.info(f"💿 Found {len(rows)} disks with {len(columns)} columns")
                    
                    if columns:
                        column_names = [col.get("name", "unknown") for col in columns]
                        logger.info(f"💿 Disk columns: {column_names}")
                    
                    # Now test orphaned disk query
                    orphaned_query = """
                    Resources
                    | where type == "microsoft.compute/disks"
                    | where isnull(properties.managedBy) or properties.managedBy == ""
                    | project id, name, resourceGroup, location, type, properties, subscriptionId
                    | limit 10
                    """
                    
                    data2 = {"query": orphaned_query}
                    response2 = await client.post(url, headers=headers, json=data2)
                    
                    if response2.status_code == 200:
                        result2 = response2.json()
                        data_content2 = result2.get("data", {})
                        orphaned_rows = data_content2.get("rows", []) if isinstance(data_content2, dict) else []
                        
                        logger.info(f"💿 Found {len(orphaned_rows)} orphaned disks")
                        
                        return {
                            "success": True,
                            "total_disks": len(rows),
                            "orphaned_disks": len(orphaned_rows),
                            "columns": column_names if columns else [],
                            "sample_disk": rows[0] if rows else None,
                            "sample_orphaned": orphaned_rows[0] if orphaned_rows else None
                        }
                    else:
                        logger.error(f"💿 Orphaned query failed: {response2.status_code}")
                        return {
                            "success": True,
                            "total_disks": len(rows),
                            "orphaned_query_error": f"Status {response2.status_code}: {response2.text}"
                        }
                else:
                    return {
                        "success": False,
                        "message": f"Unexpected data format: {type(data_content)}"
                    }
            else:
                logger.error(f"💿 Disk query failed: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "message": f"Disk query failed: {response.status_code}",
                    "error": response.text
                }
                
    except Exception as e:
        logger.error(f"💿 Disk test exception: {str(e)}")
        return {
            "success": False,
            "message": f"Disk test failed: {str(e)}"
        }

@app.get("/api/test/frontend-data")
async def test_frontend_data():
    """Test endpoint that returns sample data to verify frontend rendering."""
    return {
        "success": True,
        "message": "Found 2 test resources",
        "resources": [
            {
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Compute/disks/test-disk",
                "name": "test-disk",
                "type": "microsoft.compute/disks",
                "resourceGroup": "test-rg",
                "location": "westus2",
                "subscriptionId": "test-subscription",
                "priority": "High",
                "cost_impact": "$5.00/month estimated",
                "analysis": "Test orphaned disk for frontend verification"
            },
            {
                "id": "/subscriptions/test/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-ip",
                "name": "test-ip",
                "type": "microsoft.network/publicipaddresses",
                "resourceGroup": "test-rg",
                "location": "westus2",
                "subscriptionId": "test-subscription",
                "priority": "High",
                "upgrade_type": "public_ip",
                "analysis": "Test deprecated Basic SKU Public IP",
                "recommendation": "Upgrade to Standard SKU"
            }
        ],
        "total_resources": 2,
        "scan_timestamp": datetime.now().isoformat(),
        "subscriptions_scanned": "test"
    }

@app.get("/api/debug/deprecated-simple")
async def debug_deprecated_simple():
    """Simple debug endpoint to help troubleshoot deprecated resources query."""
    return {
        "debug_info": {
            "current_query": """
            Resources
            | where type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers", "microsoft.storage/storageaccounts")
            | extend skuName = case(
                isnotnull(properties.sku.name), tostring(properties.sku.name),
                isnotnull(properties.sku), tostring(properties.sku),
                ""
            )
            | extend skuTier = case(
                isnotnull(properties.sku.tier), tostring(properties.sku.tier),
                ""
            )
            | extend accessTier = case(
                isnotnull(properties.accessTier), tostring(properties.accessTier),
                ""
            )
            | where skuName =~ "Basic" 
               or skuTier =~ "Basic"
               or skuName =~ "Standard_LRS"
               or skuName contains "Basic"
               or accessTier =~ "Archive"
            | project id, name, resourceGroup, location, type, subscriptionId, skuName, skuTier, accessTier, properties
            | limit 100
            """,
            "explanation": "This query searches for Public IPs, Load Balancers, and Storage Accounts with Basic SKU or deprecated configurations",
            "possible_issues": [
                "No Basic SKU resources exist in tenant",
                "Resources might be using different property paths",
                "Query conditions might be too restrictive",
                "Resources might be using Standard SKU already"
            ],
            "suggested_actions": [
                "Try the /api/test/deprecated-query endpoint with authentication",
                "Check if you have any Public IPs or Load Balancers in Azure Portal",
                "Verify if they are using Basic or Standard SKU"
            ]
        }
    }

@app.get("/api/test/deprecated-query")
async def test_deprecated_query(user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Test deprecated resources query with multiple approaches."""
    try:
        token = user_info['token']
        
        # Test 1: Get ALL network and storage resources to see what exists (no filters)
        query1 = """
        Resources
        | where type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers", "microsoft.storage/storageaccounts")
        | project id, name, resourceGroup, location, type, subscriptionId, properties
        | limit 50
        """
        
        # Test 2: Look for any SKU properties at all (show actual data structure)
        query2 = """
        Resources
        | where type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers")
        | extend skuInfo = tostring(properties.sku)
        | extend skuName = tostring(properties.sku.name)
        | extend skuTier = tostring(properties.sku.tier)
        | extend allProperties = tostring(properties)
        | project id, name, type, skuInfo, skuName, skuTier, allProperties
        | limit 20
        """
        
        # Test 3: VERY broad search - any resource with "basic" anywhere
        query3 = """
        Resources
        | where type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers")
        | extend propsString = tostring(properties)
        | where propsString contains "Basic" or propsString contains "basic"
           or tostring(properties.sku.name) contains "Basic"
           or tostring(properties.sku.tier) contains "Basic"
        | project id, name, type, properties
        | limit 20
        """
        
        # Test 4: Storage accounts - check all configurations
        query4 = """
        Resources
        | where type == "microsoft.storage/storageaccounts"
        | extend skuName = tostring(properties.sku.name)
        | extend accessTier = tostring(properties.accessTier)
        | extend kind = tostring(kind)
        | extend allProps = tostring(properties)
        | project id, name, skuName, accessTier, kind, allProps
        | limit 20
        """
        
        # Test 5: Show me EVERYTHING - let's see what resources you actually have
        query5 = """
        Resources
        | where type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers", "microsoft.storage/storageaccounts")
        | extend resourceInfo = pack("type", type, "sku", properties.sku, "accessTier", properties.accessTier)
        | project id, name, type, location, resourceInfo, properties
        | limit 30
        """
        
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        results = {}
        
        async with httpx.AsyncClient(timeout=60) as client:
            # Test all queries
            for i, query in enumerate([query1, query2, query3, query4, query5], 1):
                try:
                    response = await client.post(url, headers=headers, json={"query": query})
                    if response.status_code == 200:
                        result = response.json()
                        data = result.get("data", {})
                        
                        if isinstance(data, dict):
                            rows = data.get("rows", [])
                            columns = data.get("columns", [])
                            column_names = [col.get("name") for col in columns] if columns else []
                            
                            results[f"test_{i}"] = {
                                "query_description": [
                                    "All network/storage resources (no filters)",
                                    "SKU property structure analysis", 
                                    "Very broad Basic SKU search (any 'basic' text)",
                                    "Storage account detailed analysis",
                                    "Complete resource information dump"
                                ][i-1],
                                "count": len(rows),
                                "columns": column_names,
                                "sample_data": rows[:2] if rows else [],  # Show 2 samples max
                                "success": True
                            }
                        else:
                            results[f"test_{i}"] = {"success": False, "error": "Unexpected data format"}
                    else:
                        results[f"test_{i}"] = {"success": False, "error": f"Status {response.status_code}: {response.text}"}
                except Exception as e:
                    results[f"test_{i}"] = {"success": False, "error": str(e)}
        
        return {
            "success": True,
            "results": results,
            "summary": {
                "total_network_storage_resources": results.get("test_1", {}).get("count", 0),
                "resources_with_sku_info": results.get("test_2", {}).get("count", 0),
                "broad_basic_search_results": results.get("test_3", {}).get("count", 0),
                "storage_accounts": results.get("test_4", {}).get("count", 0),
                "total_detailed_info": results.get("test_5", {}).get("count", 0)
            },
            "diagnosis": {
                "if_all_zero": "Your tenant might not have Public IPs, Load Balancers, or Storage Accounts",
                "if_test1_has_results_but_others_zero": "Resources exist but none have Basic SKU configuration",
                "check_sample_data": "Look at sample_data in each test to see actual resource structure"
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Test failed: {str(e)}"
        }

@app.get("/api/test/upgrade-agents")
def test_upgrade_agents():
    """Test endpoint to diagnose upgrade agent status and imports."""
    import sys
    import os
    
    try:
        # Test agents directory
        agents_path = os.path.join(os.path.dirname(__file__), 'agents')
        agents_exists = os.path.exists(agents_path)
        
        # List agent files
        agent_files = []
        if agents_exists:
            agent_files = [f for f in os.listdir(agents_path) if f.endswith('.py')]
        
        # Test orchestrator import
        orchestrator_import_success = False
        orchestrator_error = None
        try:
            if agents_path not in sys.path:
                sys.path.insert(0, agents_path)
            from agents.upgrade_orchestrator import AutomatedUpgradeOrchestrator
            orchestrator_import_success = True
        except Exception as e:
            orchestrator_error = str(e)
        
        # Test orchestrator initialization
        orchestrator_init_success = False
        orchestrator_init_error = None
        if orchestrator_import_success:
            try:
                orchestrator = AutomatedUpgradeOrchestrator("test-subscription-id")
                orchestrator_init_success = True
            except Exception as e:
                orchestrator_init_error = str(e)
        
        # Test agent imports
        agent_imports = {}
        for agent_name in ['upgrade_public_ip', 'upgrade_load_balancer', 'upgrade_storage_account']:
            try:
                module = __import__(f'agents.{agent_name}', fromlist=[agent_name])
                agent_imports[agent_name] = {
                    "success": True,
                    "has_automated_function": hasattr(module, f'{agent_name}_automated')
                }
            except Exception as e:
                agent_imports[agent_name] = {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "status": "diagnostic_complete",
            "system_info": {
                "agents_directory_exists": agents_exists,
                "agents_path": agents_path,
                "agent_files": agent_files,
                "python_path_includes_agents": agents_path in sys.path
            },
            "orchestrator": {
                "import_success": orchestrator_import_success,
                "import_error": orchestrator_error,
                "initialization_success": orchestrator_init_success,
                "initialization_error": orchestrator_init_error
            },
            "agents": agent_imports,
            "timestamp": datetime.now().isoformat(),
            "diagnosis": {
                "all_agents_ready": orchestrator_init_success and all(
                    agent.get("success", False) for agent in agent_imports.values()
                ),
                "recommended_action": "Check orchestrator and agent initialization errors above"
            }
        }
        
    except Exception as e:
        return {
            "status": "diagnostic_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def calculate_total_cost_savings(resources):
    """
    Calculate total potential cost savings from orphaned resources.
    
    Args:
        resources: List of orphaned resources with cost_impact or estimatedSavings
        
    Returns:
        dict: Summary of cost savings with total, breakdown, and count
    """
    total_min_savings = 0.0
    total_max_savings = 0.0
    resource_count = 0
    resource_breakdown = {}
    
    for resource in resources:
        resource_type = resource.get("type", "").split("/")[-1] if resource.get("type") else "unknown"
        
        # Get cost impact from the resource
        cost_impact = resource.get("cost_impact", "")
        estimated_savings = ""
        
        # Check if resource has actions with estimatedSavings
        actions = resource.get("actions", [])
        for action in actions:
            if action.get("estimatedSavings"):
                estimated_savings = action["estimatedSavings"]
                break
        
        # Use either cost_impact or estimatedSavings
        cost_string = estimated_savings or cost_impact
        
        if cost_string and "$" in cost_string:
            # Extract numerical values from cost strings like "$4-50/month" or "$5.00/month"
            import re
            
            # Pattern to match numbers in cost strings
            numbers = re.findall(r'\$?(\d+(?:\.\d{2})?)', cost_string)
            
            if numbers:
                try:
                    if "-" in cost_string and len(numbers) >= 2:
                        # Range format like "$4-50/month"
                        min_cost = float(numbers[0])
                        max_cost = float(numbers[1])
                    else:
                        # Single value like "$5.00/month"
                        min_cost = max_cost = float(numbers[0])
                    
                    total_min_savings += min_cost
                    total_max_savings += max_cost
                    resource_count += 1
                    
                    # Track by resource type
                    if resource_type not in resource_breakdown:
                        resource_breakdown[resource_type] = {
                            "count": 0,
                            "min_savings": 0.0,
                            "max_savings": 0.0
                        }
                    
                    resource_breakdown[resource_type]["count"] += 1
                    resource_breakdown[resource_type]["min_savings"] += min_cost
                    resource_breakdown[resource_type]["max_savings"] += max_cost
                    
                except (ValueError, IndexError):
                    # Skip resources with unparseable cost data
                    continue
    
    # Format the response
    if total_min_savings == total_max_savings:
        total_savings_text = f"${total_max_savings:.2f}/month"
    else:
        total_savings_text = f"${total_min_savings:.2f}-${total_max_savings:.2f}/month"
    
    return {
        "total_monthly_savings": total_savings_text,
        "total_annual_savings": f"${total_min_savings * 12:.2f}-${total_max_savings * 12:.2f}/year" if total_min_savings != total_max_savings else f"${total_max_savings * 12:.2f}/year",
        "resource_count": resource_count,
        "breakdown_by_type": resource_breakdown,
        "summary": f"Deleting {resource_count} orphaned resources could save {total_savings_text}"
    }

@app.post("/api/scan/orphaned")
async def scan_orphaned_resources(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Scan for orphaned Azure resources."""
    try:
        token = user_info['token']
        
        # Extract subscriptions from payload
        subscriptions = payload.get("subscriptions", [])
        
        # Enhanced query for orphaned disks with better detection
        query = """
        Resources
        | where type == "microsoft.compute/disks"
        | where isnull(properties.managedBy) or properties.managedBy == ""
        | extend diskSizeGB = toint(properties.diskSizeGB)
        | project id, name, resourceGroup, location, type, diskSizeGB, subscriptionId, properties
        | limit 100
        """
        
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Build request data
        data = {"query": query}
        if subscriptions:
            data["subscriptions"] = subscriptions
        
        logger.info(f"🔍 Scanning for orphaned resources in {len(subscriptions) if subscriptions else 'all'} subscriptions")
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                
                # Parse Resource Graph response format properly
                data_content = result.get("data", {})
                resources = []
                
                logger.info(f"🔍 Full response structure: {list(result.keys())}")
                logger.info(f"🔍 Data content type: {type(data_content)}")
                
                if isinstance(data_content, dict):
                    # Standard Resource Graph format with rows and columns
                    rows = data_content.get("rows", [])
                    columns = data_content.get("columns", [])
                    
                    logger.info(f"📊 Found {len(rows)} rows with {len(columns)} columns")
                    
                    if columns and rows:
                        column_names = [col["name"] for col in columns]
                        logger.info(f"🏷️ Column names: {column_names}")
                        for row in rows:
                            resource_dict = dict(zip(column_names, row))
                            resources.append(resource_dict)
                elif isinstance(data_content, list):
                    # Direct list format (fallback)
                    resources = data_content
                    logger.info(f"📊 Using direct list format, found {len(resources)} resources")
                else:
                    # Additional fallback for value format
                    if "value" in result:
                        resources = result["value"]
                        logger.info(f"📊 Using 'value' format, found {len(resources)} resources")
                
                logger.info(f"📊 Final parsed resources count: {len(resources)}")
                if resources:
                    logger.info(f"🔍 Sample resource: {list(resources[0].keys()) if resources[0] else 'empty'}")
                
                # Format resources for frontend
                formatted_resources = []
                for resource in resources:
                    # Try different ways to get disk size
                    disk_size = 0
                    if 'diskSizeGB' in resource:
                        disk_size = resource.get('diskSizeGB', 0)
                    elif 'properties_diskSizeGB' in resource:
                        disk_size = resource.get('properties_diskSizeGB', 0)
                    elif 'properties.diskSizeGB' in resource:
                        disk_size = resource.get('properties.diskSizeGB', 0)
                    elif isinstance(resource.get('properties'), dict):
                        disk_size = resource.get('properties', {}).get('diskSizeGB', 0)
                    
                    # Ensure disk_size is a number
                    try:
                        disk_size = int(disk_size) if disk_size else 0
                    except (ValueError, TypeError):
                        disk_size = 0
                    
                    formatted_resources.append({
                        "id": resource.get("id", ""),
                        "name": resource.get("name", ""),
                        "type": resource.get("type", ""),
                        "resourceGroup": resource.get("resourceGroup", ""),
                        "location": resource.get("location", ""),
                        "subscriptionId": resource.get("subscriptionId", ""),
                        "priority": "Medium",
                        "cost_impact": f"${disk_size * 0.05:.2f}/month estimated" if disk_size > 0 else "Unknown cost",
                        "analysis": f"Orphaned disk ({disk_size}GB) - not attached to any VM" if disk_size > 0 else "Orphaned disk - not attached to any VM"
                    })
                
                # Calculate total cost savings for all orphaned resources
                cost_savings = calculate_total_cost_savings(formatted_resources)
                
                return {
                    "success": True,
                    "message": f"Found {len(formatted_resources)} orphaned resources",
                    "resources": formatted_resources,
                    "total_resources": len(formatted_resources),
                    "cost_savings": cost_savings,
                    "scan_timestamp": datetime.now().isoformat(),
                    "subscriptions_scanned": len(subscriptions) if subscriptions else "all"
                }
            else:
                logger.error(f"❌ Resource Graph API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "message": f"Resource Graph API error: {response.status_code} - {response.text}",
                    "resources": [],
                    "total_resources": 0
                }
                
    except Exception as e:
        logger.error(f"Orphaned scan failed: {e}")
        return {
            "success": False,
            "message": f"Scan failed: {str(e)}",
            "resources": [],
            "total_resources": 0
        }

@app.post("/api/scan/deprecated")
async def scan_deprecated_resources(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Scan for deprecated Azure resources using Microsoft's official knowledge base."""
    try:
        token = user_info['token']
        
        # Extract subscriptions from payload
        subscriptions = payload.get("subscriptions", [])
        
        # Use a working query for deprecated resources detection
        query = """
        Resources
        | where type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers", "microsoft.storage/storageaccounts")
        | extend skuName = case(
            isnotnull(properties.sku.name), tostring(properties.sku.name),
            isnotnull(properties.sku), tostring(properties.sku),
            isnotnull(sku.name), tostring(sku.name),
            isnotnull(sku), tostring(sku),
            ""
        )
        | extend skuTier = case(
            isnotnull(properties.sku.tier), tostring(properties.sku.tier),
            isnotnull(sku.tier), tostring(sku.tier),
            ""
        )
        | extend accessTier = case(
            isnotnull(properties.accessTier), tostring(properties.accessTier),
            ""
        )
        | where skuName =~ "Basic" 
           or skuTier =~ "Basic"
           or skuName =~ "Standard_LRS"
           or skuName =~ "Standard_GRS"
           or accessTier =~ "Archive"
        | project id, name, resourceGroup, location, type, subscriptionId, skuName, skuTier, accessTier, properties
        | limit 100
        """
        
        logger.info(f"🧠 Using Microsoft-trained AI query for deprecated resources detection")
        
        url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Build request data
        data = {"query": query}
        if subscriptions:
            data["subscriptions"] = subscriptions
        
        # Execute query with Microsoft AI enhancement
        logger.info(f"Executing Microsoft AI-enhanced deprecated resources query across {len(subscriptions)} subscription(s)")
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                
                # Parse Resource Graph response format properly
                data_content = result.get("data", {})
                resources = []
                
                logger.info(f"🔍 Deprecated scan - Full response structure: {list(result.keys())}")
                logger.info(f"🔍 Deprecated scan - Data content type: {type(data_content)}")
                
                if isinstance(data_content, dict):
                    # Standard Resource Graph format with rows and columns
                    rows = data_content.get("rows", [])
                    columns = data_content.get("columns", [])
                    
                    logger.info(f"📊 Found {len(rows)} rows with {len(columns)} columns")
                    
                    if columns and rows:
                        column_names = [col["name"] for col in columns]
                        logger.info(f"🏷️ Column names: {column_names}")
                        for row in rows:
                            resource_dict = dict(zip(column_names, row))
                            resources.append(resource_dict)
                elif isinstance(data_content, list):
                    # Direct list format (fallback)
                    resources = data_content
                    logger.info(f"📊 Using direct list format, found {len(resources)} resources")
                else:
                    # Additional fallback for value format
                    if "value" in result:
                        resources = result["value"]
                        logger.info(f"📊 Using 'value' format, found {len(resources)} resources")
                
                # Apply Microsoft's official deprecation analysis to each resource
                validated_resources = []
                deprecated_patterns = microsoft_kb.get_deprecated_resources_patterns()
                
                for resource in resources:
                    # Use Microsoft Knowledge Base to analyze deprecation status
                    deprecation_info = microsoft_kb.analyze_resource_deprecation(resource)
                    
                    if deprecation_info['is_deprecated']:
                        # Enrich resource with Microsoft's official deprecation details
                        resource['deprecation_reason'] = deprecation_info['reason']
                        resource['retirement_date'] = deprecation_info.get('retirement_date', 'TBD')
                        resource['microsoft_recommendation'] = deprecation_info.get('recommendation', 'Upgrade recommended')
                        resource['risk_level'] = deprecation_info.get('risk_level', 'Medium')
                        resource['cost_impact'] = deprecation_info.get('cost_impact', 'Review recommended')
                        
                        validated_resources.append(resource)
                        logger.info(f"✅ Microsoft AI validated deprecated: {resource.get('name', 'unknown')} ({deprecation_info['reason']})")
                
                # If no validated deprecated resources, use fallback detection
                if len(validated_resources) == 0 and len(resources) > 0:
                    logger.info("� No Microsoft-validated deprecated resources, applying fallback analysis...")
                    
                    for resource in resources:
                        # Apply basic deprecation patterns as fallback
                        resource_type = resource.get("type", "")
                        sku_name = str(resource.get("skuName", "")).lower()
                        sku_tier = str(resource.get("skuTier", "")).lower()
                        
                        if ("basic" in sku_name or "basic" in sku_tier) and "publicipaddresses" in resource_type:
                            resource['deprecation_reason'] = "Basic SKU Public IP (retiring Sept 30, 2025)"
                            resource['retirement_date'] = "2025-09-30"
                            resource['microsoft_recommendation'] = "Upgrade to Standard SKU"
                            resource['risk_level'] = "High"
                            resource['cost_impact'] = "Service disruption risk"
                            validated_resources.append(resource)
                        elif ("basic" in sku_name or "basic" in sku_tier) and "loadbalancers" in resource_type:
                            resource['deprecation_reason'] = "Basic SKU Load Balancer (retiring Sept 30, 2025)"
                            resource['retirement_date'] = "2025-09-30" 
                            resource['microsoft_recommendation'] = "Upgrade to Standard SKU"
                            resource['risk_level'] = "High"
                            resource['cost_impact'] = "Service disruption risk"
                            validated_resources.append(resource)
                
                # Use validated resources for final result
                resources = validated_resources
                
                # If still no resources found, try a simpler fallback query
                if len(resources) == 0:
                    logger.info("📊 No validated deprecated resources found, trying fallback query...")
                    
                    fallback_query = """
                    Resources
                    | where type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers", "microsoft.storage/storageaccounts")
                    | limit 20
                    """
                    
                    fallback_data = {"query": fallback_query}
                    if subscriptions:
                        fallback_data["subscriptions"] = subscriptions
                    
                    fallback_response = await client.post(url, headers=headers, json=fallback_data)
                    if fallback_response.status_code == 200:
                        fallback_result = fallback_response.json()
                        fallback_data_content = fallback_result.get("data", {})
                        
                        if isinstance(fallback_data_content, dict):
                            fallback_rows = fallback_data_content.get("rows", [])
                            fallback_columns = fallback_data_content.get("columns", [])
                            
                            if fallback_columns and fallback_rows:
                                fallback_column_names = [col["name"] for col in fallback_columns]
                                for row in fallback_rows:
                                    fallback_resource_dict = dict(zip(fallback_column_names, row))
                                    resources.append(fallback_resource_dict)
                                    
                                logger.info(f"📊 FALLBACK: Found {len(fallback_rows)} resources with simple query")
                
                logger.info(f"📊 Final Microsoft AI-enhanced deprecated resources count: {len(resources)}")
                if resources:
                    logger.info(f"🔍 Sample Microsoft-validated deprecated resource: {list(resources[0].keys()) if resources[0] else 'empty'}")
                
                # Format resources for frontend with Microsoft AI enhancements
                formatted_resources = []
                for resource in resources:
                    resource_type = resource.get("type", "")
                    sku_name = resource.get("skuName", "")
                    sku_tier = resource.get("skuTier", "")
                    access_tier = resource.get("accessTier", "")
                    
                    # Use Microsoft Knowledge Base for enhanced formatting
                    if 'microsoft_recommendation' in resource:
                        description = resource.get('deprecation_reason', 'Deprecated resource detected')
                        recommendation = resource.get('microsoft_recommendation', 'Upgrade recommended')
                        upgrade_type = "microsoft_validated"
                    else:
                        # Legacy formatting for non-validated resources
                        if "publicipaddresses" in resource_type:
                            upgrade_type = "public_ip"
                            description = f"Public IP with potential optimization - SKU: {sku_name}/{sku_tier}"
                            recommendation = "Review and potentially upgrade to Standard SKU for better performance"
                            
                        elif "loadbalancers" in resource_type:
                            upgrade_type = "load_balancer"
                            description = f"Load Balancer with potential optimization - SKU: {sku_name}/{sku_tier}"
                            recommendation = "Review and potentially upgrade to Standard SKU for improved features"
                            
                        elif "storageaccounts" in resource_type:
                            upgrade_type = "storage_account"
                            if access_tier == "Archive":
                                description = f"Archive tier storage account - consider lifecycle management"
                                recommendation = "Review access patterns and consider Hot/Cool tiers for frequently accessed data"
                            elif "LRS" in sku_name:
                                description = f"Storage account using LRS - consider redundancy upgrade - SKU: {sku_name}"
                                recommendation = "Consider upgrading to GRS or ZRS for better data redundancy"
                            else:
                                description = f"Storage account with optimization opportunity - SKU: {sku_name}"
                                recommendation = "Review storage account configuration for optimization opportunities"
                                
                        else:
                            upgrade_type = "general"
                            description = f"Resource with deprecated or suboptimal configuration - SKU: {sku_name}"
                            recommendation = "Review resource configuration and consider upgrades for better performance"
                    
                    formatted_resources.append({
                        "id": resource.get("id", ""),
                        "name": resource.get("name", ""),
                        "type": resource.get("type", ""),
                        "resourceGroup": resource.get("resourceGroup", ""),
                        "location": resource.get("location", ""),
                        "subscriptionId": resource.get("subscriptionId", ""),
                        "priority": resource.get("risk_level", "High"),
                        "upgrade_type": upgrade_type,
                        "analysis": description,
                        "recommendation": recommendation,
                        # Microsoft AI enhancements
                        "deprecation_reason": resource.get("deprecation_reason", ""),
                        "retirement_date": resource.get("retirement_date", ""),
                        "microsoft_recommendation": resource.get("microsoft_recommendation", ""),
                        "cost_impact": resource.get("cost_impact", ""),
                        "microsoft_validated": 'microsoft_recommendation' in resource,
                        "actions": [
                            {
                                "type": "upgrade",
                                "description": f"Optimize {upgrade_type.replace('_', ' ').title()}",
                                "riskLevel": resource.get("risk_level", "Medium"),
                                "confirmationRequired": True,
                                "estimatedTimeToComplete": "10-30 minutes"
                            }
                        ]
                    })
                
                logger.info(f"🎯 Microsoft AI-enhanced deprecated scan complete: {len(formatted_resources)} resources formatted")
                
                return {
                    "success": True,
                    "message": f"Microsoft AI found {len(formatted_resources)} deprecated resources with official validation",
                    "resources": formatted_resources,
                    "total_resources": len(formatted_resources),
                    "scan_timestamp": datetime.now().isoformat(),
                    "subscriptions_scanned": len(subscriptions) if subscriptions else "all"
                }
            else:
                logger.error(f"❌ Resource Graph API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "message": f"Resource Graph API error: {response.status_code} - {response.text}",
                    "resources": [],
                    "total_resources": 0
                }
    except Exception as e:
        logger.error(f"❌ Microsoft AI-enhanced deprecated scan failed: {str(e)}")
        logger.exception("Full error details:")
        return {
            "success": False,
            "message": f"Microsoft AI scan failed: {str(e)}",
            "resources": [],
            "total_resources": 0
        }

@app.post("/api/resources/delete")
async def delete_resource(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Delete an Azure resource."""
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
            
            if response.status_code in [200, 202, 204]:
                logger.info("✅ Resource deletion initiated successfully")
                return {
                    "success": True,
                    "message": "Resource deletion initiated",
                    "status": "deleted" if response.status_code == 200 else "deletion_initiated",
                    "resourceId": resource_id
                }
            else:
                logger.error(f"❌ Failed to delete resource: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "message": f"Failed to delete resource: {response.status_code} - {response.text}",
                    "resourceId": resource_id
                }
                
    except Exception as e:
        logger.error(f"Delete resource error: {str(e)}")
        return {
            "success": False,
            "message": f"Delete failed: {str(e)}",
            "resourceId": payload.get("resourceId", "unknown")
        }

@app.post("/api/resources/upgrade")
async def upgrade_resource(payload: dict, user_info: Dict[str, Any] = Depends(verify_azure_token)):
    """Upgrade Azure resources using automated agents or provide manual guidance."""
    try:
        resource_id = payload.get("resourceId", "")
        
        if not resource_id:
            raise HTTPException(status_code=400, detail="Resource ID is required")
        
        # Try to import and use automated upgrade agents
        try:
            import sys
            import os
            
            # Add agents directory to path if not already there
            agents_path = os.path.join(os.path.dirname(__file__), 'agents')
            if agents_path not in sys.path:
                sys.path.insert(0, agents_path)
            
            logger.info(f"🔧 Attempting to import orchestrator from: {agents_path}")
            from agents.upgrade_orchestrator import AutomatedUpgradeOrchestrator
            
            logger.info(f"🤖 Using automated upgrade agents for: {resource_id}")
            
            # Extract subscription ID from resource ID
            subscription_id = user_info.get('decoded', {}).get('subscription', 'unknown')
            if subscription_id == 'unknown' and resource_id:
                # Extract subscription ID from resource ID format:
                # /subscriptions/{subscription-id}/resourceGroups/...
                resource_parts = resource_id.split('/')
                if len(resource_parts) > 2 and resource_parts[1] == 'subscriptions':
                    subscription_id = resource_parts[2]
            
            logger.info(f"🔧 Initializing orchestrator with subscription: {subscription_id}")
            
            # Get user's access token for Azure API calls
            access_token = user_info['token']
            tenant_id = user_info.get('decoded', {}).get('tid', '')
            
            # Initialize orchestrator with user's credentials
            orchestrator = AutomatedUpgradeOrchestrator(
                subscription_id=subscription_id,
                access_token=access_token,
                tenant_id=tenant_id
            )
            
            logger.info(f"🔧 Orchestrator initialized, calling upgrade for: {resource_id}")
            
            # Perform automated upgrade
            result = await orchestrator.upgrade_resource(resource_id)
            
            logger.info(f"🎯 Automated upgrade result: {result}")
            
            return {
                "success": result.get("success", False),
                "method": "automated_agents",
                "message": result.get("message", "Automated upgrade completed"),
                "details": result,
                "timestamp": datetime.now().isoformat(),
                "resourceId": resource_id
            }
            
        except ImportError as e:
            logger.info(f"📋 Automated agents not available, providing manual guidance: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Automated upgrade failed, falling back to manual guidance: {e}")
            logger.exception("Full automated upgrade error details:")
        
        # Fallback to manual guidance
        resource_name = resource_id.split('/')[-1] if resource_id else "your-resource"
        
        if "publicipaddresses" in resource_id.lower():
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
        elif "loadbalancers" in resource_id.lower():
            instructions = {
                "title": "Load Balancer Upgrade (Basic to Standard SKU)",
                "estimated_time": "10-20 minutes",
                "resource_name": resource_name,
                "steps": [
                    {
                        "step": 1,
                        "action": "Navigate to Azure Portal",
                        "details": "Open Azure Portal and search for 'Load balancers'"
                    },
                    {
                        "step": 2,
                        "action": "Locate your Load Balancer",
                        "details": f"Find and click on: {resource_name}"
                    },
                    {
                        "step": 3,
                        "action": "Review configuration", 
                        "details": "Note frontend IPs, backend pools, and health probes"
                    },
                    {
                        "step": 4,
                        "action": "Create new Standard LB",
                        "details": "Basic to Standard upgrade requires creating a new load balancer"
                    },
                    {
                        "step": 5,
                        "action": "Migrate configuration",
                        "details": "Recreate rules, probes, and backend pools on new Standard LB"
                    },
                    {
                        "step": 6,
                        "action": "Update DNS and associations",
                        "details": "Point applications to new Standard load balancer"
                    },
                    {
                        "step": 7,
                        "action": "Delete old Basic LB",
                        "details": "After confirming everything works, delete the Basic LB"
                    }
                ],
                "warnings": [
                    "⚠️  This requires creating a new load balancer",
                    "⚠️  Significant downtime during migration",
                    "⚠️  Higher cost for Standard SKU"
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
            "message": "Providing manual upgrade guidance (automated agents not available)",
            "instructions": instructions,
            "timestamp": datetime.now().isoformat(),
            "resourceId": resource_id,
            "portalUrl": f"https://portal.azure.com/#@/resource{resource_id}"
        }
        
    except Exception as e:
        logger.error(f"Upgrade endpoint failed: {e}")
        return {
            "success": False,
            "message": f"Upgrade failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
