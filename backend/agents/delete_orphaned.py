import httpx

async def delete_orphaned_resources(user_token, approval_payload):
    """
    Deletes the orphaned resources listed in approval_payload using the user's token.
    approval_payload: dict with:
      - 'subscription_id': subscription id string
      - 'resources': list of { 'id': resourceId }
    """
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }
    deleted = []
    for res in approval_payload.get('resources', []):
        resource_id = res['id']
        # Use the appropriate api-version for your resource type if needed
        url = f"https://management.azure.com{resource_id}?api-version=2022-09-01"
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.delete(url, headers=headers)
                resp.raise_for_status()
                deleted.append(res['id'])
            except Exception as e:
                deleted.append({'id': res['id'], 'error': str(e)})
    return {'deleted': deleted}