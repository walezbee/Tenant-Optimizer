import os
import httpx
from openai import OpenAI
import json
import logging

logger = logging.getLogger("tenant-optimizer")

async def detect_orphaned_resources(user_token, subscriptions):
    """
    Scans for orphaned managed disks using the user's token and Resource Graph REST API.
    Args:
        user_token: User's Azure access token (from frontend).
        subscriptions: List of subscription ids.
    Returns:
        OpenAI's classification of orphaned disks, as string or dict.
    """
    # Use the correct Resource Graph API endpoint and version
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }
    
    # Comprehensive query for ALL types of orphaned resources
    query = """
    // Orphaned Managed Disks (not attached to any VM)
    Resources
    | where type =~ 'microsoft.compute/disks'
    | where isnull(managedBy) or managedBy == ''
    | extend ResourceType = 'Orphaned Disk', Cost = sku.tier
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties
    
    union
    
    // Orphaned Public IP Addresses (not associated with any resource)
    (Resources
    | where type =~ 'microsoft.network/publicipaddresses'
    | where isnull(properties.ipConfiguration) or properties.ipConfiguration == ''
    | extend ResourceType = 'Orphaned Public IP', Cost = sku.name
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties)
    
    union
    
    // Orphaned Network Interfaces (not attached to any VM)
    (Resources
    | where type =~ 'microsoft.network/networkinterfaces'
    | where isnull(properties.virtualMachine) or properties.virtualMachine == ''
    | extend ResourceType = 'Orphaned Network Interface', Cost = 'Standard'
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties)
    
    union
    
    // Orphaned Network Security Groups (not associated with any subnet or NIC)
    (Resources
    | where type =~ 'microsoft.network/networksecuritygroups'
    | where array_length(properties.subnets) == 0 and array_length(properties.networkInterfaces) == 0
    | extend ResourceType = 'Orphaned Network Security Group', Cost = 'Free'
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties)
    
    union
    
    // Orphaned Load Balancers (no backend pools or rules)
    (Resources
    | where type =~ 'microsoft.network/loadbalancers'
    | where array_length(properties.backendAddressPools) == 0 or array_length(properties.loadBalancingRules) == 0
    | extend ResourceType = 'Orphaned Load Balancer', Cost = sku.name
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties)
    
    union
    
    // Orphaned Application Gateways (no backend pools)
    (Resources
    | where type =~ 'microsoft.network/applicationgateways'
    | where array_length(properties.backendAddressPools) == 0
    | extend ResourceType = 'Orphaned Application Gateway', Cost = sku.name
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties)
    
    union
    
    // Orphaned Storage Accounts (empty or unused)
    (Resources
    | where type =~ 'microsoft.storage/storageaccounts'
    | where tags['usage'] == 'unused' or tags['status'] == 'empty'
    | extend ResourceType = 'Potentially Orphaned Storage Account', Cost = sku.name
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties)
    
    | limit 200
    """
    
    // Orphaned Public IP Addresses (not associated with any resource)
    Resources
    | where type =~ 'microsoft.network/publicipaddresses'
    | extend ipConfig = properties.ipConfiguration.id
    | where isnull(ipConfig) or ipConfig == ''
    | extend ResourceType = 'Orphaned Public IP', Cost = sku.name
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties
    
    union
    
    // Orphaned Network Security Groups (not associated with any subnet or NIC)
    Resources
    | where type =~ 'microsoft.network/networksecuritygroups'
    | extend subnets = properties.subnets
    | extend networkInterfaces = properties.networkInterfaces
    | where array_length(subnets) == 0 and array_length(networkInterfaces) == 0
    | extend ResourceType = 'Orphaned Network Security Group', Cost = 'Standard'
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties
    
    union
    
    // Orphaned Network Interfaces (not attached to any VM)
    Resources
    | where type =~ 'microsoft.network/networkinterfaces'
    | extend virtualMachine = properties.virtualMachine.id
    | where isnull(virtualMachine) or virtualMachine == ''
    | extend ResourceType = 'Orphaned Network Interface', Cost = 'Standard'
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties
    
    union
    
    // Orphaned Storage Accounts (unused for extended periods - identify by last access)
    Resources
    | where type =~ 'microsoft.storage/storageaccounts'
    | extend lastAccess = properties.lastGeoFailoverTime
    | extend ResourceType = 'Potentially Orphaned Storage Account', Cost = sku.name
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties
    
    union
    
    // Orphaned Load Balancers (no backend pools or rules configured)
    Resources
    | where type =~ 'microsoft.network/loadbalancers'
    | extend backendPools = properties.backendAddressPools
    | extend rules = properties.loadBalancingRules
    | where array_length(backendPools) == 0 or array_length(rules) == 0
    | extend ResourceType = 'Orphaned Load Balancer', Cost = sku.name
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties
    
    union
    
    // Orphaned Application Gateways (no backend pools)
    Resources
    | where type =~ 'microsoft.network/applicationgateways'
    | extend backendPools = properties.backendAddressPools
    | where array_length(backendPools) == 0
    | extend ResourceType = 'Orphaned Application Gateway', Cost = sku.name
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties
    
    union
    
    // Unattached Availability Sets (no VMs assigned)
    Resources
    | where type =~ 'microsoft.compute/availabilitysets'
    | extend virtualMachines = properties.virtualMachines
    | where array_length(virtualMachines) == 0
    | extend ResourceType = 'Empty Availability Set', Cost = 'Free'
    | project id, name, type, location, resourceGroup, ResourceType, Cost, sku, tags, properties
    
    | limit 200
    """
    
    payload = {
        "subscriptions": subscriptions,
        "query": query
    }
    
    logger.info(f"🔍 Querying Resource Graph for orphaned resources in {len(subscriptions)} subscriptions")
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
        logger.info("✅ No orphaned resources found")
        return []

    # Check if OpenAI API key is available and valid
    openai_key = os.getenv("OPENAI_KEY")
    if not openai_key or not openai_key.startswith("sk-"):
        logger.warning(f"⚠️ OpenAI API key {'not found' if not openai_key else 'invalid format'}, returning basic analysis")
        # Return structured data without AI analysis
        orphaned_findings = []
        for resource in resources:
            resource_type = resource.get("type", "").lower()
            resource_name = resource.get("name", "")
            resource_id = resource.get("id", "")
            
            # Determine the specific issue and recommendation based on resource type
            if "disk" in resource_type:
                issue = "Orphaned managed disk - not attached to any virtual machine"
                recommendation = "Review if this disk contains important data. If not needed, delete to save storage costs (~$4-50/month depending on size and type)."
                cost_estimate = "~$4-50/month"
            elif "publicipaddress" in resource_type:
                sku_name = resource.get("sku", {}).get("name", "")
                issue = f"Orphaned public IP address ({sku_name} SKU) - not associated with any resource"
                recommendation = "Delete unused public IP to save costs. Basic SKU: ~$3.65/month, Standard SKU varies by region."
                cost_estimate = "~$3-15/month"
            elif "networksecuritygroup" in resource_type:
                issue = "Orphaned Network Security Group - not associated with any subnet or network interface"
                recommendation = "Review and delete if not needed. NSGs don't incur direct costs but add management overhead."
                cost_estimate = "No direct cost"
            elif "networkinterface" in resource_type:
                issue = "Orphaned Network Interface - not attached to any virtual machine"
                recommendation = "Delete unused network interface. No direct cost but may hold IP addresses unnecessarily."
                cost_estimate = "No direct cost"
            elif "loadbalancer" in resource_type:
                sku_name = resource.get("sku", {}).get("name", "")
                issue = f"Orphaned Load Balancer ({sku_name} SKU) - no backend pools or rules configured"
                recommendation = "Delete unused load balancer. Standard SKU incurs hourly charges (~$18/month)."
                cost_estimate = "~$18/month for Standard"
            elif "applicationgateway" in resource_type:
                issue = "Orphaned Application Gateway - no backend address pools configured"
                recommendation = "Delete unused Application Gateway. Significant cost (~$125-250/month) plus data processing fees."
                cost_estimate = "~$125-250/month"
            elif "storageaccount" in resource_type:
                issue = "Potentially orphaned Storage Account - may be unused"
                recommendation = "Review storage account usage. Check last access time and delete if confirmed unused. Costs vary by data stored and tier."
                cost_estimate = "Varies by usage"
            else:
                issue = "Potentially orphaned resource - not in use by other resources"
                recommendation = "Review resource usage and delete if confirmed unused to save costs."
                cost_estimate = "Varies"
            
            orphaned_findings.append({
                "resourceId": resource_id,
                "resourceName": resource_name,
                "resourceType": resource.get("type", ""),
                "location": resource.get("location", ""),
                "resourceGroup": resource.get("resourceGroup", ""),
                "issue": f"{issue} - Basic analysis without AI",
                "recommendation": f"{recommendation} Note: Advanced AI analysis unavailable - verify before deletion.",
                "estimatedMonthlyCost": cost_estimate,
                "priority": "Medium"
            })
        
        return orphaned_findings
    
    # Initialize OpenAI client
    client = OpenAI(api_key=openai_key)
    
    prompt = f"""
You are an Azure cloud optimization expert with deep knowledge of Azure resource management and cost optimization.

TASK: Analyze the following Azure resources and identify which are truly orphaned/unused and costing money unnecessarily.

AZURE ORPHANED RESOURCE EXPERTISE:
- Managed Disks: Orphaned if managedBy is null/empty (not attached to VMs)
- Public IPs: Orphaned if ipConfiguration is null/empty (not associated with resources)
- Network Security Groups: Orphaned if no subnets or network interfaces associated
- Network Interfaces: Orphaned if virtualMachine is null/empty (not attached to VMs)
- Storage Accounts: May be orphaned if unused for extended periods
- Load Balancers: Orphaned if no backend pools or load balancing rules
- Application Gateways: Orphaned if no backend address pools configured
- Availability Sets: Orphaned if no virtual machines assigned

COST IMPACT KNOWLEDGE:
- Managed Disks: Charged for storage capacity (Premium SSD > Standard SSD > Standard HDD)
- Public IPs: Basic SKU ~$3.65/month, Standard SKU varies by region
- Storage Accounts: Charged for storage used, transactions, and redundancy level
- Load Balancers: Basic is free, Standard has hourly charges
- Application Gateways: Significant hourly charges + data processing fees

For each truly orphaned resource, return a JSON object with:
- resourceId: Full Azure resource ID
- resourceName: Resource name
- resourceType: Azure resource type
- location: Azure region
- resourceGroup: Resource group name
- issue: Specific reason why it's orphaned and costing money
- recommendation: Detailed action to take (delete, modify, or investigate)
- estimatedMonthlyCost: Rough monthly cost estimate if available
- priority: High/Medium/Low based on cost impact

RESOURCES TO ANALYZE:
{json.dumps(resources, indent=2)}

Return ONLY a JSON array of truly orphaned resources that are costing money unnecessarily. If no resources are orphaned, return an empty array [].
"""
    
    try:
        logger.info("🤖 Analyzing orphaned resources with OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4",  # Use gpt-4 instead of gpt-4o if not available
            messages=[
                {"role": "system", "content": "You are an Azure cloud cost optimization expert with comprehensive knowledge of Azure resource relationships, dependencies, and cost structures. You specialize in identifying truly orphaned resources that are unnecessarily costing money."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3000,
            temperature=0.0
        )
        
        result = response.choices[0].message.content
        # Try to parse as JSON, fallback to structured data
        try:
            parsed_result = json.loads(result)
            if isinstance(parsed_result, list):
                return parsed_result
            else:
                return [parsed_result] if isinstance(parsed_result, dict) else []
        except json.JSONDecodeError:
            logger.warning("⚠️ OpenAI returned non-JSON response, using fallback data")
            return [
                {
                    "resourceId": resource.get("id", ""),
                    "resourceName": resource.get("name", ""),
                    "resourceType": resource.get("type", ""),
                    "location": resource.get("location", ""),
                    "resourceGroup": resource.get("resourceGroup", ""),
                    "issue": "Potentially orphaned resource (AI analysis failed)",
                    "recommendation": "Review if this resource is still needed. If not, consider deleting to save costs. Note: AI analysis failed - basic recommendation provided."
                }
                for resource in resources
            ]
            
    except Exception as e:
        logger.error(f"❌ OpenAI API error: {str(e)}")
        # Return fallback data when OpenAI fails
        return [
            {
                "resourceId": resource.get("id", ""),
                "resourceName": resource.get("name", ""),
                "resourceType": resource.get("type", ""),
                "location": resource.get("location", ""),
                "resourceGroup": resource.get("resourceGroup", ""),
                "issue": "Potentially orphaned resource (AI analysis failed)",
                "recommendation": f"Review if this resource is still needed. If not, consider deleting to save costs. Note: AI analysis failed due to: {str(e)}"
            }
            for resource in resources
        ]