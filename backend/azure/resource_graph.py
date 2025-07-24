from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient

def run_resource_graph_query(subscription_id, query):
    cred = DefaultAzureCredential()
    client = ResourceGraphClient(cred)
    query_body = {
        "subscriptions": [subscription_id],
        "query": query
    }
    result = client.resources(**query_body)
    return result.data