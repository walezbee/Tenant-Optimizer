import os
import httpx
from openai import OpenAI
import json

async def detect_deprecated_resources(user_token, subscriptions):
    """
    Detects deprecated or outdated resources using the user's token and Resource Graph REST API.
    Args:
        user_token: User's Azure access token.
        subscriptions: List of subscription id strings.
    Returns:
        List of deprecated resources with recommendations.
    """
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2023-07-01"
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }
    query = """
    resources
    | project id, name, type, kind, sku, location, properties
    """
    payload = {
        "subscriptions": subscriptions,
        "query": query
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    
    resources = [dict(row) for row in data.get("data", [])][:50]  # Limit to 50 for API limits

    prompt = (
        "You are an Azure cloud optimization expert. "
        "Given the following list of Azure resources, identify those that are deprecated or outdated. "
        "For each deprecated/outdated resource, explain why and recommend the appropriate upgrade or migration path. "
        "Return your response as a JSON array: [{id, name, type, reason, recommendation}].\n\n"
        f"Resources:\n{json.dumps(resources, indent=2)}"
    )

    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_KEY"))
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # Use gpt-4 instead of gpt-4o if not available
            messages=[
                {"role": "system", "content": "You are a helpful Azure cloud optimization expert."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.0
        )
        
        result = response.choices[0].message.content
        # Try to parse as JSON, fallback to string
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result
            
    except Exception as e:
        return {"error": f"OpenAI API error: {str(e)}", "resources": resources}