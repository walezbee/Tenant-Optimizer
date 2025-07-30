"""
Azure Public IP Automated Upgrade Agent

This agent automates the complete Public IP upgrade process from Basic to Standard SKU,
handling all the manual steps that were previously required:
1. Navigate to Azure Portal (programmatically connect to Azure APIs)
2. Open the Public IP Resource (retrieve resource details)  
3. Dissociate from Attached Resources (detach from NICs, Load Balancers, etc.)
4. Change SKU from Basic to Standard (perform the upgrade)
5. Re-associate with Resources (reattach to original resources)

Author: GitHub Copilot
Date: July 29, 2025
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
import json
import time

# HTTP client for direct API calls
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

# Optional Azure SDK imports - graceful fallback if not available
try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.network.models import PublicIPAddress, PublicIPAddressSku, PublicIPAddressSkuName, PublicIPAddressSkuTier
    AZURE_SDK_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Azure SDK not available: {e}")
    AZURE_SDK_AVAILABLE = False
    # Create dummy classes to prevent import errors
    class DefaultAzureCredential:
        pass
    class NetworkManagementClient:
        pass
    class PublicIPAddress:
        pass
    class PublicIPAddressSku:
        pass
    class PublicIPAddressSkuName:
        pass
    class PublicIPAddressSkuTier:
        pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PublicIPUpgradeAgent:
    """
    Automated agent for upgrading Public IP addresses from Basic to Standard SKU.
    Handles all association/dissociation logic automatically.
    """
    
    def __init__(self, subscription_id: str):
        """Initialize the upgrade agent."""
        self.subscription_id = subscription_id
        self.sdk_available = AZURE_SDK_AVAILABLE
        
        # Try to initialize Azure SDK if available
        try:
            if self.sdk_available:
                self.credential = DefaultAzureCredential()
                self.network_client = NetworkManagementClient(self.credential, subscription_id)
                logger.info("🔑 PublicIP Agent using DefaultAzureCredential for authentication")
            else:
                raise Exception("Azure SDK not available")
        except Exception as e:
            logger.warning(f"⚠️ PublicIP Agent Azure SDK authentication failed: {e}")
            self.credential = None
            self.network_client = None
        
    async def upgrade_public_ip(self, resource_id: str) -> Dict[str, Any]:
        """
        Main method to upgrade a Public IP from Basic to Standard SKU.
        
        Args:
            resource_id: Full Azure resource ID of the Public IP
            
        Returns:
            Dict containing upgrade results and details
        """
        if not self.sdk_available:
            return {
                "success": False,
                "error": "Azure SDK dependencies not available",
                "message": "Automated upgrade requires Azure SDK packages",
                "fallback_required": True,
                "manual_instructions": self._get_manual_upgrade_instructions(resource_id)
            }
            
        try:
            logger.info(f"Starting automated upgrade for Public IP: {resource_id}")
            
            # Step 1: Parse resource ID and get resource details
            resource_parts = self._parse_resource_id(resource_id)
            if not resource_parts:
                return {"success": False, "error": "Invalid resource ID format"}
                
            # Step 2: Get current Public IP configuration
            current_config = await self._get_public_ip_details(
                resource_parts['resource_group'], 
                resource_parts['resource_name']
            )
            
            if not current_config:
                return {"success": False, "error": "Could not retrieve Public IP details"}
                
            # Step 3: Check if upgrade is needed
            if current_config.sku.name.lower() == 'standard':
                return {
                    "success": True, 
                    "message": "Public IP is already Standard SKU",
                    "skipped": True
                }
                
            # Step 4: Find and document attached resources
            attached_resources = await self._find_attached_resources(
                resource_parts['resource_group'],
                resource_parts['resource_name']
            )
            
            logger.info(f"Found {len(attached_resources)} attached resources")
            
            # Step 5: Dissociate from attached resources
            dissociation_results = await self._dissociate_from_resources(
                resource_parts['resource_group'],
                attached_resources
            )
            
            if not dissociation_results['success']:
                return {
                    "success": False,
                    "error": f"Failed to dissociate resources: {dissociation_results['error']}"
                }
                
            # Step 6: Perform the SKU upgrade
            upgrade_result = await self._upgrade_sku(
                resource_parts['resource_group'],
                resource_parts['resource_name'],
                current_config
            )
            
            if not upgrade_result['success']:
                # If upgrade fails, try to re-associate resources
                await self._re_associate_resources(
                    resource_parts['resource_group'],
                    attached_resources,
                    dissociation_results['original_configs']
                )
                return {
                    "success": False,
                    "error": f"SKU upgrade failed: {upgrade_result['error']}"
                }
                
            # Step 7: Re-associate with resources
            association_results = await self._re_associate_resources(
                resource_parts['resource_group'],
                attached_resources,
                dissociation_results['original_configs']
            )
            
            # Step 8: Prepare detailed results
            results = {
                "success": True,
                "resource_id": resource_id,
                "upgrade_details": {
                    "original_sku": "Basic",
                    "new_sku": "Standard",
                    "attached_resources_count": len(attached_resources),
                    "dissociation_success": dissociation_results['success'],
                    "upgrade_success": upgrade_result['success'],
                    "re_association_success": association_results['success']
                },
                "steps_completed": [
                    "✅ Retrieved Public IP configuration",
                    "✅ Identified attached resources",
                    "✅ Dissociated from attached resources",
                    "✅ Upgraded SKU from Basic to Standard",
                    "✅ Re-associated with resources"
                ]
            }
            
            if not association_results['success']:
                results["warnings"] = [
                    f"Re-association partially failed: {association_results['error']}",
                    "Manual verification of resource associations recommended"
                ]
                
            logger.info(f"Public IP upgrade completed successfully: {resource_id}")
            return results
            
        except Exception as e:
            logger.error(f"Public IP upgrade failed: {str(e)}")
            return {
                "success": False,
                "error": f"Upgrade process failed: {str(e)}",
                "resource_id": resource_id
            }
    
    def _parse_resource_id(self, resource_id: str) -> Optional[Dict[str, str]]:
        """Parse Azure resource ID into components."""
        try:
            parts = resource_id.strip('/').split('/')
            if len(parts) >= 8 and 'publicIPAddresses' in parts:
                return {
                    'subscription_id': parts[1],
                    'resource_group': parts[3],
                    'resource_name': parts[-1]
                }
        except Exception as e:
            logger.error(f"Failed to parse resource ID: {str(e)}")
        return None
    
    async def _get_public_ip_details(self, resource_group: str, resource_name: str) -> Optional[PublicIPAddress]:
        """Get current Public IP configuration."""
        try:
            public_ip = self.network_client.public_ip_addresses.get(
                resource_group_name=resource_group,
                public_ip_address_name=resource_name
            )
            logger.info(f"Retrieved Public IP details: {resource_name} (SKU: {public_ip.sku.name})")
            return public_ip
        except Exception as e:
            logger.error(f"Failed to get Public IP details: {str(e)}")
            return None
    
    async def _find_attached_resources(self, resource_group: str, public_ip_name: str) -> List[Dict[str, Any]]:
        """Find all resources attached to this Public IP."""
        attached_resources = []
        
        try:
            # Get the Public IP to check its configuration
            public_ip = self.network_client.public_ip_addresses.get(
                resource_group_name=resource_group,
                public_ip_address_name=public_ip_name
            )
            
            # Check if attached to Network Interface
            if public_ip.ip_configuration:
                attached_resources.append({
                    'type': 'NetworkInterface',
                    'id': public_ip.ip_configuration.id,
                    'name': public_ip.ip_configuration.id.split('/')[-3] if public_ip.ip_configuration.id else None
                })
            
            # Check Load Balancers in the resource group
            load_balancers = self.network_client.load_balancers.list(resource_group)
            for lb in load_balancers:
                for frontend_config in lb.frontend_ip_configurations or []:
                    if (frontend_config.public_ip_address and 
                        frontend_config.public_ip_address.id and
                        public_ip_name in frontend_config.public_ip_address.id):
                        attached_resources.append({
                            'type': 'LoadBalancer',
                            'id': lb.id,
                            'name': lb.name,
                            'frontend_config': frontend_config.name
                        })
            
            # Check Application Gateways
            try:
                app_gateways = self.network_client.application_gateways.list(resource_group)
                for ag in app_gateways:
                    for frontend_config in ag.frontend_ip_configurations or []:
                        if (frontend_config.public_ip_address and 
                            frontend_config.public_ip_address.id and
                            public_ip_name in frontend_config.public_ip_address.id):
                            attached_resources.append({
                                'type': 'ApplicationGateway',
                                'id': ag.id,
                                'name': ag.name,
                                'frontend_config': frontend_config.name
                            })
            except Exception as e:
                logger.warning(f"Could not check Application Gateways: {str(e)}")
            
            logger.info(f"Found attached resources: {[r['type'] + ':' + r['name'] for r in attached_resources]}")
            return attached_resources
            
        except Exception as e:
            logger.error(f"Failed to find attached resources: {str(e)}")
            return []
    
    async def _dissociate_from_resources(self, resource_group: str, attached_resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Dissociate Public IP from all attached resources."""
        original_configs = {}
        
        try:
            for resource in attached_resources:
                if resource['type'] == 'NetworkInterface':
                    # Handle Network Interface dissociation
                    nic_name = resource['name']
                    if nic_name:
                        nic = self.network_client.network_interfaces.get(resource_group, nic_name)
                        original_configs[resource['id']] = {
                            'type': 'NetworkInterface',
                            'name': nic_name,
                            'ip_configurations': []
                        }
                        
                        # Store original IP configurations and remove public IP references
                        for ip_config in nic.ip_configurations or []:
                            original_configs[resource['id']]['ip_configurations'].append({
                                'name': ip_config.name,
                                'had_public_ip': ip_config.public_ip_address is not None,
                                'public_ip_id': ip_config.public_ip_address.id if ip_config.public_ip_address else None
                            })
                            
                            # Remove public IP reference
                            if ip_config.public_ip_address:
                                ip_config.public_ip_address = None
                        
                        # Update the NIC
                        operation = self.network_client.network_interfaces.begin_create_or_update(
                            resource_group, nic_name, nic
                        )
                        operation.wait()
                        logger.info(f"Dissociated Public IP from Network Interface: {nic_name}")
                
                elif resource['type'] == 'LoadBalancer':
                    # Handle Load Balancer dissociation
                    lb_name = resource['name']
                    lb = self.network_client.load_balancers.get(resource_group, lb_name)
                    original_configs[resource['id']] = {
                        'type': 'LoadBalancer',
                        'name': lb_name,
                        'frontend_configs': []
                    }
                    
                    # Store original frontend configurations and remove public IP references
                    for frontend_config in lb.frontend_ip_configurations or []:
                        original_configs[resource['id']]['frontend_configs'].append({
                            'name': frontend_config.name,
                            'had_public_ip': frontend_config.public_ip_address is not None,
                            'public_ip_id': frontend_config.public_ip_address.id if frontend_config.public_ip_address else None
                        })
                        
                        # Remove public IP reference if it matches
                        if (frontend_config.public_ip_address and 
                            resource.get('frontend_config') == frontend_config.name):
                            frontend_config.public_ip_address = None
                    
                    # Update the Load Balancer
                    operation = self.network_client.load_balancers.begin_create_or_update(
                        resource_group, lb_name, lb
                    )
                    operation.wait()
                    logger.info(f"Dissociated Public IP from Load Balancer: {lb_name}")
            
            return {
                'success': True,
                'original_configs': original_configs,
                'dissociated_count': len(attached_resources)
            }
            
        except Exception as e:
            logger.error(f"Failed to dissociate resources: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'original_configs': original_configs
            }
    
    async def _upgrade_sku(self, resource_group: str, public_ip_name: str, current_config: PublicIPAddress) -> Dict[str, Any]:
        """Upgrade the Public IP SKU from Basic to Standard."""
        try:
            # Create updated configuration with Standard SKU
            updated_config = PublicIPAddress(
                location=current_config.location,
                sku=PublicIPAddressSku(
                    name=PublicIPAddressSkuName.STANDARD,
                    tier=PublicIPAddressSkuTier.REGIONAL
                ),
                public_ip_allocation_method=current_config.public_ip_allocation_method,
                public_ip_address_version=current_config.public_ip_address_version,
                dns_settings=current_config.dns_settings,
                tags=current_config.tags
            )
            
            # Perform the upgrade
            logger.info(f"Upgrading Public IP SKU: {public_ip_name}")
            operation = self.network_client.public_ip_addresses.begin_create_or_update(
                resource_group_name=resource_group,
                public_ip_address_name=public_ip_name,
                parameters=updated_config
            )
            
            # Wait for completion
            result = operation.wait()
            
            logger.info(f"SKU upgrade completed: {public_ip_name} -> Standard")
            return {
                'success': True,
                'new_sku': 'Standard',
                'resource_id': result.id
            }
            
        except Exception as e:
            logger.error(f"SKU upgrade failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _re_associate_resources(self, resource_group: str, attached_resources: List[Dict[str, Any]], 
                                    original_configs: Dict[str, Any]) -> Dict[str, Any]:
        """Re-associate the upgraded Public IP with its original resources."""
        try:
            success_count = 0
            errors = []
            
            for resource in attached_resources:
                resource_config = original_configs.get(resource['id'])
                if not resource_config:
                    continue
                
                try:
                    if resource_config['type'] == 'NetworkInterface':
                        # Re-associate with Network Interface
                        nic_name = resource_config['name']
                        nic = self.network_client.network_interfaces.get(resource_group, nic_name)
                        
                        # Restore public IP references
                        for i, ip_config in enumerate(nic.ip_configurations or []):
                            original_ip_config = resource_config['ip_configurations'][i]
                            if original_ip_config['had_public_ip']:
                                # Get the upgraded public IP reference
                                public_ip_ref = self.network_client.public_ip_addresses.get(
                                    resource_group, 
                                    original_ip_config['public_ip_id'].split('/')[-1]
                                )
                                ip_config.public_ip_address = public_ip_ref
                        
                        # Update the NIC
                        operation = self.network_client.network_interfaces.begin_create_or_update(
                            resource_group, nic_name, nic
                        )
                        operation.wait()
                        success_count += 1
                        logger.info(f"Re-associated Public IP with Network Interface: {nic_name}")
                    
                    elif resource_config['type'] == 'LoadBalancer':
                        # Re-associate with Load Balancer
                        lb_name = resource_config['name']
                        lb = self.network_client.load_balancers.get(resource_group, lb_name)
                        
                        # Restore public IP references
                        for frontend_config in lb.frontend_ip_configurations or []:
                            for original_frontend in resource_config['frontend_configs']:
                                if (frontend_config.name == original_frontend['name'] and 
                                    original_frontend['had_public_ip']):
                                    # Get the upgraded public IP reference
                                    public_ip_ref = self.network_client.public_ip_addresses.get(
                                        resource_group,
                                        original_frontend['public_ip_id'].split('/')[-1]
                                    )
                                    frontend_config.public_ip_address = public_ip_ref
                        
                        # Update the Load Balancer
                        operation = self.network_client.load_balancers.begin_create_or_update(
                            resource_group, lb_name, lb
                        )
                        operation.wait()
                        success_count += 1
                        logger.info(f"Re-associated Public IP with Load Balancer: {lb_name}")
                        
                except Exception as e:
                    error_msg = f"Failed to re-associate with {resource_config['name']}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            return {
                'success': len(errors) == 0,
                'success_count': success_count,
                'total_resources': len(attached_resources),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Re-association process failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_manual_upgrade_instructions(self, resource_id: str) -> Dict[str, Any]:
        """Provide manual upgrade instructions when automation is not available."""
        resource_name = resource_id.split('/')[-1] if resource_id else "your-public-ip"
        
        return {
            "title": "Public IP Address Upgrade (Basic to Standard SKU)",
            "estimated_time": "5-10 minutes",
            "resource_name": resource_name,
            "prerequisites": [
                "Ensure the Public IP is not currently in use",
                "Verify you have Network Contributor permissions",
                "Consider maintenance window if IP is critical"
            ],
            "steps": [
                {
                    "step": 1,
                    "action": "Navigate to Azure Portal",
                    "details": "Open Azure Portal (portal.azure.com) and search for 'Public IP addresses'"
                },
                {
                    "step": 2,
                    "action": "Locate and select your Public IP",
                    "details": f"Find and click on the Public IP resource: {resource_name}"
                },
                {
                    "step": 3,
                    "action": "Check current associations",
                    "details": "In the Overview tab, note any associated resources (VMs, Load Balancers, etc.)"
                },
                {
                    "step": 4,
                    "action": "Dissociate if needed",
                    "details": "If associated with resources, dissociate them first (will cause temporary downtime)"
                },
                {
                    "step": 5,
                    "action": "Upgrade SKU",
                    "details": "Go to Configuration tab → Change SKU from Basic to Standard → Save"
                },
                {
                    "step": 6,
                    "action": "Re-associate resources",
                    "details": "Re-associate with the original resources to restore connectivity"
                }
            ],
            "warnings": [
                "⚠️  This upgrade will cause temporary downtime while dissociated",
                "⚠️  Standard SKU Public IPs have different pricing",
                "⚠️  Some legacy configurations may not be compatible"
            ],
            "post_upgrade": [
                "Verify connectivity to associated resources",
                "Test any applications that depend on this IP",
                "Update DNS records if the IP address changed"
            ]
        }

# Main execution function for API integration
async def upgrade_public_ip_automated(subscription_id: str, resource_id: str) -> Dict[str, Any]:
    """
    Main function to perform automated Public IP upgrade.
    
    Args:
        subscription_id: Azure subscription ID
        resource_id: Full resource ID of the Public IP to upgrade
        
    Returns:
        Dict containing upgrade results
    """
    agent = PublicIPUpgradeAgent(subscription_id)
    return await agent.upgrade_public_ip(resource_id)

# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_upgrade():
        # Example resource ID - replace with actual values for testing
        subscription_id = "your-subscription-id"
        resource_id = "/subscriptions/your-sub/resourceGroups/your-rg/providers/Microsoft.Network/publicIPAddresses/your-ip"
        
        result = await upgrade_public_ip_automated(subscription_id, resource_id)
        print(json.dumps(result, indent=2))
    
    # Uncomment to test
    # asyncio.run(test_upgrade())
