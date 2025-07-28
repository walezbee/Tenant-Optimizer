#!/usr/bin/env python3
"""
Health check script for deployed Tenant Optimizer application.
Tests the live deployment to ensure it's working correctly.
"""

import requests
import json
import sys
from urllib.parse import urljoin

def test_health_endpoint(base_url):
    """Test the health endpoint."""
    print("🏥 Testing health endpoint...")
    
    try:
        response = requests.get(urljoin(base_url, "/health"), timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Health endpoint responding")
            print(f"   Status: {health_data.get('status')}")
            print(f"   JWT Available: {health_data.get('jwt_available')}")
            print(f"   Agents Available: {health_data.get('agents_available')}")
            print(f"   Environment: {health_data.get('environment')}")
            return True
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Health endpoint request failed: {e}")
        return False

def test_static_files(base_url):
    """Test that static files are being served."""
    print("\n📁 Testing static file serving...")
    
    try:
        response = requests.get(base_url, timeout=10)
        
        if response.status_code == 200:
            if "Tenant Optimizer" in response.text:
                print("✅ Frontend is being served correctly")
                return True
            else:
                print("⚠️  Frontend served but content may be incorrect")
                return False
        else:
            print(f"❌ Frontend not accessible: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Frontend request failed: {e}")
        return False

def test_cors_headers(base_url):
    """Test CORS headers are present."""
    print("\n🌐 Testing CORS configuration...")
    
    try:
        response = requests.options(urljoin(base_url, "/health"), 
                                  headers={"Origin": "https://tenant-optimizer-web.azurewebsites.net"},
                                  timeout=10)
        
        cors_header = response.headers.get("Access-Control-Allow-Origin")
        if cors_header:
            print(f"✅ CORS headers present: {cors_header}")
            return True
        else:
            print("⚠️  CORS headers not found (may still work)")
            return True  # Don't fail on this
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  CORS test failed: {e}")
        return True  # Don't fail on this

def main():
    """Main test function."""
    base_url = "https://tenant-optimizer-web.azurewebsites.net"
    
    print("🧪 Testing Deployed Tenant Optimizer Application")
    print(f"🌐 Base URL: {base_url}")
    print("=" * 60)
    
    success = True
    
    # Test health endpoint
    if not test_health_endpoint(base_url):
        success = False
    
    # Test static files
    if not test_static_files(base_url):
        success = False
    
    # Test CORS
    test_cors_headers(base_url)
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Deployment health check passed!")
        print("✅ The application appears to be running correctly")
        print(f"🔗 Visit: {base_url}")
        sys.exit(0)
    else:
        print("❌ Deployment health check failed!")
        print("🔧 Check the application logs for more details")
        sys.exit(1)

if __name__ == "__main__":
    main()
