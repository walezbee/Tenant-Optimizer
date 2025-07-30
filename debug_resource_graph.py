#!/usr/bin/env python3
"""
Debug script to test Azure Resource Graph API response format
"""
import httpx
import json
import asyncio
from datetime import datetime

async def test_resource_graph():
    """Test Resource Graph API to understand response format"""
    
    # This is a test query to see what the actual response looks like
    query = """
    Resources
    | where type == "microsoft.compute/disks"
    | project id, name, type, resourceGroup, location, subscriptionId
    | limit 5
    """
    
    url = "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
    
    # Note: This would need a valid token in real usage
    print("=== Resource Graph API Debug Test ===")
    print(f"Query: {query}")
    print(f"URL: {url}")
    print("Expected response format:")
    print(json.dumps({
        "data": {
            "rows": [
                ["/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Compute/disks/disk1", "disk1", "microsoft.compute/disks", "rg", "eastus", "subscription-id"]
            ],
            "columns": [
                {"name": "id", "type": "string"},
                {"name": "name", "type": "string"},
                {"name": "type", "type": "string"},
                {"name": "resourceGroup", "type": "string"},
                {"name": "location", "type": "string"},
                {"name": "subscriptionId", "type": "string"}
            ]
        }
    }, indent=2))
    print("\nThis format requires parsing rows with column mapping.")

if __name__ == "__main__":
    asyncio.run(test_resource_graph())
