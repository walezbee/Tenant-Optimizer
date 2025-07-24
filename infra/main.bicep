@description('The name of the existing resource group where resources will be deployed.')
param resourceGroupName string

@description('The Azure region where the resource group is located.')
param location string

@description('Name of the application.')
param appName string

@description('Administrator email for the application.')
param adminEmail string



module openai 'modules/openai.bicep' = {
  name: 'openai'
  scope: resourceGroup(resourceGroupName)
  params: {
  }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  scope: resourceGroup(resourceGroupName)
  params: {
    location: location
  }
}

module keyvault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  scope: resourceGroup(resourceGroupName)
  params: {}
}

module appservice 'modules/appservice.bicep' = {
  name: 'appservice'
  scope: resourceGroup(resourceGroupName)
  params: {
    keyVaultName: keyvault.outputs.keyVaultName
  }
}
