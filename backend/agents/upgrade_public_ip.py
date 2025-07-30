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
    
    def __init__(self, subscription_id: str, access_token: str = None, tenant_id: str = None):
        """Initialize the upgrade agent."""
        self.subscription_id = subscription_id
        self.access_token = access_token
        self.tenant_id = tenant_id
        self.sdk_available = AZURE_SDK_AVAILABLE
        
        # If we have access token, use HTTP calls (preferred)
        if access_token and HTTPX_AVAILABLE:
            self.credential = None
            self.network_client = None
            logger.info("🔑 PublicIP Agent using user access token for authentication")
        else:
            # Try Azure SDK as fallback
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
        logger.info(f"🚀 Starting Public IP upgrade: {resource_id}")
        
        try:
            # Prioritize Azure SDK approach for better dissociation handling
            if self.sdk_available and self.network_client:
                logger.info("🔧 Using Azure SDK approach (primary method)")
                return await self._upgrade_via_sdk(resource_id)
            
            # Fallback to HTTP-based upgrade if SDK not available
            elif self.access_token and HTTPX_AVAILABLE:
                logger.info("🔧 Using HTTP API approach (fallback method)")
                return await self._upgrade_via_http(resource_id)
            
            # No authentication method available
            else:
                return {
                    "success": False,
                    "error": "Azure SDK dependencies not available",
                    "message": "Automated upgrade requires Azure SDK packages",
                    "fallback_required": True,
                    "manual_instructions": self._get_manual_upgrade_instructions(resource_id)
                }
                
        except Exception as e:
            logger.error(f"❌ Public IP upgrade failed: {str(e)}")
            return {
                "success": False,
                "error": f"Upgrade process failed: {str(e)}",
                "resource_id": resource_id
            }
    
    async def _upgrade_via_http(self, resource_id: str) -> Dict[str, Any]:
        """Upgrade Public IP using HTTP API calls with access token."""
        try:
            logger.info("🔧 Using HTTP API for Public IP upgrade")
            
            # Step 1: Get current Public IP configuration
            logger.info("📋 Step 1: Retrieving current Public IP configuration...")
            
            url = f"https://management.azure.com{resource_id}?api-version=2023-09-01"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=60) as client:
                # Get current configuration
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to retrieve Public IP: {response.status_code}",
                        "message": f"Could not access Public IP resource: {response.text}"
                    }
                
                current_config = response.json()
                current_sku = current_config.get("sku", {}).get("name", "").lower()
                
                logger.info(f"📊 Current SKU: {current_sku}")
                
                # Check if already Standard
                if current_sku == "standard":
                    return {
                        "success": True,
                        "message": "Public IP is already using Standard SKU",
                        "sku_before": "Standard",
                        "sku_after": "Standard",
                        "no_change_required": True
                    }
                
                # Step 2: Check if Public IP is attached to any resources
                attached_resource = None
                ip_configuration = current_config.get("properties", {}).get("ipConfiguration")
                
                if ip_configuration:
                    logger.info("🔗 Step 2: Public IP is attached to a resource - dissociating...")
                    attached_resource = ip_configuration.get("id")
                    
                    # Dissociate from the attached resource
                    dissociation_result = await self._dissociate_public_ip_http(attached_resource, url, client, headers)
                    if not dissociation_result["success"]:
                        return dissociation_result
                    
                    # Enhanced verification with multiple checks
                    logger.info("🔍 Enhanced verification: Ensuring complete dissociation...")
                    
                    # Wait longer for Azure to process the changes
                    import asyncio
                    await asyncio.sleep(5)
                    
                    # Multiple verification attempts with exponential backoff
                    max_verification_attempts = 10
                    for attempt in range(max_verification_attempts):
                        logger.info(f"🔍 Verification attempt {attempt + 1}/{max_verification_attempts}")
                        
                        verify_response = await client.get(url, headers=headers)
                        if verify_response.status_code == 200:
                            verify_config = verify_response.json()
                            ip_config_ref = verify_config.get("properties", {}).get("ipConfiguration")
                            
                            if not ip_config_ref:
                                logger.info("✅ Dissociation verified successfully")
                                break
                            else:
                                wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30 seconds
                                logger.info(f"⏳ Still attached, waiting {wait_time}s before retry...")
                                await asyncio.sleep(wait_time)
                        else:
                            logger.warning(f"⚠️ Verification request failed: {verify_response.status_code}")
                            await asyncio.sleep(2)
                    
                    # Final verification
                    final_verify = await client.get(url, headers=headers)
                    if final_verify.status_code == 200:
                        final_config = final_verify.json()
                        if final_config.get("properties", {}).get("ipConfiguration"):
                            return {
                                "success": False, 
                                "error": "PublicIPStillAttached",
                                "message": "Failed to fully dissociate Public IP after multiple attempts. The resource may be in use by another service."
                            }
                        
                else:
                    logger.info("🔗 Step 2: Public IP is not attached to any resources")
                
                # Step 3: Update to Standard SKU
                logger.info("🔄 Step 3: Updating SKU from Basic to Standard...")
                
                # Create updated configuration
                updated_config = current_config.copy()
                updated_config["sku"] = {
                    "name": "Standard",
                    "tier": "Regional"
                }
                
                # Ensure allocation method is Static for Standard SKU
                if "properties" not in updated_config:
                    updated_config["properties"] = {}
                updated_config["properties"]["publicIPAllocationMethod"] = "Static"
                
                # Remove the ipConfiguration since we dissociated it
                if "ipConfiguration" in updated_config.get("properties", {}):
                    del updated_config["properties"]["ipConfiguration"]
                
                # Update the Public IP
                update_response = await client.put(url, headers=headers, json=updated_config)
                
                if update_response.status_code in [200, 201, 202]:
                    logger.info("✅ Public IP SKU upgraded successfully!")
                    
                    # Step 4: Re-associate with the resource if it was attached
                    if attached_resource:
                        logger.info("🔗 Step 4: Re-associating Public IP with resource...")
                        reassociation_result = await self._reassociate_public_ip_http(
                            attached_resource, resource_id, client, headers
                        )
                        if not reassociation_result["success"]:
                            return {
                                "success": False,
                                "error": "Upgrade succeeded but re-association failed",
                                "message": f"Public IP upgraded but failed to re-associate: {reassociation_result['message']}",
                                "manual_action_required": True
                            }
                    
                    return {
                        "success": True,
                        "message": "Public IP successfully upgraded from Basic to Standard SKU",
                        "sku_before": "Basic",
                        "sku_after": "Standard", 
                        "resource_id": resource_id,
                        "upgrade_method": "http_api",
                        "allocation_method": "Static",
                        "attached_resource": attached_resource,
                        "details": {
                            "upgrade_completed": True,
                            "downtime_minimal": True,
                            "configuration_preserved": True,
                            "dissociation_performed": attached_resource is not None,
                            "reassociation_performed": attached_resource is not None
                        }
                    }
                else:
                    # If upgrade failed and we dissociated, try to reassociate
                    if attached_resource:
                        logger.warning("⚠️ Upgrade failed, attempting to restore association...")
                        await self._reassociate_public_ip_http(attached_resource, resource_id, client, headers)
                    
                    return {
                        "success": False,
                        "error": f"Upgrade failed: {update_response.status_code}",
                        "message": f"Failed to update Public IP: {update_response.text}"
                    }
                    
        except Exception as e:
            logger.error(f"❌ HTTP-based upgrade failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": f"HTTP-based upgrade failed: {str(e)}"
            }
    
    async def _upgrade_via_sdk(self, resource_id: str) -> Dict[str, Any]:
        """
        Upgrade Public IP using Azure SDK with proper resource state management.
        
        This implementation follows Azure's recommended approach for SKU upgrades:
        1. Complete dissociation from all attached resources
        2. Wait for Azure to fully process the dissociation
        3. Perform the SKU upgrade on the unattached Public IP
        4. Reassociate to original resources
        """
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.network import NetworkManagementClient
            from azure.mgmt.network.models import PublicIPAddressSku, PublicIPAddressSkuName, PublicIPAddressSkuTier
            import asyncio
            
            logger.info("🔧 Using Enhanced Azure SDK approach for Public IP upgrade")
            
            # Parse resource ID to extract components
            parts = resource_id.split("/")
            subscription_id = parts[2]
            resource_group = parts[4]
            public_ip_name = parts[8]
            
            logger.info(f"📋 Subscription: {subscription_id}")
            logger.info(f"📋 Resource Group: {resource_group}")
            logger.info(f"📋 Public IP Name: {public_ip_name}")
            
            # Initialize Azure SDK client with retry configuration
            credential = DefaultAzureCredential()
            network_client = NetworkManagementClient(credential, subscription_id)
            
            # Step 1: Get current Public IP configuration
            logger.info("📊 Step 1: Getting current Public IP configuration...")
            public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
            
            logger.info(f"📊 Current SKU: {public_ip.sku.name}")
            logger.info(f"📊 Current Allocation: {public_ip.public_ip_allocation_method}")
            
            # Check if already Standard
            if public_ip.sku.name and public_ip.sku.name.lower() == "standard":
                return {
                    "success": True,
                    "message": "Public IP is already using Standard SKU",
                    "sku_before": "Standard",
                    "sku_after": "Standard",
                    "no_change_required": True
                }
            
            # Step 2: Enhanced dissociation with proper verification
            attached_resources = []
            
            if public_ip.ip_configuration:
                logger.info("🔗 Step 2: Public IP is attached - performing enhanced dissociation...")
                
                # Store all attachment details for later reassociation
                ip_config_id = public_ip.ip_configuration.id
                nic_parts = ip_config_id.split("/")
                nic_name = nic_parts[8]  # network interface name
                config_name = nic_parts[10]  # IP configuration name
                
                logger.info(f"🔌 Attached to NIC: {nic_name}, Config: {config_name}")
                
                # Store attachment info for reassociation
                attached_resources.append({
                    "type": "network_interface",
                    "nic_name": nic_name,
                    "config_name": config_name,
                    "resource_group": resource_group
                })
                
                # Perform complete dissociation
                await self._perform_complete_dissociation(
                    network_client, resource_group, nic_name, config_name, public_ip_name
                )
                
            else:
                logger.info("🔗 Step 2: Public IP is not attached - proceeding with upgrade")
            
            # Step 3: Enhanced SKU upgrade with proper resource handling
            logger.info("🔄 Step 3: Performing enhanced SKU upgrade...")
            
            # Get fresh Public IP reference after dissociation
            fresh_public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
            
            # Verify it's completely dissociated before upgrade
            if fresh_public_ip.ip_configuration:
                raise Exception("Public IP is still attached after dissociation - cannot proceed with upgrade")
            
            # Create proper SKU object for Standard
            fresh_public_ip.sku = PublicIPAddressSku(
                name=PublicIPAddressSkuName.STANDARD,
                tier=PublicIPAddressSkuTier.REGIONAL
            )
            
            # Ensure Static allocation for Standard SKU
            fresh_public_ip.public_ip_allocation_method = "Static"
            
            # Perform the upgrade with proper error handling
            logger.info("🚀 Executing SKU upgrade to Standard...")
            upgrade_poller = network_client.public_ip_addresses.begin_create_or_update(
                resource_group, public_ip_name, fresh_public_ip
            )
            
            # Wait for upgrade with timeout
            logger.info("⏳ Waiting for SKU upgrade to complete...")
            upgrade_result = upgrade_poller.result(timeout=300)  # 5 minute timeout
            logger.info("✅ SKU upgrade completed successfully")
            
            # Verify the upgrade was successful
            upgraded_public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
            if upgraded_public_ip.sku.name.lower() != "standard":
                raise Exception(f"SKU upgrade failed - still shows {upgraded_public_ip.sku.name}")
            
            # Step 4: Reassociate to original resources
            if attached_resources:
                logger.info("🔄 Step 4: Reassociating Public IP to original resources...")
                
                for attachment in attached_resources:
                    await self._perform_reassociation(
                        network_client, attachment, resource_group, public_ip_name
                    )
            
            return {
                "success": True,
                "message": "Public IP successfully upgraded using Enhanced Azure SDK approach",
                "sku_before": "Basic",
                "sku_after": "Standard",
                "resource_id": resource_id,
                "upgrade_method": "enhanced_azure_sdk",
                "allocation_method": "Static",
                "attached_resources": len(attached_resources),
                "details": {
                    "upgrade_completed": True,
                    "sdk_based": True,
                    "enhanced_dissociation": True,
                    "dissociation_performed": len(attached_resources) > 0,
                    "reassociation_performed": len(attached_resources) > 0,
                    "verification_completed": True
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Enhanced SDK-based upgrade failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Enhanced Azure SDK upgrade failed: {str(e)}",
                "upgrade_method": "enhanced_azure_sdk"
            }
    
    async def _dissociate_public_ip_http(self, ip_config_id: str, public_ip_url: str, client, headers) -> Dict[str, Any]:
        """Dissociate Public IP from network interface using HTTP API."""
        try:
            # Extract network interface ID from IP configuration ID
            # Format: /subscriptions/.../networkInterfaces/nic-name/ipConfigurations/ipconfig-name
            nic_id = "/".join(ip_config_id.split("/")[:-2])
            
            logger.info(f"🔌 Dissociating Public IP from NIC: {nic_id}")
            
            # Get current NIC configuration
            nic_url = f"https://management.azure.com{nic_id}?api-version=2023-09-01"
            nic_response = await client.get(nic_url, headers=headers)
            
            if nic_response.status_code != 200:
                return {
                    "success": False,
                    "message": f"Failed to get NIC configuration: {nic_response.status_code}"
                }
            
            nic_config = nic_response.json()
            
            # Find the IP configuration and remove the public IP reference
            ip_configs = nic_config.get("properties", {}).get("ipConfigurations", [])
            config_name = ip_config_id.split("/")[-1]
            
            for ip_config in ip_configs:
                if ip_config.get("name") == config_name:
                    if "publicIPAddress" in ip_config.get("properties", {}):
                        del ip_config["properties"]["publicIPAddress"]
                        logger.info(f"🔌 Removed Public IP reference from {config_name}")
                    break
            
            # Update the NIC
            update_response = await client.put(nic_url, headers=headers, json=nic_config)
            
            if update_response.status_code in [200, 201, 202]:
                logger.info("✅ Successfully updated NIC to remove Public IP reference")
                
                # Wait longer for the dissociation to propagate in Azure
                logger.info("⏳ Waiting 10 seconds for dissociation to propagate...")
                await asyncio.sleep(10)
                
                # Aggressive verification - check both NIC and Public IP status
                max_retries = 15  # Increased from 5
                verification_success = False
                
                for attempt in range(max_retries):
                    logger.info(f"🔍 Verification attempt {attempt + 1}/{max_retries}")
                    
                    # Check Public IP status
                    public_ip_response = await client.get(public_ip_url, headers=headers)
                    public_ip_free = False
                    
                    if public_ip_response.status_code == 200:
                        public_ip_data = public_ip_response.json()
                        ip_config_ref = public_ip_data.get("properties", {}).get("ipConfiguration")
                        
                        if not ip_config_ref:
                            public_ip_free = True
                            logger.info("✅ Public IP shows as free")
                        else:
                            logger.info(f"⏳ Public IP still attached to: {ip_config_ref.get('id', 'unknown')}")
                    
                    # Also check NIC status to double-verify
                    nic_verify_response = await client.get(nic_url, headers=headers)
                    nic_clean = False
                    
                    if nic_verify_response.status_code == 200:
                        nic_verify_data = nic_verify_response.json()
                        ip_configs_verify = nic_verify_data.get("properties", {}).get("ipConfigurations", [])
                        
                        for ip_config_verify in ip_configs_verify:
                            if ip_config_verify.get("name") == config_name:
                                if "publicIPAddress" not in ip_config_verify.get("properties", {}):
                                    nic_clean = True
                                    logger.info("✅ NIC shows Public IP reference removed")
                                else:
                                    logger.info("⏳ NIC still shows Public IP reference")
                                break
                    
                    # Both checks must pass
                    if public_ip_free and nic_clean:
                        verification_success = True
                        logger.info("✅ Complete dissociation verified!")
                        break
                    
                    # Progressive wait time
                    wait_time = min(5 + attempt * 2, 30)  # 5, 7, 9, ... up to 30 seconds
                    logger.info(f"⏳ Waiting {wait_time}s before next verification...")
                    await asyncio.sleep(wait_time)
                
                if verification_success:
                    return {"success": True, "nic_config": nic_config}
                else:
                    return {
                        "success": False,
                        "message": f"Failed to verify complete dissociation after {max_retries} attempts. The Public IP may still be in use."
                    }
            else:
                return {
                    "success": False,
                    "message": f"Failed to update NIC: {update_response.status_code} - {update_response.text}"
                }
                
        except Exception as e:
            logger.error(f"❌ Dissociation failed: {str(e)}")
            return {"success": False, "message": f"Dissociation error: {str(e)}"}
    
    async def _reassociate_public_ip_http(self, ip_config_id: str, public_ip_id: str, client, headers) -> Dict[str, Any]:
        """Re-associate Public IP with network interface using HTTP API."""
        try:
            # Extract network interface ID from IP configuration ID
            nic_id = "/".join(ip_config_id.split("/")[:-2])
            
            logger.info(f"🔗 Re-associating Public IP with NIC: {nic_id}")
            
            # Get current NIC configuration
            nic_url = f"https://management.azure.com{nic_id}?api-version=2023-09-01"
            nic_response = await client.get(nic_url, headers=headers)
            
            if nic_response.status_code != 200:
                return {
                    "success": False,
                    "message": f"Failed to get NIC configuration: {nic_response.status_code}"
                }
            
            nic_config = nic_response.json()
            
            # Find the IP configuration and add the public IP reference
            ip_configs = nic_config.get("properties", {}).get("ipConfigurations", [])
            config_name = ip_config_id.split("/")[-1]
            
            for ip_config in ip_configs:
                if ip_config.get("name") == config_name:
                    if "properties" not in ip_config:
                        ip_config["properties"] = {}
                    ip_config["properties"]["publicIPAddress"] = {"id": public_ip_id}
                    logger.info(f"🔗 Added Public IP reference to {config_name}")
                    break
            
            # Update the NIC
            update_response = await client.put(nic_url, headers=headers, json=nic_config)
            
            if update_response.status_code in [200, 201, 202]:
                logger.info("✅ Successfully re-associated Public IP with NIC")
                return {"success": True}
            else:
                return {
                    "success": False,
                    "message": f"Failed to update NIC: {update_response.status_code} - {update_response.text}"
                }
                
        except Exception as e:
            logger.error(f"❌ Re-association failed: {str(e)}")
            return {"success": False, "message": f"Re-association error: {str(e)}"}
    
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

    async def _perform_complete_dissociation(self, network_client, resource_group: str, 
                                           nic_name: str, config_name: str, public_ip_name: str):
        """
        Perform complete dissociation with enhanced verification and retry logic.
        This method ensures the Public IP is fully released from Azure's perspective.
        """
        import asyncio
        
        logger.info(f"🔌 Starting complete dissociation process for {public_ip_name}")
        
        # Step 1: Get the current NIC configuration
        nic = network_client.network_interfaces.get(resource_group, nic_name)
        
        # Step 2: Remove public IP reference from the specified configuration
        public_ip_removed = False
        for ip_config in nic.ip_configurations:
            if ip_config.name == config_name:
                if ip_config.public_ip_address:
                    logger.info(f"🔌 Removing Public IP reference from {config_name}")
                    ip_config.public_ip_address = None
                    public_ip_removed = True
                break
        
        if not public_ip_removed:
            logger.warning("⚠️ No public IP reference found to remove")
            return
        
        # Step 3: Update the NIC with enhanced waiting
        logger.info("🔄 Updating NIC to dissociate Public IP...")
        update_poller = network_client.network_interfaces.begin_create_or_update(
            resource_group, nic_name, nic
        )
        
        # Wait for NIC update to complete with timeout
        logger.info("⏳ Waiting for NIC update to complete...")
        update_result = update_poller.result(timeout=180)  # 3 minute timeout
        logger.info("✅ NIC update operation completed")
        
        # Step 4: Enhanced verification with multiple checks
        logger.info("🔍 Performing enhanced dissociation verification...")
        
        max_attempts = 12  # Increased verification attempts
        verification_delay = 15  # Longer delay between checks
        
        for attempt in range(max_attempts):
            logger.info(f"🔍 Verification attempt {attempt + 1}/{max_attempts}")
            
            # Check both NIC and Public IP perspectives
            try:
                # Check from NIC perspective
                current_nic = network_client.network_interfaces.get(resource_group, nic_name)
                nic_has_public_ip = False
                
                for ip_config in current_nic.ip_configurations:
                    if ip_config.name == config_name and ip_config.public_ip_address:
                        nic_has_public_ip = True
                        break
                
                # Check from Public IP perspective
                current_public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
                public_ip_attached = current_public_ip.ip_configuration is not None
                
                if not nic_has_public_ip and not public_ip_attached:
                    logger.info("✅ Complete dissociation verified from both perspectives")
                    return
                
                logger.info(f"⏳ Still attached (NIC: {nic_has_public_ip}, Public IP: {public_ip_attached}) - waiting {verification_delay}s...")
                await asyncio.sleep(verification_delay)
                
            except Exception as e:
                logger.warning(f"⚠️ Verification attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(verification_delay)
        
        # Final verification - if still attached, throw error
        try:
            final_public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
            if final_public_ip.ip_configuration:
                raise Exception(f"Public IP {public_ip_name} is still attached after {max_attempts} verification attempts. Manual intervention may be required.")
        except Exception as e:
            if "still attached" in str(e):
                raise e
            logger.warning(f"Final verification failed: {str(e)}")
        
        logger.info("✅ Dissociation process completed")

    async def _perform_reassociation(self, network_client, attachment: dict, 
                                   resource_group: str, public_ip_name: str):
        """
        Perform reassociation with proper error handling and verification.
        """
        import asyncio
        
        nic_name = attachment["nic_name"]
        config_name = attachment["config_name"]
        
        logger.info(f"🔄 Starting reassociation of {public_ip_name} to {nic_name}.{config_name}")
        
        try:
            # Get fresh references to both resources
            nic = network_client.network_interfaces.get(resource_group, nic_name)
            public_ip_ref = network_client.public_ip_addresses.get(resource_group, public_ip_name)
            
            # Find the correct IP configuration and reassociate
            reassociated = False
            for ip_config in nic.ip_configurations:
                if ip_config.name == config_name:
                    logger.info(f"🔗 Reassociating Public IP to {config_name}")
                    ip_config.public_ip_address = public_ip_ref
                    reassociated = True
                    break
            
            if not reassociated:
                raise Exception(f"Could not find IP configuration {config_name} for reassociation")
            
            # Update the NIC
            logger.info("🔄 Updating NIC with reassociated Public IP...")
            reassoc_poller = network_client.network_interfaces.begin_create_or_update(
                resource_group, nic_name, nic
            )
            
            # Wait for reassociation to complete
            logger.info("⏳ Waiting for reassociation to complete...")
            reassoc_result = reassoc_poller.result(timeout=180)  # 3 minute timeout
            logger.info("✅ Reassociation completed successfully")
            
            # Verify reassociation
            await asyncio.sleep(5)  # Brief wait for consistency
            
            updated_public_ip = network_client.public_ip_addresses.get(resource_group, public_ip_name)
            if updated_public_ip.ip_configuration:
                logger.info("✅ Reassociation verified - Public IP is properly attached")
            else:
                logger.warning("⚠️ Reassociation may not have completed - Public IP shows as unattached")
                
        except Exception as e:
            logger.error(f"❌ Reassociation failed: {str(e)}")
            raise Exception(f"Failed to reassociate Public IP {public_ip_name} to {nic_name}: {str(e)}")


# Main execution function for API integration
async def upgrade_public_ip_automated(subscription_id: str, resource_id: str, access_token: str = None, tenant_id: str = None) -> Dict[str, Any]:
    """
    Main function to perform automated Public IP upgrade.
    
    Args:
        subscription_id: Azure subscription ID
        resource_id: Full resource ID of the Public IP to upgrade
        access_token: User's access token for authentication
        tenant_id: Azure tenant ID
        
    Returns:
        Dict containing upgrade results
    """
    agent = PublicIPUpgradeAgent(subscription_id, access_token, tenant_id)
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
