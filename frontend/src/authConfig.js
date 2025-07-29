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

// Scopes used for login
export const loginRequest = {
    scopes: [
        "openid",
        "profile", 
        "offline_access"
    ],
    prompt: "select_account" // Force account selection for multi-tenant
};

// Scopes for ARM (Azure Resource Manager) API
export const armRequest = {
    scopes: ["https://management.azure.com/user_impersonation"],
    prompt: "select_account" // Changed from "consent" - admin consent already granted
};

// Scopes for custom API
export const apiRequest = {
    scopes: ["api://b0a762fa-2904-4726-b991-871dbfe84f28/user_impersonation"]
};