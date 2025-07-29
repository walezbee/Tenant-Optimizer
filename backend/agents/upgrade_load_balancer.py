"""
Azure Load Balancer Automated Upgrade Agent

This agent automates Load Balancer upgrades from Basic to Standard SKU,
handling all the complex dependency management and configuration updates.

Author: GitHub Copilot
Date: July 29, 2025
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import LoadBalancer, LoadBalancerSku, LoadBalancerSkuName, LoadBalancerSkuTier
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoadBalancerUpgradeAgent:
    """
    Automated agent for upgrading Load Balancers from Basic to Standard SKU.
    Handles backend pool, rule, and probe configuration preservation.
    """
    
    def __init__(self, subscription_id: str):
        """Initialize the upgrade agent."""
        self.subscription_id = subscription_id
        self.credential = DefaultAzureCredential()
        self.network_client = NetworkManagementClient(self.credential, subscription_id)
        
    async def upgrade_load_balancer(self, resource_id: str) -> Dict[str, Any]:
        """
        Main method to upgrade a Load Balancer from Basic to Standard SKU.
        
        Args:
            resource_id: Full Azure resource ID of the Load Balancer
            
        Returns:
            Dict containing upgrade results and details
        """
        try:
            logger.info(f"Starting automated Load Balancer upgrade: {resource_id}")
            
            # Parse resource ID
            resource_parts = self._parse_resource_id(resource_id)
            if not resource_parts:
                return {"success": False, "error": "Invalid resource ID format"}
                
            # Get current Load Balancer configuration
            current_config = await self._get_load_balancer_details(
                resource_parts['resource_group'], 
                resource_parts['resource_name']
            )
            
            if not current_config:
                return {"success": False, "error": "Could not retrieve Load Balancer details"}
                
            # Check if upgrade is needed
            if current_config.sku and current_config.sku.name and current_config.sku.name.lower() == 'standard':
                return {
                    "success": True, 
                    "message": "Load Balancer is already Standard SKU",
                    "skipped": True
                }
                
            # Validate upgrade compatibility
            compatibility_check = await self._check_upgrade_compatibility(current_config)
            if not compatibility_check['compatible']:
                return {
                    "success": False,
                    "error": f"Upgrade not compatible: {compatibility_check['reason']}"
                }
                
            # Perform the upgrade
            upgrade_result = await self._perform_upgrade(
                resource_parts['resource_group'],
                resource_parts['resource_name'],
                current_config
            )
            
            if upgrade_result['success']:
                return {
                    "success": True,
                    "resource_id": resource_id,
                    "upgrade_details": {
                        "original_sku": "Basic",
                        "new_sku": "Standard",
                        "frontend_configs_count": len(current_config.frontend_ip_configurations or []),
                        "backend_pools_count": len(current_config.backend_address_pools or []),
                        "rules_count": len(current_config.load_balancing_rules or [])
                    },
                    "steps_completed": [
                        "✅ Validated upgrade compatibility",
                        "✅ Preserved frontend IP configurations",
                        "✅ Preserved backend address pools",
                        "✅ Preserved load balancing rules",
                        "✅ Upgraded SKU from Basic to Standard"
                    ]
                }
            else:
                return {
                    "success": False,
                    "error": f"Load Balancer upgrade failed: {upgrade_result['error']}"
                }
                
        except Exception as e:
            logger.error(f"Load Balancer upgrade failed: {str(e)}")
            return {
                "success": False,
                "error": f"Upgrade process failed: {str(e)}",
                "resource_id": resource_id
            }
    
    def _parse_resource_id(self, resource_id: str) -> Optional[Dict[str, str]]:
        """Parse Azure resource ID into components."""
        try:
            parts = resource_id.strip('/').split('/')
            if len(parts) >= 8 and 'loadBalancers' in parts:
                return {
                    'subscription_id': parts[1],
                    'resource_group': parts[3],
                    'resource_name': parts[-1]
                }
        except Exception as e:
            logger.error(f"Failed to parse resource ID: {str(e)}")
        return None
    
    async def _get_load_balancer_details(self, resource_group: str, resource_name: str) -> Optional[LoadBalancer]:
        """Get current Load Balancer configuration."""
        try:
            load_balancer = self.network_client.load_balancers.get(
                resource_group_name=resource_group,
                load_balancer_name=resource_name
            )
            current_sku = load_balancer.sku.name if load_balancer.sku else "Basic"
            logger.info(f"Retrieved Load Balancer details: {resource_name} (SKU: {current_sku})")
            return load_balancer
        except Exception as e:
            logger.error(f"Failed to get Load Balancer details: {str(e)}")
            return None
    
    async def _check_upgrade_compatibility(self, load_balancer: LoadBalancer) -> Dict[str, Any]:
        """Check if the Load Balancer can be upgraded safely."""
        try:
            # Check for incompatible configurations
            issues = []
            
            # Check Public IP compatibility
            for frontend_config in load_balancer.frontend_ip_configurations or []:
                if frontend_config.public_ip_address:
                    try:
                        # Get Public IP details to check SKU
                        public_ip_parts = frontend_config.public_ip_address.id.split('/')
                        public_ip_name = public_ip_parts[-1]
                        resource_group = public_ip_parts[4]
                        
                        public_ip = self.network_client.public_ip_addresses.get(
                            resource_group, public_ip_name
                        )
                        
                        if public_ip.sku and public_ip.sku.name.lower() == 'basic':
                            issues.append(f"Public IP '{public_ip_name}' must be upgraded to Standard SKU first")
                            
                    except Exception as e:
                        logger.warning(f"Could not check Public IP compatibility: {str(e)}")
            
            # Check availability zones (Standard LB supports zones, Basic doesn't)
            if load_balancer.frontend_ip_configurations:
                for frontend_config in load_balancer.frontend_ip_configurations:
                    if hasattr(frontend_config, 'zones') and frontend_config.zones:
                        # This is fine for Standard SKU
                        pass
            
            if issues:
                return {
                    'compatible': False,
                    'reason': '; '.join(issues)
                }
            
            return {'compatible': True}
            
        except Exception as e:
            logger.error(f"Compatibility check failed: {str(e)}")
            return {
                'compatible': False,
                'reason': f"Compatibility check failed: {str(e)}"
            }
    
    async def _perform_upgrade(self, resource_group: str, load_balancer_name: str, 
                             current_config: LoadBalancer) -> Dict[str, Any]:
        """Perform the actual Load Balancer SKU upgrade."""
        try:
            # Create updated configuration with Standard SKU
            updated_config = LoadBalancer(
                location=current_config.location,
                sku=LoadBalancerSku(
                    name=LoadBalancerSkuName.STANDARD,
                    tier=LoadBalancerSkuTier.REGIONAL
                ),
                frontend_ip_configurations=current_config.frontend_ip_configurations,
                backend_address_pools=current_config.backend_address_pools,
                load_balancing_rules=current_config.load_balancing_rules,
                probes=current_config.probes,
                inbound_nat_rules=current_config.inbound_nat_rules,
                inbound_nat_pools=current_config.inbound_nat_pools,
                outbound_rules=current_config.outbound_rules,
                tags=current_config.tags
            )
            
            # Perform the upgrade
            logger.info(f"Upgrading Load Balancer SKU: {load_balancer_name}")
            operation = self.network_client.load_balancers.begin_create_or_update(
                resource_group_name=resource_group,
                load_balancer_name=load_balancer_name,
                parameters=updated_config
            )
            
            # Wait for completion
            result = operation.wait()
            
            logger.info(f"Load Balancer SKU upgrade completed: {load_balancer_name} -> Standard")
            return {
                'success': True,
                'new_sku': 'Standard',
                'resource_id': result.id
            }
            
        except Exception as e:
            logger.error(f"Load Balancer SKU upgrade failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

# Main execution function for API integration
async def upgrade_load_balancer_automated(subscription_id: str, resource_id: str) -> Dict[str, Any]:
    """
    Main function to perform automated Load Balancer upgrade.
    
    Args:
        subscription_id: Azure subscription ID
        resource_id: Full resource ID of the Load Balancer to upgrade
        
    Returns:
        Dict containing upgrade results
    """
    agent = LoadBalancerUpgradeAgent(subscription_id)
    return await agent.upgrade_load_balancer(resource_id)
