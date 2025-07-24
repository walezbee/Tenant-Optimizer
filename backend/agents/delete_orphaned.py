from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient

def delete_orphaned_resources(token, approval_payload):
    """
    Deletes the orphaned resources listed in approval_payload.
    approval_payload: dict with 'resources': list of { 'id': resourceId }
    """
    cred = DefaultAzureCredential()
    subscription_id = approval_payload.get('subscription_id')
    client = ResourceManagementClient(cred, subscription_id)
    deleted = []
    for res in approval_payload.get('resources', []):
        try:
            client.resources.begin_delete_by_id(res['id'], api_version='2022-09-01')
            deleted.append(res['id'])
        except Exception as e:
            deleted.append({'id': res['id'], 'error': str(e)})
    return {'deleted': deleted}