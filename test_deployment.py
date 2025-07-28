#!/usr/bin/env python3
"""
Simple test script to verify the main application can start.
Run this locally to test before deployment.
"""

import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        import fastapi
        print("✅ FastAPI imported successfully")
    except ImportError as e:
        print(f"❌ FastAPI import failed: {e}")
        return False
    
    try:
        import uvicorn
        print("✅ Uvicorn imported successfully")
    except ImportError as e:
        print(f"❌ Uvicorn import failed: {e}")
        return False
    
    try:
        import httpx
        print("✅ HTTPX imported successfully")
    except ImportError as e:
        print(f"❌ HTTPX import failed: {e}")
        return False
    
    try:
        import jwt
        print("✅ PyJWT imported successfully")
    except ImportError as e:
        print(f"❌ PyJWT import failed: {e}")
        return False
    
    try:
        import openai
        print("✅ OpenAI imported successfully")
    except ImportError as e:
        print(f"❌ OpenAI import failed: {e}")
        return False
    
    return True

def test_main_module():
    """Test that the main application module can be imported."""
    print("\nTesting main module...")
    
    try:
        from backend import main
        print("✅ Main module imported successfully")
        
        # Test FastAPI app creation
        app = main.app
        print(f"✅ FastAPI app created: {app.title}")
        
        return True
    except ImportError as e:
        print(f"❌ Main module import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Main module error: {e}")
        return False

def test_agent_modules():
    """Test that agent modules can be imported."""
    print("\nTesting agent modules...")
    
    agents = [
        'detect_orphaned',
        'detect_deprecated', 
        'delete_orphaned',
        'upgrade_deprecated'
    ]
    
    all_good = True
    for agent in agents:
        try:
            module = __import__(f'backend.agents.{agent}', fromlist=[agent])
            print(f"✅ Agent {agent} imported successfully")
        except ImportError as e:
            print(f"⚠️  Agent {agent} import warning: {e}")
            # Don't fail on agent imports since we have fallbacks
        except Exception as e:
            print(f"❌ Agent {agent} error: {e}")
            all_good = False
    
    return all_good

if __name__ == "__main__":
    print("🧪 Testing Tenant Optimizer Application")
    print("=" * 50)
    
    success = True
    
    # Test core imports
    if not test_imports():
        success = False
    
    # Test main module
    if not test_main_module():
        success = False
    
    # Test agent modules
    if not test_agent_modules():
        print("⚠️  Some agent modules had issues, but app should still work")
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All critical tests passed! Deployment should work.")
        sys.exit(0)
    else:
        print("❌ Some critical tests failed. Check the errors above.")
        sys.exit(1)
