// EMERGENCY FIX: Replace the imports in App.tsx temporarily to test
// Change line 3 in App.tsx from:
// import { msalConfig, loginRequest, armRequest, apiRequest } from "./authConfig";
// 
// To:
// import { msalConfigFixed as msalConfig, loginRequestFixed as loginRequest, armRequestFixed as armRequest, apiRequest } from "./authConfigFixed";

// Step-by-step testing approach:

// 1. First, try the basic login without any ARM scopes
export const testLoginOnly = {
    scopes: ["openid", "profile"],
    prompt: "select_account"
};

// 2. If basic login works, then try ARM separately
export const testArmRequest = {
    scopes: ["https://management.azure.com/user_impersonation"]
    // No prompt - let MSAL decide
};

// 3. For debugging - log all MSAL events
export function setupMSALLogging(msalInstance) {
    msalInstance.setLogger({
        loggerCallback: (level, message, containsPii) => {
            if (containsPii) { return; }
            console.log(`[MSAL ${level}] ${message}`);
        },
        piiLoggingEnabled: false,
        logLevel: 3 // Info level - shows consent requirements
    });
}

// 4. Alternative admin consent URL (try this if current one isn't working)
export const alternativeConsentUrl = `https://login.microsoftonline.com/{tenant-id}/adminconsent?client_id=9a164f91-1339-4504-b38e-cf089a90f6fb&redirect_uri=https://tenant-optimizer-web.azurewebsites.net&state=alternative_consent`;

console.log("🚨 EMERGENCY AUTH CONFIG LOADED");
console.log("📝 Use this for step-by-step debugging");
console.log("🔗 Alternative consent URL:", alternativeConsentUrl);
