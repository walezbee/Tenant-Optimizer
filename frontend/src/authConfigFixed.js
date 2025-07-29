// Alternative Auth Configuration for Multi-Tenant Fix
// Use this configuration if the current setup continues to fail

export const msalConfigFixed = {
    auth: {
        clientId: "9a164f91-1339-4504-b38e-cf089a90f6fb",
        authority: "https://login.microsoftonline.com/common",
        redirectUri: "https://tenant-optimizer-web.azurewebsites.net",
        postLogoutRedirectUri: "https://tenant-optimizer-web.azurewebsites.net",
        navigateToLoginRequestUrl: false, // Important for external tenants
        // Add these for multi-tenant support
        knownAuthorities: ["login.microsoftonline.com"],
        cloudDiscoveryMetadata: "",
        authorityMetadata: ""
    },
    cache: {
        cacheLocation: "sessionStorage",
        storeAuthStateInCookie: false,
    },
    system: {
        allowNativeBroker: false,
        windowHashTimeout: 60000,
        iframeHashTimeout: 6000,
        loadFrameTimeout: 0,
        // Add for better multi-tenant support
        loggerOptions: {
            loggerCallback: (level, message, containsPii) => {
                if (containsPii) return;
                console.log(`MSAL [${level}]: ${message}`);
            },
            piiLoggingEnabled: false,
            logLevel: 3 // Info level
        }
    }
};

// Basic login request - no additional scopes
export const loginRequestFixed = {
    scopes: ["openid", "profile", "User.Read"],
    forceRefresh: false,
    // Remove prompt to let MSAL handle it
};

// ARM request - simplified
export const armRequestFixed = {
    scopes: ["https://management.azure.com/user_impersonation"],
    forceRefresh: false,
    // No prompt - let MSAL handle consent automatically
};

export const consentHelperUrl = `https://login.microsoftonline.com/common/adminconsent?client_id=9a164f91-1339-4504-b38e-cf089a90f6fb&redirect_uri=https://tenant-optimizer-web.azurewebsites.net&state=admin_consent_for_external_tenant`;

console.log("🔧 Alternative auth config loaded. Admin consent URL:", consentHelperUrl);
