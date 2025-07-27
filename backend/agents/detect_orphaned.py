from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
import openai
import os
import json

def detect_deprecated_resources(token, subscriptions):
    """
    Detects deprecated or outdated resources in provided Azure subscriptions.
    Args:
        token: User's access token (not directly used here, but available for future expansion).
        subscriptions: List of subscription id strings.
    Returns:
        List of deprecated resources with recommendations.
    """
    cred = DefaultAzureCredential()
    client = ResourceGraphClient(cred)

    query = """
    resources
    | project id, name, type, kind, sku, location, properties
    """
    request = QueryRequest(
        query=query,
        subscriptions=subscriptions
    )
    result = client.resources(request)
    resources = [dict(row) for row in result.data[:50]]  # Limit for prompt size

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
        output_text = response["choices"][0]["message"]["content"]
        deprecated = json.loads(output_text)
    except Exception as e:
        deprecated = {"error": "Failed to parse response", "details": str(e), "raw": output_text}

    return deprecated