import os
import httpx
import openai
import json

async def detect_orphaned_resources(user_token, subscriptions):
    """
    Scans for orphaned managed disks using the user's token and Resource Graph REST API.
    Args:
        user_token: User's Azure access token (from frontend).
        subscriptions: List of subscription ids.
    Returns:
        OpenAI's classification of orphaned disks, as string or dict.
    """
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources?api-version=2023-07-01"
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }
    query = """
    resources
    | where type =~ 'microsoft.compute/disks'
    | where managedBy == ''
    | project id, name, type, location, managedBy, sku, tags
    """
    payload = {
        "subscriptions": subscriptions,
        "query": query
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    disks = [dict(row) for row in data.get("data", [])]

    openai.api_key = os.getenv("OPENAI_KEY")
    prompt = (
        "Given these Azure managed disks (JSON list), identify which are truly orphaned (unused) and explain why. "
        "Return a JSON array of orphaned disks, each with id, name, and reason:\n"
        f"{disks}"
    )
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}]
    )
    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return response.choices[0].message.content