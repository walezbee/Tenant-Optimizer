"""
Quick test script to validate automated upgrade system locally
"""

import asyncio
import json
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def test_agents_loading():
    """Test if all upgrade agents can be loaded"""
    print("🧪 Testing Automated Upgrade Agents...")
    
    results = {
        "agents": {},
        "dependencies": {}
    }
    
    # Test agent imports
    agents_to_test = [
        ("PublicIP Agent", "agents.upgrade_public_ip"),
        ("LoadBalancer Agent", "agents.upgrade_load_balancer"), 
        ("StorageAccount Agent", "agents.upgrade_storage_account"),
        ("Orchestrator", "agents.upgrade_orchestrator")
    ]
    
    for name, module_name in agents_to_test:
        try:
            module = __import__(module_name, fromlist=[''])
            results["agents"][name] = {
                "status": "✅ Loaded",
                "functions": [f for f in dir(module) if not f.startswith('_') and callable(getattr(module, f))]
            }
        except Exception as e:
            results["agents"][name] = {
                "status": f"❌ Failed: {str(e)}"
            }
    
    # Test dependencies
    dependencies_to_test = [
        ("Azure Identity", "azure.identity", "DefaultAzureCredential"),
        ("Azure Network", "azure.mgmt.network", "NetworkManagementClient"),
        ("Azure Storage", "azure.mgmt.storage", "StorageManagementClient"),
        ("Azure Resource", "azure.mgmt.resource", "ResourceManagementClient"),
        ("AsyncIO", "asyncio", "run"),
        ("HTTPX", "httpx", "AsyncClient")
    ]
    
    for name, module_name, test_class in dependencies_to_test:
        try:
            module = __import__(module_name, fromlist=[test_class])
            getattr(module, test_class)
            results["dependencies"][name] = "✅ Available"
        except Exception as e:
            results["dependencies"][name] = f"❌ Missing: {str(e)}"
    
    return results

async def test_simulation():
    """Test upgrade simulation logic"""
    print("\n🧪 Testing Upgrade Simulation...")
    
    # Test resource ID patterns
    test_resources = [
        "/subscriptions/12345/resourceGroups/test/providers/Microsoft.Network/publicIPAddresses/test-ip",
        "/subscriptions/12345/resourceGroups/test/providers/Microsoft.Network/loadBalancers/test-lb",
        "/subscriptions/12345/resourceGroups/test/providers/Microsoft.Storage/storageAccounts/testsa"
    ]
    
    simulation_results = {}
    
    for resource_id in test_resources:
        resource_type = None
        if "/publicIPAddresses/" in resource_id:
            resource_type = "Microsoft.Network/publicIPAddresses"
        elif "/loadBalancers/" in resource_id:
            resource_type = "Microsoft.Network/loadBalancers"
        elif "/storageAccounts/" in resource_id:
            resource_type = "Microsoft.Storage/storageAccounts"
        
        simulation_results[resource_id] = {
            "detected_type": resource_type,
            "would_simulate": resource_type is not None
        }
    
    return simulation_results

if __name__ == "__main__":
    async def main():
        print("🤖 Tenant Optimizer - Automated Upgrade System Test")
        print("=" * 60)
        
        # Test agent loading
        agent_results = await test_agents_loading()
        print("\n📋 Agent Loading Results:")
        for agent, result in agent_results["agents"].items():
            print(f"   {agent}: {result['status']}")
            if 'functions' in result:
                print(f"      Functions: {', '.join(result['functions'][:3])}{'...' if len(result['functions']) > 3 else ''}")
        
        print("\n📦 Dependency Check:")
        for dep, status in agent_results["dependencies"].items():
            print(f"   {dep}: {status}")
        
        # Test simulation
        sim_results = await test_simulation()
        print("\n🧪 Simulation Logic Test:")
        for resource_id, result in sim_results.items():
            resource_name = resource_id.split('/')[-1]
            print(f"   {resource_name}: {result['detected_type']} {'✅' if result['would_simulate'] else '❌'}")
        
        # Summary
        agents_working = sum(1 for result in agent_results["agents"].values() if "✅" in result["status"])
        deps_working = sum(1 for status in agent_results["dependencies"].values() if "✅" in status)
        
        print(f"\n📊 Summary:")
        print(f"   Agents Ready: {agents_working}/{len(agent_results['agents'])}")
        print(f"   Dependencies: {deps_working}/{len(agent_results['dependencies'])}")
        
        if agents_working == len(agent_results["agents"]) and deps_working == len(agent_results["dependencies"]):
            print("   🎉 System Status: READY FOR TESTING")
        else:
            print("   ⚠️  System Status: NEEDS ATTENTION")
            
    asyncio.run(main())
