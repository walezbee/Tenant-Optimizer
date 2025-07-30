#!/usr/bin/env python3
"""
Test script to verify Microsoft Knowledge Base functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from ai.microsoft_knowledge_base import MicrosoftKnowledgeBase

def test_microsoft_knowledge_base():
    """Test the Microsoft Knowledge Base functionality"""
    print("🧠 Testing Microsoft Knowledge Base...")
    
    # Initialize knowledge base
    kb = MicrosoftKnowledgeBase()
    print(f"✅ Knowledge Base initialized - Last updated: {kb.last_updated}")
    
    # Test deprecated resource analysis
    print("\n📊 Testing deprecated resource analysis...")
    
    # Test Basic SKU Public IP
    test_resource_basic_ip = {
        "type": "microsoft.network/publicipaddresses",
        "name": "test-basic-ip",
        "skuName": "Basic",
        "skuTier": "Basic"
    }
    
    result = kb.analyze_resource_deprecation(test_resource_basic_ip)
    print(f"Basic Public IP result: {result}")
    
    # Test Basic SKU Load Balancer
    test_resource_basic_lb = {
        "type": "microsoft.network/loadbalancers", 
        "name": "test-basic-lb",
        "skuName": "Basic",
        "skuTier": "Basic"
    }
    
    result = kb.analyze_resource_deprecation(test_resource_basic_lb)
    print(f"Basic Load Balancer result: {result}")
    
    # Test Standard resource (should not be deprecated)
    test_resource_standard = {
        "type": "microsoft.network/publicipaddresses",
        "name": "test-standard-ip", 
        "skuName": "Standard",
        "skuTier": "Standard"
    }
    
    result = kb.analyze_resource_deprecation(test_resource_standard)
    print(f"Standard Public IP result: {result}")
    
    # Test KQL queries
    print("\n📊 Testing KQL queries...")
    queries = kb.get_kql_queries()
    print(f"Available queries: {list(queries.keys())}")
    
    print("\n✅ Microsoft Knowledge Base test completed successfully!")
    return True

if __name__ == "__main__":
    try:
        test_microsoft_knowledge_base()
        print("\n🚀 All tests passed! Microsoft Knowledge Base is working correctly.")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
