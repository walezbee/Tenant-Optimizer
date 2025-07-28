export const msalConfig = {
    auth: {
        clientId: "9a164f91-1339-4504-b38e-cf089a90f6fb", // Your Application (client) ID
        authority: "https://login.microsoftonline.com/common", // Multi-tenant: use 'common'
        redirectUri: "https://tenant-optimizer-web.azurewebsites.net", // Your deployed SPA URL
        postLogoutRedirectUri: "https://tenant-optimizer-web.azurewebsites.net", // Optional: after sign-out
    },
    cache: {
        cacheLocation: "sessionStorage", // or "localStorage" if you want persistence
        storeAuthStateInCookie: false, // recommended for most scenarios
    }
};

// Scopes used for login
export const loginRequest = {
    scopes: [
        "openid",
        "profile",
        "offline_access",
        "api://b0a762fa-2904-4726-b991-871dbfe84f28/user_impersonation"
    ]
};

// Scopes for ARM (Azure Resource Manager) API
export const armRequest = {
    scopes: ["https://management.azure.com/.default"]
};