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
    
    # Test query - just get all disks first to ensure basic functionality
    query = """
    Resources
    | where type =~ 'microsoft.compute/disks'
    | project id, name, type, location, resourceGroup, sku, tags, properties
    | limit 10
    """
    
    payload = {
        "subscriptions": subscriptions,
        "query": query
    }
    
    logger.info(f"🔍 Querying Resource Graph for disks in {len(subscriptions)} subscriptions")
    logger.info(f"📡 Resource Graph URL: {url}")
    logger.info(f"🔎 Subscriptions: {subscriptions}")
    logger.info(f"📝 Query: {query}")
    
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
        logger.info("✅ No resources found in Resource Graph response")
        # Return a test result to confirm the function is working
        return [{
            "resourceId": "test-no-resources-found",
            "resourceName": "No Resources Found", 
            "resourceType": "Test",
            "location": "N/A",
            "resourceGroup": "N/A",
            "issue": "No disks found in the selected subscriptions",
            "recommendation": "This means either there are no managed disks, or there may be an issue with the query or permissions.",
            "estimatedMonthlyCost": "$0",
            "priority": "Low"
        }]

    # For debugging - return simplified results for all found disks
    logger.info(f"📊 Processing {len(resources)} resources for analysis")
    
    # Return basic information about found disks
    orphaned_findings = []
    for resource in resources:
        resource_name = resource.get("name", "")
        resource_id = resource.get("id", "")
        managed_by = resource.get("properties", {}).get("managedBy") if isinstance(resource.get("properties"), dict) else None
        
        if not managed_by:  # This is an orphaned disk
            issue = "Orphaned managed disk - not attached to any virtual machine"
            recommendation = "Review if this disk contains important data. If not needed, delete to save storage costs."
            cost_estimate = "~$4-50/month"
            priority = "Medium"
        else:
            issue = "Managed disk is attached to a VM"
            recommendation = "This disk is in use and should not be deleted."
            cost_estimate = "Active resource"
            priority = "Low"
        
        orphaned_findings.append({
            "resourceId": resource_id,
            "resourceName": resource_name,
            "resourceType": resource.get("type", ""),
            "location": resource.get("location", ""),
            "resourceGroup": resource.get("resourceGroup", ""),
            "issue": f"{issue} - Debug mode",
            "recommendation": f"{recommendation} [managedBy: {managed_by}]",
            "estimatedMonthlyCost": cost_estimate,
            "priority": priority
        })
    
    logger.info(f"✅ Returning {len(orphaned_findings)} disk analysis results")
    return orphaned_findings