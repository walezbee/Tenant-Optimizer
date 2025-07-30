"""
Test script to verify Resource Graph API calls work with your subscription
"""
import asyncio
import httpx
import json

async def test_subscription_access():
    """Test if we can list subscriptions"""
    print("=== Testing Subscription Access ===")
    print("Please test at: https://tenant-optimizer-web.azurewebsites.net/")
    print()
    print("Steps to diagnose the issue:")
    print("1. Open browser developer tools (F12)")
    print("2. Go to Console tab")
    print("3. Navigate to the tenant optimizer app")
    print("4. Login with your Azure credentials")
    print("5. Select subscriptions") 
    print("6. Click 'Scan Orphaned Resources' or 'Scan Deprecated Resources'")
    print("7. Check the Network tab for API calls and their responses")
    print("8. Look for any error messages in Console")
    print()
    print("Expected behavior:")
    print("- The scan should show detailed logs in the application logs")
    print("- You should see the column names and row counts")
    print("- If no resources are found, it will show 0 resources but with debug info")
    print()
    print("Common issues:")
    print("- Empty subscriptions: No orphaned or deprecated resources exist")
    print("- Permissions: User may not have Reader access to Resource Graph")
    print("- Authentication: Token may have expired")
    print()
    print("If you still see no resources, please check the browser developer tools")
    print("and share any error messages you see in the Network or Console tabs.")

if __name__ == "__main__":
    asyncio.run(test_subscription_access())
