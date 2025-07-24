from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
import openai
import os
import json

def detect_deprecated_resources(token):
    """
    Detects deprecated or outdated resources in a given Azure subscription.
    Returns a list of deprecated resources with recommendations.
    """
    # Collect resources from Azure Resource Graph
    cred = DefaultAzureCredential()
    client = ResourceGraphClient(cred)

    # Query for all resources - you may want to limit fields for efficiency
    query = """
    resources
    | project id, name, type, kind, sku, location, properties
    """
    # In production, dynamically determine subscriptions from token/user context
    subscriptions = [os.getenv("AZURE_SUBSCRIPTION_ID") or "<your-subscription-id>"]

    result = client.resources(query=query, subscriptions=subscriptions)
    resources = result.data

    # Format resources for AI prompt (limit for demo, real-world: batch in chunks)
    resource_list = [dict(row) for row in resources[:50]]

    # Prepare the prompt for OpenAI
    prompt = (
        "You are an Azure cloud optimization expert. "
        "Given the following list of Azure resources, identify those that are deprecated or outdated. "
        "For each deprecated/outdated resource, explain why and recommend the appropriate upgrade or migration path. "
        "Return your response as a JSON array: [{id, name, type, reason, recommendation}].\n\n"
        f"Resources:\n{json.dumps(resource_list, indent=2)}"
    )

    # Call Azure OpenAI
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
    # Parse the assistant's JSON output
    try:
        output_text = response["choices"][0]["message"]["content"]
        deprecated = json.loads(output_text)
    except Exception as e:
        deprecated = {"error": "Failed to parse response", "details": str(e), "raw": output_text}

    return deprecated