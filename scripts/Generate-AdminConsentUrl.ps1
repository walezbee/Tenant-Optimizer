# Admin Consent URL Generator for Tenant Optimizer
# This script generates the admin consent URL that ANY Azure tenant administrator can use
# to grant consent for their organization to use the Tenant Optimizer application

param(
    [Parameter(Mandatory=$false)]
    [string]$TenantId = "common",
    
    [Parameter(Mandatory=$false)]
    [string]$ClientId = "9a164f91-1339-4504-b38e-cf089a90f6fb",
    
    [Parameter(Mandatory=$false)]
    [string]$RedirectUri = "https://tenant-optimizer-web.azurewebsites.net"
)

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Tenant Optimizer - Admin Consent Helper  " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This URL works for ANY Azure tenant administrator." -ForegroundColor Green
Write-Host "Share this URL with tenant admins who need to grant consent." -ForegroundColor Green
Write-Host ""

# Generate the admin consent URL
$encodedRedirectUri = [System.Web.HttpUtility]::UrlEncode($RedirectUri)
$adminConsentUrl = "https://login.microsoftonline.com/$TenantId/adminconsent?client_id=$ClientId&redirect_uri=$encodedRedirectUri"

Write-Host "Application Details:" -ForegroundColor Yellow
Write-Host "  Client ID: $ClientId"
Write-Host "  Redirect URI: $RedirectUri"
Write-Host "  Tenant: $TenantId"
Write-Host ""

Write-Host "Admin Consent URL:" -ForegroundColor Green
Write-Host $adminConsentUrl
Write-Host ""

# Copy to clipboard if possible
try {
    Set-Clipboard -Value $adminConsentUrl
    Write-Host "✅ Admin consent URL copied to clipboard!" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Could not copy to clipboard. Please copy the URL manually." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Instructions for IT Administrators:" -ForegroundColor Yellow
Write-Host "1. Click the URL above or copy it to your browser"
Write-Host "2. Sign in with your Azure AD administrator account"
Write-Host "3. Review the requested permissions:"
Write-Host "   - Azure Service Management (user_impersonation)"
Write-Host "   - Microsoft Graph (User.Read, offline_access)"
Write-Host "4. Click 'Accept' to grant consent for your organization"
Write-Host "5. Users in your tenant can now access the Tenant Optimizer"
Write-Host ""
Write-Host "NOTE: This URL works for administrators from ANY Azure tenant." -ForegroundColor Cyan
Write-Host "You only need to grant consent ONCE per organization." -ForegroundColor Cyan
Write-Host ""

# Offer to open in browser
$openBrowser = Read-Host "Open admin consent URL in browser? (y/N)"
if ($openBrowser -eq "y" -or $openBrowser -eq "Y") {
    try {
        Start-Process $adminConsentUrl
        Write-Host "✅ Opening admin consent URL in browser..." -ForegroundColor Green
    } catch {
        Write-Host "❌ Could not open browser. Please copy the URL manually." -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "For more information, see:" -ForegroundColor Cyan
Write-Host "https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-admin-consent"
