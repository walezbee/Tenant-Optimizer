# Azure AD Setup

1. Go to https://portal.azure.com → Azure Active Directory → App registrations → New registration.
2. Name: "Tenant Optimizer", Supported account types: "Accounts in any organizational directory"
3. Set Redirect URI to your app's URL (e.g., https://tenant-optimizer.azurewebsites.net/auth/callback)
4. Save Application (client) ID and Directory (tenant) ID.
5. Create a client secret. Store this in Azure Key Vault.
6. In API permissions, add "Azure Service Management" and "User.Read".
7. Assign roles to let app read resource inventory (Reader).