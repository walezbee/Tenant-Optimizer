# Azure AD Setup for Multi-Tenant Application

## Application Registration

1. Go to https://portal.azure.com → Azure Active Directory → App registrations → New registration.
2. **Name**: "Tenant Optimizer"
3. **Supported account types**: "Accounts in any organizational directory (Any Azure AD directory - Multitenant)"
4. **Redirect URI**: 
   - Type: Single-page application (SPA)
   - URL: https://tenant-optimizer-web.azurewebsites.net
5. Save the **Application (client) ID** and **Directory (tenant) ID**.

## Application Configuration

### Authentication Settings
- **Redirect URIs**: Add your production and development URLs
- **Logout URL**: https://tenant-optimizer-web.azurewebsites.net
- **Implicit grant**: Enable ID tokens (for hybrid flow)
- **Allow public client flows**: No (recommended for SPA)

### API Permissions
1. **Microsoft Graph** (Delegated):
   - `User.Read` - Read basic user profile
   - `offline_access` - Maintain access to data you have given it access to

2. **Azure Service Management** (Delegated):
   - `user_impersonation` - Access Azure Service Management as organization users

3. **Custom API** (if using backend):
   - `api://[your-backend-client-id]/user_impersonation`

### App Roles (Optional)
Define roles for different user types:
- `Admin` - Full access to all features
- `Reader` - Read-only access to resources
- `Contributor` - Can approve/deny recommendations

## Multi-Tenant Consent Strategy

### Option 1: Pre-consent (Recommended)
Create admin consent URLs for each tenant:
```
https://login.microsoftonline.com/{tenant-id}/adminconsent?client_id={your-client-id}&redirect_uri={your-redirect-uri}
```

### Option 2: Publisher Verification
- Verify your publisher domain
- Complete Microsoft Partner Network registration
- This reduces consent prompts for verified publishers

### Option 3: Incremental Consent
- Request minimal permissions initially
- Request additional permissions when needed
- Provides better user experience

## Security Best Practices

1. **Client Secret Management**:
   - Store in Azure Key Vault
   - Rotate secrets regularly
   - Use certificate-based authentication when possible

2. **Token Validation**:
   - Validate issuer (`iss`) claim
   - Verify audience (`aud`) claim matches your client ID
   - Check token expiration (`exp`)

3. **RBAC Configuration**:
   - Assign minimal required roles
   - Use Azure AD groups for role management
   - Implement conditional access policies

## Troubleshooting Common Issues

### AADSTS65001 - Consent Required
**Solution**: Tenant admin must grant consent using admin consent URL

### AADSTS50020 - User from Identity Provider
**Solution**: Ensure application supports the user's identity provider

### AADSTS700016 - Application Not Found
**Solution**: Verify client ID and ensure app is registered in correct tenant