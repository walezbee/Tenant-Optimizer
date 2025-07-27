from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
from openai import OpenAI
import os

def detect_orphaned_resources(token, subscriptions):
    """
    Scans for orphaned managed disks in all provided subscriptions.
    Args:
        token: User's access token (not directly used here, but available for future expansion).
        subscriptions: List of subscription ids (strings) to scan.
    Returns:
        OpenAI's classification of orphaned disks, as string or dict.
    """
    cred = DefaultAzureCredential()
    client = ResourceGraphClient(cred)

    query = """
    resources
    | where type =~ 'microsoft.compute/disks'
    | where managedBy == ''
    | project id, name, type, location, managedBy, sku, tags
    """

    request = QueryRequest(
        query=query,
        subscriptions=subscriptions
    )
    result = client.resources(request)
    disks = [dict(row) for row in result.data]

    openai_client = OpenAI(api_key=os.getenv('OPENAI_KEY'))
    prompt = (
        "Given these Azure managed disks (JSON list), identify which are truly orphaned (unused) and explain why. "
        "Return a JSON array of orphaned disks, each with id, name, and reason:\n"
        f"{disks}"
    )
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}]
    )
    # Try to parse JSON output, else return raw
    try:
        import json
        return json.loads(response.choices[0].message.content)
    except Exception:
        return response.choices[0].message.content