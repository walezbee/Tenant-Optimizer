# Deploy Infrastructure with Managed Identity for Automated Upgrade Agents
# This script deploys the updated Bicep template with Managed Identity and RBAC permissions

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroupName,
    
    [Parameter(Mandatory=$true)]
    [string]$Location = "West Europe"
)

Write-Host "🚀 Deploying Tenant Optimizer Infrastructure with Automated Upgrade Agents Support" -ForegroundColor Green
Write-Host "📍 Resource Group: $ResourceGroupName" -ForegroundColor Cyan
Write-Host "🌍 Location: $Location" -ForegroundColor Cyan

# Check if Azure CLI is logged in
try {
    $account = az account show --query "name" -o tsv 2>$null
    if (-not $account) {
        throw "Not logged in"
    }
    Write-Host "✅ Logged in to Azure as: $account" -ForegroundColor Green
} catch {
    Write-Host "❌ Please log in to Azure CLI first: az login" -ForegroundColor Red
    exit 1
}

# Check if resource group exists
$rgExists = az group exists --name $ResourceGroupName
if ($rgExists -eq "false") {
    Write-Host "📦 Creating resource group: $ResourceGroupName" -ForegroundColor Yellow
    az group create --name $ResourceGroupName --location $Location
} else {
    Write-Host "✅ Resource group exists: $ResourceGroupName" -ForegroundColor Green
}

# Deploy the main Bicep template
Write-Host "🔧 Deploying infrastructure..." -ForegroundColor Yellow

$deploymentResult = az deployment group create `
    --resource-group $ResourceGroupName `
    --template-file "infra/main.bicep" `
    --parameters resourceGroupName=$ResourceGroupName location=$Location `
    --query "properties.provisioningState" -o tsv

if ($deploymentResult -eq "Succeeded") {
    Write-Host "✅ Infrastructure deployment completed successfully!" -ForegroundColor Green
    Write-Host "🤖 Automated upgrade agents are now enabled with:" -ForegroundColor Green
    Write-Host "   - System-Assigned Managed Identity" -ForegroundColor White
    Write-Host "   - Contributor role for resource management" -ForegroundColor White
    Write-Host "   - Azure SDK packages installed" -ForegroundColor White
    
    Write-Host "`n🎯 Next Steps:" -ForegroundColor Cyan
    Write-Host "1. Wait for App Service to restart and install new packages" -ForegroundColor White
    Write-Host "2. Test the automated upgrade functionality" -ForegroundColor White
    Write-Host "3. Basic Public IP upgrades should now work automatically!" -ForegroundColor White
} else {
    Write-Host "❌ Infrastructure deployment failed!" -ForegroundColor Red
    Write-Host "Check the deployment logs in Azure Portal for details" -ForegroundColor Yellow
    exit 1
}
