export const msalConfig = {
    auth: {
        clientId: "9a164f91-1339-4504-b38e-cf089a90f6fb", // Your Application (client) ID
        authority: "https://login.microsoftonline.com/common", // Multi-tenant: use 'common'
        redirectUri: "https://tenant-optimizer-web.azurewebsites.net", // Your deployed SPA URL
        postLogoutRedirectUri: "https://tenant-optimizer-web.azurewebsites.net", // Optional: after sign-out
        knownAuthorities: [], // Add trusted authorities if needed
        cloudDiscoveryMetadata: "", // Optional: for national clouds
        authorityMetadata: "" // Optional: for performance optimization
    },
    cache: {
        cacheLocation: "sessionStorage", // or "localStorage" if you want persistence
        storeAuthStateInCookie: false, // recommended for most scenarios
    },
    system: {
        allowNativeBroker: false, // Disable native broker for web apps
        windowHashTimeout: 60000, // 60 seconds timeout for popup
        iframeHashTimeout: 6000, // 6 seconds timeout for iframe
        loadFrameTimeout: 0 // Disable iframe for popup flow
    }
};

// Scopes used for login - simplified for multi-tenant
export const loginRequest = {
    scopes: [
        "openid",
        "profile", 
        "email" // Add email scope explicitly
    ],
    prompt: "select_account", // Force account selection for multi-tenant
    extraQueryParameters: {
        "response_mode": "fragment" // Ensure fragment mode for SPA
    }
};

// Scopes for ARM (Azure Resource Manager) API - simplified approach
export const armRequest = {
    scopes: ["https://management.azure.com/user_impersonation"],
    // Remove prompt entirely - let MSAL handle it automatically
    extraQueryParameters: {
        "response_mode": "fragment"
    }
};

// Scopes for custom API
export const apiRequest = {
    scopes: ["api://b0a762fa-2904-4726-b991-871dbfe84f28/user_impersonation"]
};