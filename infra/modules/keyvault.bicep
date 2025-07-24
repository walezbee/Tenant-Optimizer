resource kv 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: 'tenant-optimizer-kv'
  location: resourceGroup().location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    accessPolicies: []
    enabledForDeployment: true
    enabledForTemplateDeployment: true
  }
}

output keyVaultName string = kv.name
