import os
import httpx
import openai
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
    resources = [dict(row) for row in data.get("data", [])][:50]

    prompt = (
        "You are an Azure cloud optimization expert. "
        "Given the following list of Azure resources, identify those that are deprecated or outdated. "
        "For each deprecated/outdated resource, explain why and recommend the appropriate upgrade or migration path. "
        "Return your response as a JSON array: [{id, name, type, reason, recommendation}].\n\n"
        f"Resources:\n{json.dumps(resources, indent=2)}"
    )

    openai.api_key = os.getenv("OPENAI_KEY")
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful cloud expert."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1500,
        temperature=0.0
    )
    try:
        output_text = response.choices[0].message.content
        deprecated = json.loads(output_text)
    except Exception as e:
        deprecated = {"error": "Failed to parse response", "details": str(e), "raw": output_text}

    return deprecated