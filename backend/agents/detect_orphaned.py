import os
import httpx
from openai import OpenAI
import json
import logging

logger = logging.getLogger("tenant-optimizer")

async def detect_orphaned_resources(user_token, subscriptions):
    """
    Detects orphaned Azure resources using AI-powered analysis.
    Args:
        user_token: User's Azure access token (from frontend).
        subscriptions: List of subscription ids.
    Returns:
        List of orphaned resources with AI analysis and action recommendations.
    """
    # Use the correct Resource Graph API endpoint and version
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2021-03-01"
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }
    
    # Comprehensive query to detect various types of orphaned resources
    query = """
    Resources
    | where type in (
        "microsoft.compute/disks",
        "microsoft.network/publicipaddresses", 
        "microsoft.network/networksecuritygroups",
        "microsoft.network/networkinterfaces",
        "microsoft.network/loadbalancers",
        "microsoft.network/applicationgateways",
        "microsoft.storage/storageaccounts"
    )
    | extend orphanedReason = case(
        type == "microsoft.compute/disks" and isempty(properties.managedBy), "Disk not attached to VM",
        type == "microsoft.network/publicipaddresses" and isempty(properties.ipConfiguration), "Public IP not associated with resource",
        type == "microsoft.network/networksecuritygroups" and array_length(properties.subnets) == 0 and array_length(properties.networkInterfaces) == 0, "NSG not associated with subnet or NIC",
        type == "microsoft.network/networkinterfaces" and isempty(properties.virtualMachine), "Network interface not attached to VM",
        type == "microsoft.network/loadbalancers" and array_length(properties.backendAddressPools) == 0, "Load balancer has no backend pools",
        type == "microsoft.network/applicationgateways" and array_length(properties.backendAddressPools) == 0, "Application gateway has no backend pools",
        ""
    )
    | where isnotempty(orphanedReason)
    | project id, name, type, location, resourceGroup, properties, sku, tags, orphanedReason
    """
    
    payload = {
        "subscriptions": subscriptions,
        "query": query
    }
    
    logger.info(f"� Querying for orphaned resources in {len(subscriptions)} subscriptions")
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=payload)
            logger.info(f"📡 Resource Graph response status: {resp.status_code}")
            
            if resp.status_code != 200:
                logger.error(f"❌ Resource Graph error: {resp.text}")
                raise Exception(f"Azure Resource Graph API error: {resp.status_code} - {resp.text}")
            
            resp.raise_for_status()
            data = resp.json()
            
        # Extract the data from the Resource Graph response
        data_content = data.get("data", {})
        
        # Handle different response formats
        resources = []
        if isinstance(data_content, dict):
            # Standard format with rows and columns
            rows = data_content.get("rows", [])
            columns = data_content.get("columns", [])
            
            if columns and rows:
                column_names = [col["name"] for col in columns]
                for row in rows:
                    resource_dict = dict(zip(column_names, row))
                    resources.append(resource_dict)
        elif isinstance(data_content, list):
            resources = data_content
        else:
            if "value" in data:
                resources = data["value"]
    
    except Exception as e:
        logger.error(f"❌ Resource Graph error: {str(e)}")
        return [{
            "resourceId": "/error/query-failed",
            "resourceName": "Query Error",
            "resourceType": "Error",
            "location": "global",
            "resourceGroup": "error",
            "issue": f"Failed to query Azure Resource Graph: {str(e)}",
            "recommendation": "Check your permissions and try again",
            "estimatedMonthlyCost": "N/A",
            "priority": "High",
            "actions": []
        }]

    if not resources:
        logger.info("ℹ️ No orphaned resources found")
        return []

    logger.info(f"📊 Found {len(resources)} potentially orphaned resources")
    
    # Analyze resources with OpenAI for detailed cost and risk assessment
    return await analyze_orphaned_resources_with_ai(resources)

async def analyze_orphaned_resources_with_ai(resources):
    """
    Uses OpenAI to analyze orphaned resources and provide detailed recommendations with actions.
    """
    # Check if OpenAI API key is available
    openai_key = os.getenv("OPENAI_KEY")
    if not openai_key or not openai_key.startswith("sk-"):
        logger.warning(f"⚠️ OpenAI API key {'not found' if not openai_key else 'invalid format'}, using basic analysis")
        return generate_basic_orphaned_analysis(resources)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=openai_key)
    
    prompt = f"""
You are an Azure cloud optimization expert analyzing orphaned resources that are unnecessarily costing money.

TASK: For each orphaned resource, provide detailed analysis with specific actions the user can take.

AZURE ORPHANED RESOURCE COST KNOWLEDGE:
- Managed Disks: Premium SSD ($0.15-0.30/GB/month), Standard SSD ($0.05-0.10/GB/month), Standard HDD ($0.04-0.06/GB/month)
- Public IPs: Basic SKU ~$3.65/month, Standard SKU ~$3.65-4.38/month depending on region
- Storage Accounts: Varies by tier, typically $0.02-0.18/GB/month plus transaction costs
- Load Balancers: Basic free, Standard ~$18.25/month plus data processing
- Application Gateways: ~$125-250/month plus data processing fees
- Network Security Groups: No direct cost but management overhead
- Network Interfaces: No direct cost but may hold reserved IPs

For each resource, return a JSON object with:
- resourceId: Full Azure resource ID
- resourceName: Resource name
- resourceType: Azure resource type
- location: Azure region
- resourceGroup: Resource group name
- issue: Specific explanation of why it's orphaned and the cost impact
- recommendation: Detailed recommendation with cost savings estimate
- estimatedMonthlyCost: Specific monthly cost estimate (e.g., "$15.50/month")
- priority: "High" (>$50/month), "Medium" ($10-50/month), "Low" (<$10/month)
- actions: Array of action objects with:
  - type: "delete" for deletion actions
  - description: What the action does
  - riskLevel: "Low", "Medium", or "High" 
  - confirmationRequired: true/false
  - estimatedSavings: Monthly cost savings

RESOURCES TO ANALYZE:
{json.dumps(resources, indent=2)}

Return ONLY a JSON array of analyzed resources. Each resource must include specific cost estimates and actionable steps.
"""
    
    try:
        logger.info("🤖 Analyzing orphaned resources with OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an Azure cloud cost optimization expert with comprehensive knowledge of Azure resource costs, dependencies, and optimization strategies."},
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
                logger.info(f"✅ AI analysis completed for {len(parsed_result)} resources")
                return parsed_result
            else:
                return [parsed_result] if isinstance(parsed_result, dict) else []
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ OpenAI returned non-JSON response: {e}")
            return generate_basic_orphaned_analysis(resources)
            
    except Exception as e:
        logger.error(f"❌ OpenAI API error: {str(e)}")
        return generate_basic_orphaned_analysis(resources)

def generate_basic_orphaned_analysis(resources):
    """
    Generates basic analysis without AI when OpenAI is unavailable.
    """
    logger.info("📊 Generating basic orphaned resource analysis")
    
    findings = []
    for resource in resources:
        resource_type = resource.get("type", "").lower()
        resource_name = resource.get("name", "")
        resource_id = resource.get("id", "")
        orphaned_reason = resource.get("orphanedReason", "")
        
        # Generate basic recommendations based on resource type
        if "disk" in resource_type:
            issue = f"Orphaned managed disk - {orphaned_reason}"
            recommendation = "Review if this disk contains important data. If not needed, delete to save storage costs."
            cost_estimate = "$4-50/month"
            priority = "Medium"
            actions = [{
                "type": "delete",
                "description": "Delete orphaned managed disk",
                "riskLevel": "High",
                "confirmationRequired": True,
                "estimatedSavings": "$4-50/month"
            }]
        elif "publicipaddress" in resource_type:
            sku_name = resource.get("sku", {}).get("name", "Unknown") if isinstance(resource.get("sku"), dict) else "Unknown"
            issue = f"Orphaned public IP address ({sku_name} SKU) - {orphaned_reason}"
            recommendation = "Delete unused public IP to save costs."
            cost_estimate = "$3.65-4.38/month"
            priority = "Medium"
            actions = [{
                "type": "delete",
                "description": "Delete orphaned public IP address",
                "riskLevel": "Low",
                "confirmationRequired": True,
                "estimatedSavings": "$3.65-4.38/month"
            }]
        elif "networksecuritygroup" in resource_type:
            issue = f"Orphaned Network Security Group - {orphaned_reason}"
            recommendation = "Review and delete if not needed. No direct cost but adds management overhead."
            cost_estimate = "No direct cost"
            priority = "Low"
            actions = [{
                "type": "delete",
                "description": "Delete orphaned network security group",
                "riskLevel": "Medium",
                "confirmationRequired": True,
                "estimatedSavings": "Management overhead reduction"
            }]
        elif "networkinterface" in resource_type:
            issue = f"Orphaned Network Interface - {orphaned_reason}"
            recommendation = "Delete unused network interface. May be holding IP addresses unnecessarily."
            cost_estimate = "No direct cost"
            priority = "Low"
            actions = [{
                "type": "delete",
                "description": "Delete orphaned network interface",
                "riskLevel": "Low",
                "confirmationRequired": True,
                "estimatedSavings": "IP address availability"
            }]
        elif "loadbalancer" in resource_type:
            sku_name = resource.get("sku", {}).get("name", "Unknown") if isinstance(resource.get("sku"), dict) else "Unknown"
            issue = f"Orphaned Load Balancer ({sku_name} SKU) - {orphaned_reason}"
            recommendation = "Delete unused load balancer to save costs."
            cost_estimate = "$18.25/month" if sku_name.lower() == "standard" else "Free (Basic)"
            priority = "High" if sku_name.lower() == "standard" else "Low"
            actions = [{
                "type": "delete",
                "description": "Delete orphaned load balancer",
                "riskLevel": "Medium",
                "confirmationRequired": True,
                "estimatedSavings": cost_estimate
            }]
        elif "applicationgateway" in resource_type:
            issue = f"Orphaned Application Gateway - {orphaned_reason}"
            recommendation = "Delete unused Application Gateway. Significant cost savings opportunity."
            cost_estimate = "$125-250/month"
            priority = "High"
            actions = [{
                "type": "delete",
                "description": "Delete orphaned application gateway",
                "riskLevel": "High",
                "confirmationRequired": True,
                "estimatedSavings": "$125-250/month"
            }]
        else:
            issue = f"Orphaned resource - {orphaned_reason}"
            recommendation = "Review resource usage and delete if confirmed unused."
            cost_estimate = "Varies"
            priority = "Medium"
            actions = [{
                "type": "delete",
                "description": "Delete orphaned resource",
                "riskLevel": "Medium",
                "confirmationRequired": True,
                "estimatedSavings": "Varies"
            }]
        
        findings.append({
            "resourceId": resource_id,
            "resourceName": resource_name,
            "resourceType": resource.get("type", ""),
            "location": resource.get("location", ""),
            "resourceGroup": resource.get("resourceGroup", ""),
            "issue": issue,
            "recommendation": recommendation,
            "estimatedMonthlyCost": cost_estimate,
            "priority": priority,
            "actions": actions
        })
    
    return findings