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

// Grant the App Service Managed Identity permissions to manage Azure resources
resource contributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(webapp.id, 'b24988ac-6180-42a0-ab88-20f7382dd24c', resourceGroup().id)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c') // Contributor role
    principalId: webapp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output webAppName string = webapp.name
output managedIdentityPrincipalId string = webapp.identity.principalId
