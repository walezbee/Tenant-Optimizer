from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from openai import OpenAI
import os

def detect_orphaned_resources(token):
    cred = DefaultAzureCredential()
    client = ResourceGraphClient(cred)
    # Query for all resources (demo: unattached disks)
    query = """
    resources
    | where type =~ 'microsoft.compute/disks'
    | where managedBy == ''
    """
    result = client.resources(query=query, subscriptions=['<sub_id>'])
    disks = result.data
    # Call OpenAI to classify
    openai_client = OpenAI(api_key=os.getenv('OPENAI_KEY'))
    prompt = f"Given these resources: {disks}, which are orphaned?"
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message.content