# Admin Consent Setup for Multi-Tenant Access

## The Problem
When users from external Azure tenants try to access the Tenant Optimizer application, they encounter the error:
```
AADSTS65001: The user or administrator has not consented to use the application
```

## The Solution: Universal Admin Consent URL

### **Important**: One URL Works for All Tenants
You **do not** need to generate separate consent URLs for each tenant. The URL below works for administrators from **any** Azure tenant.

### **Universal Admin Consent URL**
```
https://login.microsoftonline.com/common/adminconsent?client_id=9a164f91-1339-4504-b38e-cf089a90f6fb&redirect_uri=https://tenant-optimizer-web.azurewebsites.net
```

### How It Works
1. **Any tenant administrator** can use this URL
2. They sign in with **their own tenant credentials**  
3. Consent is granted for **their specific organization**
4. **All users** in their tenant can then access the app

### For Tenant Administrators

**Steps to Grant Consent:**

1. **Visit the Universal Admin Consent URL** (shown above)

2. **Sign in** with your Azure AD administrator account

3. **Review the requested permissions** and click "Accept" to grant consent for your organization

4. **Verify Success:**
   - Users in your organization can now access the application
   - No individual user consent will be required

### Permissions Requested
The application requests the following permissions:
- **Azure Service Management (user_impersonation)**: To read Azure resources
- **Microsoft Graph (User.Read)**: To read basic user profile
- **Microsoft Graph (offline_access)**: To refresh tokens

### Security Notes
- Only Global Administrators can grant tenant-wide consent
- This consent applies to all users in your organization
- You can revoke consent at any time from the Azure portal
