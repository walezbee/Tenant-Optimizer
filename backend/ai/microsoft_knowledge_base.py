"""
Microsoft Official Knowledge Base for Azure Resource Deprecation and Orphaned Resources
Based on official Microsoft Learn documentation and Azure product lifecycle announcements
Last Updated: July 30, 2025
"""

from datetime import datetime
from typing import Dict, List, Any

class MicrosoftKnowledgeBase:
    """
    Official Microsoft Knowledge Base for Azure deprecated and orphaned resources.
    Based on Microsoft Learn documentation and official retirement announcements.
    """
    
    def __init__(self):
        self.last_updated = "2025-07-30"
        self.source = "Microsoft Learn - Official Documentation"
        
    def get_deprecated_resources_patterns(self) -> Dict[str, Any]:
        """
        Returns comprehensive patterns for deprecated Azure resources based on 
        Microsoft's official retirement schedule and lifecycle policies.
        
        Source: https://learn.microsoft.com/en-us/lifecycle/end-of-support/
        """
        return {
            "retiring_september_2025": {
                "retirement_date": "2025-09-30",
                "official_announcement": "https://azure.microsoft.com/updates",
                "patterns": {
                    "public_ip_basic": {
                        "resource_types": ["microsoft.network/publicipaddresses"],
                        "detection_rules": [
                            {"property": "properties.sku.name", "values": ["Basic"], "match_type": "exact"},
                            {"property": "properties.sku.tier", "values": ["Basic"], "match_type": "exact"},
                            {"property": "sku.name", "values": ["Basic"], "match_type": "exact"},
                            {"property": "sku.tier", "values": ["Basic"], "match_type": "exact"}
                        ],
                        "description": "Basic SKU Public IP Addresses will be retired September 30, 2025",
                        "impact": "High - No new Basic Public IPs can be created after March 31, 2025",
                        "recommendation": "Upgrade to Standard SKU Public IP for better performance and availability"
                    },
                    "load_balancer_basic": {
                        "resource_types": ["microsoft.network/loadbalancers"],
                        "detection_rules": [
                            {"property": "properties.sku.name", "values": ["Basic"], "match_type": "exact"},
                            {"property": "properties.sku.tier", "values": ["Basic"], "match_type": "exact"},
                            {"property": "sku.name", "values": ["Basic"], "match_type": "exact"},
                            {"property": "sku.tier", "values": ["Basic"], "match_type": "exact"}
                        ],
                        "description": "Basic SKU Load Balancers will be retired September 30, 2025",
                        "impact": "High - No new Basic Load Balancers can be created after March 31, 2025",
                        "recommendation": "Upgrade to Standard SKU Load Balancer for improved features and SLA"
                    },
                    "unmanaged_disks": {
                        "resource_types": ["microsoft.compute/disks"],
                        "detection_rules": [
                            {"property": "properties.diskProperties.diskType", "values": ["Unmanaged"], "match_type": "exact"},
                            {"property": "type", "values": ["Microsoft.ClassicCompute/virtualMachines/disks"], "match_type": "exact"}
                        ],
                        "description": "Azure Unmanaged Disks will be retired September 30, 2025",
                        "impact": "High - Migration to Managed Disks required",
                        "recommendation": "Migrate to Azure Managed Disks for better reliability and management"
                    }
                }
            },
            "storage_optimization": {
                "patterns": {
                    "standard_lrs": {
                        "resource_types": ["microsoft.storage/storageaccounts"],
                        "detection_rules": [
                            {"property": "properties.sku.name", "values": ["Standard_LRS"], "match_type": "exact"},
                            {"property": "sku.name", "values": ["Standard_LRS"], "match_type": "exact"}
                        ],
                        "description": "Standard_LRS provides limited redundancy",
                        "impact": "Medium - Single datacenter failure risk",
                        "recommendation": "Consider upgrading to GRS or ZRS for better data durability"
                    },
                    "archive_tier": {
                        "resource_types": ["microsoft.storage/storageaccounts"],
                        "detection_rules": [
                            {"property": "properties.accessTier", "values": ["Archive"], "match_type": "exact"}
                        ],
                        "description": "Archive tier has high access costs and long retrieval times",
                        "impact": "Medium - Review access patterns for cost optimization",
                        "recommendation": "Review access patterns and consider Hot/Cool tiers for frequently accessed data"
                    }
                }
            },
            "vm_optimization": {
                "patterns": {
                    "a_series_deprecated": {
                        "resource_types": ["microsoft.compute/virtualmachines"],
                        "detection_rules": [
                            {"property": "properties.hardwareProfile.vmSize", "values": ["Standard_A1", "Standard_A2", "Standard_A3", "Standard_A4"], "match_type": "exact"},
                            {"property": "properties.hardwareProfile.vmSize", "values": ["Standard_A"], "match_type": "starts_with"},
                            {"property": "properties.hardwareProfile.vmSize", "values": ["Basic_A"], "match_type": "starts_with"}
                        ],
                        "description": "A-Series VMs are older generation with limited performance",
                        "impact": "Medium - Performance and cost optimization opportunity",
                        "recommendation": "Upgrade to newer generation VM sizes (D, E, F series) for better performance and cost efficiency"
                    }
                }
            }
        }
    
    def get_orphaned_resources_patterns(self) -> Dict[str, Any]:
        """
        Returns comprehensive patterns for orphaned Azure resources based on 
        Microsoft's cost optimization recommendations and best practices.
        
        Source: https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-component-costs
        """
        return {
            "compute_orphaned": {
                "unattached_disks": {
                    "resource_types": ["microsoft.compute/disks"],
                    "detection_rules": [
                        {"property": "properties.managedBy", "condition": "is_null_or_empty"},
                        {"property": "properties.diskState", "values": ["Unattached"], "match_type": "exact"}
                    ],
                    "description": "Managed disks not attached to any VM",
                    "cost_impact": "Medium - Ongoing storage costs without benefit",
                    "recommendation": "Evaluate if disk is still needed. Create snapshot before deletion if data recovery might be needed."
                },
                "orphaned_snapshots": {
                    "resource_types": ["microsoft.compute/snapshots"],
                    "detection_rules": [
                        {"property": "properties.creationData.sourceResourceId", "condition": "source_not_exists"}
                    ],
                    "description": "Snapshots whose source disks no longer exist",
                    "cost_impact": "Low-Medium - Ongoing storage costs",
                    "recommendation": "Review snapshots and delete those no longer needed for backup or recovery"
                }
            },
            "network_orphaned": {
                "unassociated_public_ips": {
                    "resource_types": ["microsoft.network/publicipaddresses"],
                    "detection_rules": [
                        {"property": "properties.ipConfiguration", "condition": "is_null_or_empty"},
                        {"property": "properties.publicIPAllocationMethod", "values": ["Static"], "match_type": "exact"}
                    ],
                    "description": "Public IP addresses not associated with any resource",
                    "cost_impact": "Low - Static IPs incur charges when unused",
                    "recommendation": "Delete unused public IPs or associate with resources that need them"
                },
                "unused_network_interfaces": {
                    "resource_types": ["microsoft.network/networkinterfaces"],
                    "detection_rules": [
                        {"property": "properties.virtualMachine", "condition": "is_null_or_empty"}
                    ],
                    "description": "Network interfaces not attached to any VM",
                    "cost_impact": "Very Low - Minimal ongoing cost",
                    "recommendation": "Clean up unused network interfaces to reduce management overhead"
                },
                "orphaned_network_security_groups": {
                    "resource_types": ["microsoft.network/networksecuritygroups"],
                    "detection_rules": [
                        {"property": "properties.subnets", "condition": "is_empty_array"},
                        {"property": "properties.networkInterfaces", "condition": "is_empty_array"}
                    ],
                    "description": "Network Security Groups not associated with any subnet or network interface",
                    "cost_impact": "None - But adds management complexity",
                    "recommendation": "Remove unused NSGs to simplify network security management"
                }
            },
            "storage_orphaned": {
                "empty_storage_accounts": {
                    "resource_types": ["microsoft.storage/storageaccounts"],
                    "detection_rules": [
                        {"property": "properties.primaryEndpoints", "condition": "check_empty_containers"}
                    ],
                    "description": "Storage accounts with no data or minimal usage",
                    "cost_impact": "Low-Medium - Base storage account charges",
                    "recommendation": "Review storage account usage and consolidate or delete unused accounts"
                },
                "old_storage_blobs": {
                    "resource_types": ["microsoft.storage/storageaccounts/blobservices/containers/blobs"],
                    "detection_rules": [
                        {"property": "properties.lastModified", "condition": "older_than_days", "value": 365},
                        {"property": "properties.accessTier", "values": ["Archive"], "match_type": "exact"}
                    ],
                    "description": "Blobs not accessed for extended periods",
                    "cost_impact": "Variable - Depends on size and tier",
                    "recommendation": "Implement lifecycle management policies to automatically tier or delete old data"
                }
            }
        }
    
    def get_kql_queries(self) -> Dict[str, str]:
        """
        Returns optimized KQL queries for detecting deprecated and orphaned resources
        based on Microsoft's Resource Graph best practices.
        """
        return {
            "deprecated_comprehensive": """
                Resources
                | where type in (
                    "microsoft.network/publicipaddresses",
                    "microsoft.network/loadbalancers",
                    "microsoft.storage/storageaccounts",
                    "microsoft.compute/virtualmachines",
                    "microsoft.compute/disks"
                )
                | extend skuName = case(
                    isnotnull(properties.sku.name), tostring(properties.sku.name),
                    isnotnull(properties.sku), tostring(properties.sku),
                    isnotnull(sku.name), tostring(sku.name),
                    isnotnull(sku), tostring(sku),
                    ""
                )
                | extend skuTier = case(
                    isnotnull(properties.sku.tier), tostring(properties.sku.tier),
                    isnotnull(sku.tier), tostring(sku.tier),
                    ""
                )
                | extend vmSize = case(
                    isnotnull(properties.hardwareProfile.vmSize), tostring(properties.hardwareProfile.vmSize),
                    ""
                )
                | extend accessTier = case(
                    isnotnull(properties.accessTier), tostring(properties.accessTier),
                    ""
                )
                | extend diskType = case(
                    isnotnull(properties.diskProperties.diskType), tostring(properties.diskProperties.diskType),
                    ""
                )
                | where (
                    // Basic SKU Public IPs and Load Balancers (retiring Sept 30, 2025)
                    (type in ("microsoft.network/publicipaddresses", "microsoft.network/loadbalancers") and (skuName =~ "Basic" or skuTier =~ "Basic"))
                    or
                    // Standard_LRS Storage (optimization opportunity)
                    (type == "microsoft.storage/storageaccounts" and skuName =~ "Standard_LRS")
                    or
                    // Archive tier Storage (review needed)
                    (type == "microsoft.storage/storageaccounts" and accessTier =~ "Archive")
                    or
                    // A-Series VMs (older generation)
                    (type == "microsoft.compute/virtualmachines" and (vmSize contains "Standard_A" or vmSize contains "Basic_A"))
                    or
                    // Unmanaged disks (retiring Sept 30, 2025)
                    (type == "microsoft.compute/disks" and diskType =~ "Unmanaged")
                )
                | project id, name, resourceGroup, location, type, subscriptionId, skuName, skuTier, vmSize, accessTier, diskType, properties
                | limit 100
            """,
            
            "orphaned_comprehensive": """
                Resources
                | where type in (
                    "microsoft.compute/disks",
                    "microsoft.compute/snapshots",
                    "microsoft.network/publicipaddresses",
                    "microsoft.network/networkinterfaces",
                    "microsoft.network/networksecuritygroups"
                )
                | extend isOrphaned = case(
                    // Unattached managed disks
                    type == "microsoft.compute/disks" and (isnull(properties.managedBy) or properties.managedBy == ""),
                    true,
                    // Unassociated public IPs
                    type == "microsoft.network/publicipaddresses" and (isnull(properties.ipConfiguration) or properties.ipConfiguration == ""),
                    true,
                    // Unused network interfaces
                    type == "microsoft.network/networkinterfaces" and (isnull(properties.virtualMachine) or properties.virtualMachine == ""),
                    true,
                    // Orphaned NSGs
                    type == "microsoft.network/networksecuritygroups" and array_length(properties.subnets) == 0 and array_length(properties.networkInterfaces) == 0,
                    true,
                    // Orphaned snapshots (basic check)
                    type == "microsoft.compute/snapshots",
                    true,
                    false
                )
                | where isOrphaned == true
                | extend diskSizeGB = case(
                    type == "microsoft.compute/disks", toint(properties.diskSizeGB),
                    0
                )
                | extend costEstimate = case(
                    type == "microsoft.compute/disks", diskSizeGB * 0.05,
                    type == "microsoft.network/publicipaddresses" and properties.publicIPAllocationMethod == "Static", 3.65,
                    0.0
                )
                | project id, name, resourceGroup, location, type, subscriptionId, diskSizeGB, costEstimate, properties
                | limit 100
            """
        }
    
    def get_upgrade_guidance(self, resource_type: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns specific upgrade guidance based on Microsoft's official migration documentation.
        """
        guidance_map = {
            "microsoft.network/publicipaddresses": {
                "title": "Upgrade Basic to Standard SKU Public IP",
                "urgency": "High - Retirement September 30, 2025",
                "steps": [
                    "Review associated resources (VMs, Load Balancers, etc.)",
                    "Plan maintenance window as upgrade causes temporary downtime",
                    "Dissociate Public IP from associated resources",
                    "Change SKU from Basic to Standard in Azure Portal",
                    "Re-associate with original resources",
                    "Test connectivity and update any automation"
                ],
                "considerations": [
                    "Standard SKU has different pricing model",
                    "Standard SKU provides better SLA and features",
                    "Static allocation becomes default for Standard SKU"
                ],
                "documentation": "https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/public-ip-basic-upgrade-guidance"
            },
            "microsoft.network/loadbalancers": {
                "title": "Upgrade Basic to Standard SKU Load Balancer",
                "urgency": "High - Retirement September 30, 2025",
                "steps": [
                    "Document current configuration and backend pools",
                    "Plan maintenance window",
                    "Create new Standard Load Balancer",
                    "Migrate backend pool members",
                    "Update health probes and load balancing rules",
                    "Test functionality before decommissioning Basic LB"
                ],
                "considerations": [
                    "Standard Load Balancer supports availability zones",
                    "Different pricing model and enhanced features",
                    "May require Standard SKU Public IPs"
                ],
                "documentation": "https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-basic-upgrade-guidance"
            },
            "microsoft.storage/storageaccounts": {
                "title": "Optimize Storage Account Configuration",
                "urgency": "Medium - Cost and durability optimization",
                "steps": [
                    "Analyze access patterns and performance requirements",
                    "Evaluate replication needs for your data",
                    "Plan replication type change during maintenance window",
                    "Update storage account replication type",
                    "Monitor performance and costs after change"
                ],
                "considerations": [
                    "GRS provides geo-redundancy across regions",
                    "ZRS provides zone redundancy within region",
                    "Consider read-access versions (RA-GRS, RA-GZRS) if needed"
                ],
                "documentation": "https://learn.microsoft.com/en-us/azure/storage/common/storage-redundancy"
            }
        }
        
        return guidance_map.get(resource_type, {
            "title": "Review Resource Configuration",
            "urgency": "Medium",
            "steps": ["Review current configuration", "Consult Azure documentation", "Plan optimization"],
            "considerations": ["Follow Microsoft best practices"],
            "documentation": "https://learn.microsoft.com/en-us/azure/"
        })
    
    def get_cost_impact_analysis(self, resource_type: str, resource_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provides cost impact analysis based on Microsoft's pricing documentation.
        """
        cost_analysis = {
            "microsoft.compute/disks": {
                "calculation_method": "disk_size_gb * storage_cost_per_gb_per_month",
                "typical_monthly_cost": "disk_size_gb * 0.05",
                "optimization_potential": "100% savings if deleted",
                "considerations": "Create snapshot before deletion for data recovery"
            },
            "microsoft.network/publicipaddresses": {
                "calculation_method": "static_ip_reservation_cost",
                "typical_monthly_cost": "3.65 USD for static IPs",
                "optimization_potential": "100% savings if deleted or changed to dynamic",
                "considerations": "Dynamic IPs change when resource is deallocated"
            },
            "microsoft.storage/storageaccounts": {
                "calculation_method": "storage_capacity + transactions + data_transfer",
                "typical_monthly_cost": "varies by tier and usage",
                "optimization_potential": "20-60% with proper tier optimization",
                "considerations": "Access patterns determine optimal tier"
            }
        }
        
        return cost_analysis.get(resource_type, {
            "calculation_method": "varies by resource",
            "typical_monthly_cost": "varies",
            "optimization_potential": "varies",
            "considerations": "Review Azure pricing calculator"
        })
