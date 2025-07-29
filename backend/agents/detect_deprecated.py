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
    
    # Query for various resource types that commonly have deprecated versions
    query = """
    Resources
    | where type in~ ('microsoft.compute/virtualmachines', 'microsoft.web/sites', 'microsoft.sql/servers/databases', 'microsoft.storage/storageaccounts', 'microsoft.containerservice/managedclusters')
    | project id, name, type, kind, sku, location, resourceGroup, properties, tags
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

    # Check if OpenAI API key is available
    openai_key = os.getenv("OPENAI_KEY")
    if not openai_key:
        logger.warning("⚠️ OpenAI API key not found, returning basic analysis")
        # Return basic structured data without AI analysis
        deprecated_resources = []
        for resource in resources:
            resource_type = resource.get("type", "").lower()
            sku = str(resource.get("sku", {}))
            
            # Basic heuristics for common deprecated patterns
            issue = None
            recommendation = None
            
            if "basic" in sku.lower():
                issue = "Using Basic SKU which may have limited features"
                recommendation = "Consider upgrading to Standard SKU for better performance and features"
            elif "v1" in sku.lower() or "classic" in resource_type:
                issue = "Using legacy/classic resource version"
                recommendation = "Migrate to newer resource version for better security and features"
            elif "microsoft.sql" in resource_type and "databases" in resource_type:
                issue = "SQL Database - check compatibility level"
                recommendation = "Ensure database compatibility level is current"
            
            if issue:
                deprecated_resources.append({
                    "resourceId": resource.get("id", ""),
                    "resourceName": resource.get("name", ""),
                    "resourceType": resource.get("type", ""),
                    "location": resource.get("location", ""),
                    "resourceGroup": resource.get("resourceGroup", ""),
                    "issue": issue,
                    "recommendation": recommendation
                })
        
        return deprecated_resources if deprecated_resources else []

    prompt = (
        "You are an Azure cloud optimization expert. "
        "Given the following list of Azure resources, identify those that are deprecated or outdated. "
        "For each deprecated/outdated resource, return a JSON object with: resourceId, resourceName, resourceType, location, resourceGroup, issue, recommendation. "
        "Return your response as a JSON array.\n\n"
        f"Resources:\n{json.dumps(resources, indent=2)}"
    )

    # Initialize OpenAI client
    client = OpenAI(api_key=openai_key)
    
    try:
        logger.info("🤖 Analyzing resources for deprecation with OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4",  # Use gpt-4 instead of gpt-4o if not available
            messages=[
                {"role": "system", "content": "You are a helpful Azure cloud optimization expert. Analyze resources and return structured JSON responses."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
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