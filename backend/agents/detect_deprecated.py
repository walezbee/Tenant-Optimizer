import os
import httpx
from openai import OpenAI
import json
import logging

logger = logging.getLogger("tenant-optimizer")

async def detect_deprecated_resources(user_token, subscriptions):
    """
    Detects deprecated or outdated resources using the user's token and Resource Graph REST API.
    Args:
        user_token: User's Azure access token.
        subscriptions: List of subscription id strings.
    Returns:
        List of deprecated resources with recommendations.
    """
    # Use the correct Resource Graph API endpoint and version
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }
    
    # Query for resources that might be deprecated/retired
    query = """
    Resources
    | where type in~ (
        'microsoft.network/publicipaddresses',
        'microsoft.compute/virtualmachines',
        'microsoft.network/loadbalancers',
        'microsoft.network/applicationgateways', 
        'microsoft.storage/storageaccounts',
        'microsoft.sql/servers',
        'microsoft.compute/disks',
        'microsoft.web/sites',
        'microsoft.keyvault/vaults',
        'microsoft.containerservice/managedclusters'
    )
    | extend skuName = sku.name, skuTier = sku.tier
    | project id, name, type, kind, location, resourceGroup, skuName, skuTier, sku, tags, properties
    | limit 100
    """
    
    payload = {
        "subscriptions": subscriptions,
        "query": query
    }
    
    logger.info(f"🔍 Querying Resource Graph for potentially deprecated resources in {len(subscriptions)} subscriptions")
    logger.info(f"📡 Resource Graph URL: {url}")
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=payload)
            logger.info(f"📡 Resource Graph response status: {resp.status_code}")
            
            if resp.status_code != 200:
                logger.error(f"❌ Resource Graph error: {resp.text}")
            
            resp.raise_for_status()
            data = resp.json()
            
        # Extract the data from the Resource Graph response
        # Resource Graph can return data in different formats
        data_content = data.get("data", {})
        
        logger.info(f"📊 Resource Graph response structure: {type(data_content)}")
        logger.info(f"📊 Full response keys: {list(data.keys())}")
        
        # Handle different response formats
        if isinstance(data_content, dict):
            # Standard format with rows and columns
            rows = data_content.get("rows", [])
            columns = data_content.get("columns", [])
            
            logger.info(f"📊 Found {len(rows)} rows with {len(columns)} columns")
            
            # Convert rows to dictionaries using column names
            resources = []
            if columns and rows:
                column_names = [col["name"] for col in columns]
                for row in rows:
                    resource_dict = dict(zip(column_names, row))
                    resources.append(resource_dict)
        elif isinstance(data_content, list):
            # Direct list format (some API versions return this)
            resources = data_content
            logger.info(f"📊 Found {len(resources)} resources in list format")
        else:
            # Fallback - check if data is directly in the response
            if "value" in data:
                resources = data["value"]
                logger.info(f"📊 Found {len(resources)} resources in value field")
            else:
                logger.warning("⚠️ Unexpected Resource Graph response format")
                resources = []
    
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Resource Graph HTTP error: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Azure Resource Graph API error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"❌ Resource Graph error: {str(e)}")
        raise Exception(f"Failed to query Azure Resource Graph: {str(e)}")
    
    if not resources:
        logger.info("✅ No resources found to analyze")
        return []

    # Check if OpenAI API key is available and valid
    openai_key = os.getenv("OPENAI_KEY")
    if not openai_key or not openai_key.startswith("sk-"):
        logger.warning(f"⚠️ OpenAI API key {'not found' if not openai_key else 'invalid format'}, using basic analysis")
        return generate_basic_deprecated_analysis(resources)
    
    # Use OpenAI for advanced analysis
    return await analyze_deprecated_resources_with_ai(resources, openai_key)

async def analyze_deprecated_resources_with_ai(resources, openai_key):
    """
    Uses OpenAI to analyze deprecated resources and provide upgrade recommendations with actions.
    """
    client = OpenAI(api_key=openai_key)
    
    prompt = f"""
You are an Azure cloud optimization expert with comprehensive knowledge of Microsoft's deprecation timeline and service retirement announcements.

TASK: Analyze the following Azure resources and identify those using deprecated/retired services, SKUs, or configurations.

MICROSOFT AZURE DEPRECATION KNOWLEDGE (as of 2025):

PUBLIC IP ADDRESSES:
- Basic SKU Public IPs: Deprecated/retiring - migrate to Standard SKU
- IPv4 Public IPs: Still supported but consider IPv6 for future-proofing

VIRTUAL MACHINES:
- A-series (A0-A7): Deprecated - migrate to newer series
- D-series v1: Deprecated - migrate to v2 or newer
- Old OS versions: Windows Server 2008/2012 reaching end of support

LOAD BALANCERS:
- Basic SKU Load Balancers: Being deprecated - migrate to Standard SKU

STORAGE ACCOUNTS:
- Storage Account v1: Deprecated - upgrade to v2

APPLICATION GATEWAYS:
- v1 SKU: Deprecated - migrate to v2

CONTAINER SERVICES:
- AKS versions <1.24: Deprecated

For each deprecated/retired resource found, return a JSON object with:
- resourceId: Full Azure resource ID
- resourceName: Resource name  
- resourceType: Azure resource type
- location: Azure region
- resourceGroup: Resource group name
- issue: Specific deprecation issue with timeline if known
- recommendation: Detailed migration/upgrade path
- priority: "Critical", "High", or "Medium" based on retirement timeline
- migrationComplexity: "Low", "Medium", or "High"
- estimatedMigrationTime: Rough time estimate
- actions: Array of action objects with:
  - type: "upgrade" for upgrade actions
  - description: What the action does
  - riskLevel: "Low", "Medium", or "High"
  - confirmationRequired: true/false
  - estimatedTimeToComplete: Time estimate for the action

RESOURCES TO ANALYZE:
{json.dumps(resources, indent=2)}

Return ONLY a JSON array of resources using deprecated/retired services. If no deprecated resources found, return empty array [].
"""
    
    try:
        logger.info("🤖 Analyzing resources for deprecation with OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an Azure cloud architect and optimization expert with deep knowledge of Microsoft's service deprecation timeline, retirement announcements, and migration best practices."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.1
        )
        
        result = response.choices[0].message.content
        
        # Parse JSON response
        try:
            parsed_result = json.loads(result)
            if isinstance(parsed_result, list):
                logger.info(f"✅ AI analysis completed for deprecated resources")
                return parsed_result
            else:
                return [parsed_result] if isinstance(parsed_result, dict) else []
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ OpenAI returned non-JSON response: {e}")
            return generate_basic_deprecated_analysis(resources)
            
    except Exception as e:
        logger.error(f"❌ OpenAI API error: {str(e)}")
        return generate_basic_deprecated_analysis(resources)

def generate_basic_deprecated_analysis(resources):
    """
    Generates basic deprecation analysis without AI when OpenAI is unavailable.
    """
    logger.info("📊 Generating basic deprecation analysis")
    
    deprecated_resources = []
    for resource in resources:
        resource_type = resource.get("type", "").lower()
        sku_name = resource.get("skuName", "").lower() if resource.get("skuName") else ""
        sku_tier = resource.get("skuTier", "").lower() if resource.get("skuTier") else ""
        
        issue = None
        recommendation = None
        priority = "Medium"
        actions = []
        
        # Public IP Addresses
        if "publicipaddress" in resource_type and "basic" in sku_name:
            issue = "Using Basic SKU Public IP - Microsoft is retiring Basic SKU Public IPs"
            recommendation = "Migrate to Standard SKU Public IP immediately. Basic SKUs will be retired by September 2025."
            priority = "Critical"
            actions = [{
                "type": "upgrade",
                "description": "Upgrade Basic SKU Public IP to Standard SKU",
                "riskLevel": "Medium",
                "confirmationRequired": True,
                "estimatedTimeToComplete": "15-30 minutes"
            }]
        
        # Load Balancers
        elif "loadbalancer" in resource_type and "basic" in sku_name:
            issue = "Using Basic SKU Load Balancer - being deprecated by Microsoft"
            recommendation = "Migrate to Standard SKU Load Balancer for enhanced features and future support."
            priority = "High"
            actions = [{
                "type": "upgrade",
                "description": "Upgrade Basic SKU Load Balancer to Standard SKU",
                "riskLevel": "High",
                "confirmationRequired": True,
                "estimatedTimeToComplete": "1-2 hours"
            }]
            
        # Application Gateways
        elif "applicationgateway" in resource_type and ("v1" in sku_name or "standard" in sku_name):
            issue = "Using Application Gateway v1 which is deprecated"
            recommendation = "Migrate to Application Gateway v2 (Standard_v2 or WAF_v2) for better performance and features."
            priority = "High"
            actions = [{
                "type": "upgrade",
                "description": "Migrate Application Gateway v1 to v2",
                "riskLevel": "High",
                "confirmationRequired": True,
                "estimatedTimeToComplete": "2-4 hours"
            }]
        
        # Storage Accounts
        elif "storageaccount" in resource_type:
            if "v1" in str(resource.get("kind", "")).lower():
                issue = "Using Storage Account v1 which has limited features"
                recommendation = "Upgrade to Storage Account v2 (StorageV2) for better features and performance tiers."
                priority = "Medium"
                actions = [{
                    "type": "upgrade",
                    "description": "Upgrade Storage Account v1 to v2",
                    "riskLevel": "Low",
                    "confirmationRequired": True,
                    "estimatedTimeToComplete": "30-60 minutes"
                }]
        
        # Generic Basic tier checks
        elif "basic" in sku_name or "basic" in sku_tier:
            issue = f"Using Basic SKU/tier which may have limitations or deprecation timeline"
            recommendation = "Review if Basic tier meets requirements. Consider Standard tier for production workloads."
            priority = "Medium"
            actions = [{
                "type": "upgrade",
                "description": f"Consider upgrading from Basic to Standard tier",
                "riskLevel": "Low",
                "confirmationRequired": True,
                "estimatedTimeToComplete": "30-60 minutes"
            }]
        
        if issue:
            deprecated_resources.append({
                "resourceId": resource.get("id", ""),
                "resourceName": resource.get("name", ""),
                "resourceType": resource.get("type", ""),
                "location": resource.get("location", ""),
                "resourceGroup": resource.get("resourceGroup", ""),
                "issue": issue,
                "recommendation": recommendation,
                "priority": priority,
                "migrationComplexity": "Medium",
                "estimatedMigrationTime": "30 minutes - 4 hours",
                "actions": actions
            })
    
    return deprecated_resources