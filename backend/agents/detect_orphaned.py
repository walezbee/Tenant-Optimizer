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
    
    # Query for orphaned managed disks
    query = """
    Resources
    | where type =~ 'microsoft.compute/disks'
    | where isnull(managedBy) or managedBy == ''
    | project id, name, type, location, resourceGroup, managedBy, sku, tags, properties
    | limit 100
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
            disks = []
            if columns and rows:
                column_names = [col["name"] for col in columns]
                for row in rows:
                    disk_dict = dict(zip(column_names, row))
                    disks.append(disk_dict)
        elif isinstance(data_content, list):
            # Direct list format (some API versions return this)
            disks = data_content
            logger.info(f"📊 Found {len(disks)} resources in list format")
        else:
            # Fallback - check if data is directly in the response
            if "value" in data:
                disks = data["value"]
                logger.info(f"📊 Found {len(disks)} resources in value field")
            else:
                logger.warning("⚠️ Unexpected Resource Graph response format")
                disks = []
    
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Resource Graph HTTP error: {e.response.status_code} - {e.response.text}")
        raise Exception(f"Azure Resource Graph API error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"❌ Resource Graph error: {str(e)}")
        raise Exception(f"Failed to query Azure Resource Graph: {str(e)}")
    
    if not disks:
        logger.info("✅ No orphaned resources found")
        return []

    # Check if OpenAI API key is available and valid
    openai_key = os.getenv("OPENAI_KEY")
    if not openai_key or not openai_key.startswith("sk-"):
        logger.warning(f"⚠️ OpenAI API key {'not found' if not openai_key else 'invalid format'}, returning basic analysis")
        # Return structured data without AI analysis
        return [
            {
                "resourceId": disk.get("id", ""),
                "resourceName": disk.get("name", ""),
                "resourceType": disk.get("type", ""),
                "location": disk.get("location", ""),
                "resourceGroup": disk.get("resourceGroup", ""),
                "issue": "Potentially orphaned disk (not attached to any VM) - Basic analysis without AI",
                "recommendation": "Review if this disk is still needed. If not, consider deleting to save costs. Note: Advanced AI analysis unavailable - check OpenAI API key configuration."
            }
            for disk in disks
        ]
    
    # Initialize OpenAI client
    client = OpenAI(api_key=openai_key)
    
    prompt = (
        "Given these Azure managed disks (JSON list), identify which are truly orphaned (unused) and explain why. "
        "For each orphaned disk, return a JSON object with: resourceId, resourceName, resourceType, location, resourceGroup, issue, recommendation. "
        "Return as a JSON array:\n"
        f"{json.dumps(disks, indent=2)}"
    )
    
    try:
        logger.info("🤖 Analyzing orphaned resources with OpenAI...")
        response = client.chat.completions.create(
            model="gpt-4",  # Use gpt-4 instead of gpt-4o if not available
            messages=[
                {"role": "system", "content": "You are an Azure cloud optimization expert. Analyze resources and return structured JSON responses."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
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
                    "resourceId": disk.get("id", ""),
                    "resourceName": disk.get("name", ""),
                    "resourceType": disk.get("type", ""),
                    "location": disk.get("location", ""),
                    "resourceGroup": disk.get("resourceGroup", ""),
                    "issue": "Potentially orphaned disk (AI analysis failed)",
                    "recommendation": "Review if this disk is still needed. If not, consider deleting to save costs. Note: AI analysis failed - basic recommendation provided."
                }
                for disk in disks
            ]
            
    except Exception as e:
        logger.error(f"❌ OpenAI API error: {str(e)}")
        # Return fallback data when OpenAI fails
        return [
            {
                "resourceId": disk.get("id", ""),
                "resourceName": disk.get("name", ""),
                "resourceType": disk.get("type", ""),
                "location": disk.get("location", ""),
                "resourceGroup": disk.get("resourceGroup", ""),
                "issue": "Potentially orphaned disk (AI analysis failed)",
                "recommendation": f"Review if this disk is still needed. If not, consider deleting to save costs. Note: AI analysis failed due to: {str(e)}"
            }
            for disk in disks
        ]