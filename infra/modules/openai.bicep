resource openai 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: 'openai-account'
  location: resourceGroup().location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
    tier: 'Standard'
  }
  properties: {
    apiProperties: {
      enableOpenAI: true
    }
  }
}

output openaiName string = openai.name
