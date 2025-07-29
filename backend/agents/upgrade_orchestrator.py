"""
Azure Resource Automated Upgrade Orchestrator

This orchestrator coordinates all specialized upgrade agents to provide
a unified interface for automated Azure resource upgrades.

It handles:
- Public IP upgrades (Basic to Standard SKU)
- Load Balancer upgrades (Basic to Standard SKU)  
- Storage Account optimizations
- Dependency resolution and ordering
- Error handling and rollback capabilities

Author: GitHub Copilot
Date: July 29, 2025
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
import json
import importlib
import sys
import os

# Add current directory to path for agent imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutomatedUpgradeOrchestrator:
    """
    Master orchestrator for automated Azure resource upgrades.
    Coordinates multiple specialized agents for different resource types.
    """
    
    def __init__(self, subscription_id: str):
        """Initialize the orchestrator."""
        self.subscription_id = subscription_id
        self.credential = DefaultAzureCredential()
        self.resource_client = ResourceManagementClient(self.credential, subscription_id)
        
        # Track available agents
        self.agents = {
            'Microsoft.Network/publicIPAddresses': 'upgrade_public_ip',
            'Microsoft.Network/loadBalancers': 'upgrade_load_balancer', 
            'Microsoft.Storage/storageAccounts': 'upgrade_storage_account'
        }
        
    async def upgrade_resource(self, resource_id: str, resource_type: str = None) -> Dict[str, Any]:
        """
        Main method to automatically upgrade any supported Azure resource.
        
        Args:
            resource_id: Full Azure resource ID
            resource_type: Optional resource type override
            
        Returns:
            Dict containing upgrade results and details
        """
        try:
            logger.info(f"Starting automated upgrade orchestration for: {resource_id}")
            
            # Determine resource type from ID if not provided
            if not resource_type:
                resource_type = self._extract_resource_type(resource_id)
                
            if not resource_type:
                return {
                    "success": False,
                    "error": "Could not determine resource type from resource ID"
                }
                
            # Check if we have an agent for this resource type
            if resource_type not in self.agents:
                return {
                    "success": False,
                    "error": f"No automated upgrade agent available for resource type: {resource_type}",
                    "supported_types": list(self.agents.keys())
                }
                
            # Get resource details for context
            resource_details = await self._get_resource_details(resource_id)
            
            # Execute the appropriate upgrade agent
            upgrade_result = await self._execute_upgrade_agent(
                resource_type, resource_id, resource_details
            )
            
            # Enhance result with orchestration metadata
            if upgrade_result.get('success', False):
                upgrade_result['orchestration'] = {
                    'agent_used': self.agents[resource_type],
                    'resource_type': resource_type,
                    'automation_level': 'Full',
                    'timestamp': self._get_timestamp()
                }
                logger.info(f"Automated upgrade completed successfully: {resource_id}")
            else:
                logger.error(f"Automated upgrade failed: {resource_id} - {upgrade_result.get('error', 'Unknown error')}")
                
            return upgrade_result
            
        except Exception as e:
            logger.error(f"Orchestration failed: {str(e)}")
            return {
                "success": False,
                "error": f"Orchestration process failed: {str(e)}",
                "resource_id": resource_id
            }
    
    async def upgrade_multiple_resources(self, resource_list: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Upgrade multiple resources with dependency resolution.
        
        Args:
            resource_list: List of dicts with 'id' and optionally 'type' keys
            
        Returns:
            Dict containing results for all resources
        """
        try:
            logger.info(f"Starting batch upgrade for {len(resource_list)} resources")
            
            # Sort resources by dependency order (Public IPs first, then LBs)
            sorted_resources = self._sort_by_dependencies(resource_list)
            
            results = {
                'success': True,
                'total_resources': len(resource_list),
                'successful_upgrades': 0,
                'failed_upgrades': 0,
                'skipped_upgrades': 0,
                'individual_results': []
            }
            
            # Process resources in dependency order
            for resource_info in sorted_resources:
                resource_id = resource_info['id']
                resource_type = resource_info.get('type')
                
                logger.info(f"Processing resource: {resource_id}")
                
                # Execute upgrade
                upgrade_result = await self.upgrade_resource(resource_id, resource_type)
                
                # Update counters
                if upgrade_result.get('success', False):
                    if upgrade_result.get('skipped', False):
                        results['skipped_upgrades'] += 1
                    else:
                        results['successful_upgrades'] += 1
                else:
                    results['failed_upgrades'] += 1
                    results['success'] = False  # Overall batch fails if any resource fails
                
                # Store individual result
                results['individual_results'].append({
                    'resource_id': resource_id,
                    'resource_type': resource_type,
                    'result': upgrade_result
                })
                
                # Add delay between resources to avoid throttling
                await asyncio.sleep(2)
            
            logger.info(f"Batch upgrade completed. Success: {results['successful_upgrades']}, "
                       f"Failed: {results['failed_upgrades']}, Skipped: {results['skipped_upgrades']}")
            
            return results
            
        except Exception as e:
            logger.error(f"Batch upgrade failed: {str(e)}")
            return {
                "success": False,
                "error": f"Batch upgrade process failed: {str(e)}"
            }
    
    def _extract_resource_type(self, resource_id: str) -> Optional[str]:
        """Extract resource type from Azure resource ID."""
        try:
            parts = resource_id.strip('/').split('/')
            if len(parts) >= 7:
                provider = parts[5]  # Microsoft.Network, Microsoft.Storage, etc.
                resource_type = parts[6]  # publicIPAddresses, loadBalancers, etc.
                return f"{provider}/{resource_type}"
        except Exception as e:
            logger.error(f"Failed to extract resource type: {str(e)}")
        return None
    
    async def _get_resource_details(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """Get basic resource details for context."""
        try:
            # Extract resource group and name from ID
            parts = resource_id.strip('/').split('/')
            if len(parts) >= 8:
                resource_group = parts[3]
                resource_name = parts[-1]
                provider_namespace = parts[5]
                resource_type = parts[6]
                
                # Get resource using the Resource Management API
                resource = self.resource_client.resources.get(
                    resource_group_name=resource_group,
                    resource_provider_namespace=provider_namespace,
                    parent_resource_path='',
                    resource_type=resource_type,
                    resource_name=resource_name,
                    api_version='2021-04-01'
                )
                
                return {
                    'name': resource.name,
                    'location': resource.location,
                    'type': resource.type,
                    'tags': resource.tags
                }
        except Exception as e:
            logger.warning(f"Could not get resource details: {str(e)}")
        return None
    
    async def _execute_upgrade_agent(self, resource_type: str, resource_id: str, 
                                   resource_details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute the appropriate upgrade agent for the resource type."""
        try:
            agent_module_name = self.agents[resource_type]
            
            # Import the agent module dynamically
            try:
                agent_module = importlib.import_module(agent_module_name)
            except ImportError as e:
                logger.error(f"Could not import agent module {agent_module_name}: {str(e)}")
                return {
                    "success": False,
                    "error": f"Agent module not available: {agent_module_name}"
                }
            
            # Call the appropriate upgrade function
            if resource_type == 'Microsoft.Network/publicIPAddresses':
                if hasattr(agent_module, 'upgrade_public_ip_automated'):
                    return await agent_module.upgrade_public_ip_automated(
                        self.subscription_id, resource_id
                    )
                    
            elif resource_type == 'Microsoft.Network/loadBalancers':
                if hasattr(agent_module, 'upgrade_load_balancer_automated'):
                    return await agent_module.upgrade_load_balancer_automated(
                        self.subscription_id, resource_id
                    )
                    
            elif resource_type == 'Microsoft.Storage/storageAccounts':
                if hasattr(agent_module, 'upgrade_storage_account_automated'):
                    return await agent_module.upgrade_storage_account_automated(
                        self.subscription_id, resource_id
                    )
            
            return {
                "success": False,
                "error": f"Upgrade function not found in agent module: {agent_module_name}"
            }
            
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            return {
                "success": False,
                "error": f"Agent execution failed: {str(e)}"
            }
    
    def _sort_by_dependencies(self, resource_list: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Sort resources by upgrade dependencies (Public IPs before Load Balancers)."""
        priority_order = {
            'Microsoft.Network/publicIPAddresses': 1,
            'Microsoft.Storage/storageAccounts': 2,
            'Microsoft.Network/loadBalancers': 3,  # Load Balancers last (depend on Public IPs)
        }
        
        def get_priority(resource_info):
            resource_type = resource_info.get('type')
            if not resource_type:
                resource_type = self._extract_resource_type(resource_info['id'])
            return priority_order.get(resource_type, 999)
        
        return sorted(resource_list, key=get_priority)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for logging."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'

# Main execution functions for API integration
async def upgrade_resource_automated(subscription_id: str, resource_id: str, 
                                   resource_type: str = None) -> Dict[str, Any]:
    """
    Main function to perform automated resource upgrade.
    
    Args:
        subscription_id: Azure subscription ID
        resource_id: Full resource ID of the resource to upgrade
        resource_type: Optional resource type override
        
    Returns:
        Dict containing upgrade results
    """
    orchestrator = AutomatedUpgradeOrchestrator(subscription_id)
    return await orchestrator.upgrade_resource(resource_id, resource_type)

async def upgrade_multiple_resources_automated(subscription_id: str, 
                                             resource_list: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Main function to perform batch automated resource upgrades.
    
    Args:
        subscription_id: Azure subscription ID
        resource_list: List of resources to upgrade
        
    Returns:
        Dict containing batch upgrade results
    """
    orchestrator = AutomatedUpgradeOrchestrator(subscription_id)
    return await orchestrator.upgrade_multiple_resources(resource_list)

# Example usage and testing
if __name__ == "__main__":
    async def test_orchestrator():
        # Example usage
        subscription_id = "your-subscription-id"
        
        # Single resource upgrade
        resource_id = "/subscriptions/your-sub/resourceGroups/your-rg/providers/Microsoft.Network/publicIPAddresses/your-ip"
        result = await upgrade_resource_automated(subscription_id, resource_id)
        print("Single resource result:")
        print(json.dumps(result, indent=2))
        
        # Batch upgrade
        resource_list = [
            {"id": "/subscriptions/your-sub/resourceGroups/your-rg/providers/Microsoft.Network/publicIPAddresses/ip1"},
            {"id": "/subscriptions/your-sub/resourceGroups/your-rg/providers/Microsoft.Network/loadBalancers/lb1"}
        ]
        batch_result = await upgrade_multiple_resources_automated(subscription_id, resource_list)
        print("\nBatch upgrade result:")
        print(json.dumps(batch_result, indent=2))
    
    # Uncomment to test
    # asyncio.run(test_orchestrator())
