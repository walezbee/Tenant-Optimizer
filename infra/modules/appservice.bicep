param keyVaultName string

resource plan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: 'tenant-optimizer-plan'
  location: resourceGroup().location
  sku: {
    name: 'P1v2'
    tier: 'PremiumV2'
    capacity: 1
  }
  properties: {
    reserved: true // Required for Linux App Service Plans
  }
}

resource webapp 'Microsoft.Web/sites@2022-03-01' = {
  name: 'tenant-optimizer-web'
  location: resourceGroup().location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'KEYVAULT_NAME'
          value: keyVaultName
        }
      ]
    }
    httpsOnly: true
  }
}

output webAppName string = webapp.name
output managedIdentityPrincipalId string = webapp.identity.principalId
