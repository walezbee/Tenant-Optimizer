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
    
    # Comprehensive query for resources that might be deprecated/retired
    query = """
    Resources
    | where type in~ (
        'microsoft.network/publicipaddresses',
        'microsoft.compute/virtualmachines',
        'microsoft.network/loadbalancers',
        'microsoft.network/applicationgateways', 
        'microsoft.storage/storageaccounts',
        'microsoft.sql/servers',
        'microsoft.sql/servers/databases',
        'microsoft.compute/availabilitysets',
        'microsoft.network/networksecuritygroups',
        'microsoft.compute/virtualmachinescalesets',
        'microsoft.containerservice/managedclusters',
        'microsoft.network/virtualnetworks',
        'microsoft.keyvault/vaults',
        'microsoft.insights/components',
        'microsoft.web/sites',
        'microsoft.cache/redis',
        'microsoft.servicebus/namespaces',
        'microsoft.eventhub/namespaces'
    )
    | extend skuName = sku.name, skuTier = sku.tier
    | extend apiVersion = properties.apiVersion
    | extend vmSize = properties.hardwareProfile.vmSize
    | extend osVersion = properties.storageProfile.imageReference.version
    | project id, name, type, kind, location, resourceGroup, skuName, skuTier, apiVersion, vmSize, osVersion, sku, tags, properties
    | limit 150
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
        logger.warning(f"⚠️ OpenAI API key {'not found' if not openai_key else 'invalid format'}, returning basic analysis")
        # Return comprehensive basic analysis without AI
        deprecated_resources = []
        for resource in resources:
            resource_type = resource.get("type", "").lower()
            sku_name = resource.get("skuName", "").lower() if resource.get("skuName") else ""
            sku_tier = resource.get("skuTier", "").lower() if resource.get("skuTier") else ""
            vm_size = resource.get("vmSize", "").lower() if resource.get("vmSize") else ""
            
            # Enhanced deprecation detection based on Microsoft documentation
            issue = None
            recommendation = None
            priority = "Medium"
            
            # Public IP Addresses
            if "publicipaddress" in resource_type and "basic" in sku_name:
                issue = "Using Basic SKU Public IP - Microsoft is retiring Basic SKU Public IPs"
                recommendation = "Migrate to Standard SKU Public IP immediately. Basic SKUs will be retired by September 2025."
                priority = "Critical"
            
            # Virtual Machines
            elif "virtualmachine" in resource_type:
                if vm_size and ("a0" in vm_size or "a1" in vm_size or "a2" in vm_size):
                    issue = "Using deprecated A-series VM size"
                    recommendation = "Migrate to newer VM series (B, D, or F series) for better performance and support."
                    priority = "High"
                elif "d1" in vm_size or "d2" in vm_size:
                    issue = "Using D-series v1 which is deprecated"
                    recommendation = "Upgrade to D-series v2 or newer (Dv3, Dv4, Dv5) for better performance."
                    priority = "High"
            
            # Load Balancers
            elif "loadbalancer" in resource_type and "basic" in sku_name:
                issue = "Using Basic SKU Load Balancer - being deprecated by Microsoft"
                recommendation = "Migrate to Standard SKU Load Balancer for enhanced features and future support."
                priority = "High"
                
            # Application Gateways
            elif "applicationgateway" in resource_type and ("v1" in sku_name or "standard" in sku_name):
                issue = "Using Application Gateway v1 which is deprecated"
                recommendation = "Migrate to Application Gateway v2 (Standard_v2 or WAF_v2) for better performance and features."
                priority = "High"
            
            # Storage Accounts
            elif "storageaccount" in resource_type:
                if "standard_lrs" in sku_name and "v1" in str(resource.get("kind", "")).lower():
                    issue = "Using Storage Account v1 which has limited features"
                    recommendation = "Upgrade to Storage Account v2 (StorageV2) for better features and performance tiers."
                    priority = "Medium"
            
            # AKS Clusters
            elif "managedcluster" in resource_type:
                # Note: Would need to check Kubernetes version from properties
                issue = "AKS cluster may be using deprecated Kubernetes version"
                recommendation = "Check and upgrade to latest supported Kubernetes version. Versions older than 1.24 are deprecated."
                priority = "High"
                
            # SQL Databases
            elif "databases" in resource_type and "basic" in sku_tier:
                issue = "Using Basic tier SQL Database with limited features"
                recommendation = "Consider upgrading to Standard or Premium tier, or migrate to vCore model for better performance."
                priority = "Medium"
                
            # Generic checks
            elif "basic" in sku_name or "basic" in sku_tier:
                issue = f"Using Basic SKU/tier which may have limitations or deprecation timeline"
                recommendation = "Review if Basic tier meets requirements. Consider Standard tier for production workloads."
                priority = "Medium"
            elif "v1" in sku_name or "classic" in resource_type:
                issue = "Using legacy/v1 resource version"
                recommendation = "Migrate to newer resource version for better security, features, and support."
                priority = "High"
            
            if issue:
                deprecated_resources.append({
                    "resourceId": resource.get("id", ""),
                    "resourceName": resource.get("name", ""),
                    "resourceType": resource.get("type", ""),
                    "location": resource.get("location", ""),
                    "resourceGroup": resource.get("resourceGroup", ""),
                    "issue": f"{issue} - Basic analysis without AI",
                    "recommendation": f"{recommendation} Note: Advanced AI analysis unavailable - verify current Microsoft documentation.",
                    "priority": priority,
                    "migrationComplexity": "Medium"
                })
        
        return deprecated_resources if deprecated_resources else []

    prompt = f"""
You are an Azure cloud optimization expert with comprehensive knowledge of Microsoft's deprecation timeline and service retirement announcements.

TASK: Analyze the following Azure resources and identify those using deprecated/retired services, SKUs, or configurations.

MICROSOFT AZURE DEPRECATION KNOWLEDGE (as of 2025):

PUBLIC IP ADDRESSES:
- Basic SKU Public IPs: Deprecated/retiring - migrate to Standard SKU
- IPv4 Public IPs: Still supported but consider IPv6 for future-proofing
- Classic deployment model IPs: Fully retired

VIRTUAL MACHINES:
- Classic VMs: Fully retired (migrated to ARM)
- A-series (A0-A7): Deprecated - migrate to newer series
- D-series v1: Deprecated - migrate to v2 or newer
- Old OS versions: Windows Server 2008/2012 reaching end of support
- VM sizes with <2GB RAM: Often deprecated

LOAD BALANCERS:
- Basic SKU Load Balancers: Being deprecated - migrate to Standard SKU
- Classic Load Balancers: Fully retired

STORAGE ACCOUNTS:
- Classic Storage Accounts: Fully retired
- Storage Account v1: Deprecated - upgrade to v2
- Cool/Archive access tiers: Still supported but consider newer tiers

SQL SERVICES:
- SQL Database compatibility levels <140: Deprecated
- Basic/Standard tiers in some regions: Being phased out
- DTU-based pricing: Deprecated in favor of vCore

APPLICATION GATEWAYS:
- v1 SKU: Deprecated - migrate to v2
- Classic deployment model: Fully retired

CONTAINER SERVICES:
- AKS versions <1.24: Deprecated
- Container Instances without managed identity: Security deprecation

NETWORKING:
- Classic VNets: Fully retired
- NSG rules without proper segmentation: Security deprecation
- ExpressRoute circuits <1Gbps: Some deprecated

KEY VAULTS:
- Vault access policies: Being deprecated in favor of RBAC
- Older API versions: Some deprecated

For each deprecated/retired resource found, return a JSON object with:
- resourceId: Full Azure resource ID
- resourceName: Resource name  
- resourceType: Azure resource type
- location: Azure region
- resourceGroup: Resource group name
- issue: Specific deprecation issue with timeline if known
- recommendation: Detailed migration/upgrade path
- priority: Critical/High/Medium based on retirement timeline
- migrationComplexity: Low/Medium/High
- estimatedMigrationTime: Rough time estimate

RESOURCES TO ANALYZE:
{json.dumps(resources, indent=2)}

Return ONLY a JSON array of resources using deprecated/retired services. If no deprecated resources found, return empty array [].
"""

    # Initialize OpenAI client
    client = OpenAI(api_key=openai_key)
    
    try:
        logger.info("🤖 Analyzing resources for deprecation with OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4",  # Use gpt-4 instead of gpt-4o if not available
            messages=[
                {"role": "system", "content": "You are an Azure cloud architect and optimization expert with deep knowledge of Microsoft's service deprecation timeline, retirement announcements, and migration best practices. You stay current with Microsoft documentation and deprecation notices."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3000,
            temperature=0.0
        )
        
        result = response.choices[0].message.content
        # Try to parse as JSON, fallback to basic analysis
        try:
            parsed_result = json.loads(result)
            if isinstance(parsed_result, list):
                return parsed_result
            else:
                return [parsed_result] if isinstance(parsed_result, dict) else []
        except json.JSONDecodeError:
            logger.warning("⚠️ OpenAI returned non-JSON response, using basic analysis")
            return [
                {
                    "resourceId": resource.get("id", ""),
                    "resourceName": resource.get("name", ""),
                    "resourceType": resource.get("type", ""),
                    "location": resource.get("location", ""),
                    "resourceGroup": resource.get("resourceGroup", ""),
                    "issue": "AI analysis unavailable - Manual review recommended",
                    "recommendation": "Review resource configuration for optimization opportunities"
                }
                for resource in resources[:10]  # Limit to prevent overwhelming
            ]
            
    except Exception as e:
        logger.error(f"❌ OpenAI API error: {str(e)}")
        # Return fallback data
        return [
            {
                "resourceId": resource.get("id", ""),
                "resourceName": resource.get("name", ""),
                "resourceType": resource.get("type", ""),
                "location": resource.get("location", ""),
                "resourceGroup": resource.get("resourceGroup", ""),
                "issue": f"AI analysis failed: {str(e)[:100]}...",
                "recommendation": "Manual review required for optimization opportunities"
            }
            for resource in resources[:10]  # Limit to prevent overwhelming
        ]