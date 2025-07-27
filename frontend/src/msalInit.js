import { PublicClientApplication } from "@azure/msal-browser";
import { msalConfig, loginRequest } from "./authConfig";

export const msalInstance = new PublicClientApplication(msalConfig);

export async function loginAndGetToken() {
    // Try to get account
    let account = msalInstance.getActiveAccount();
    if (!account) {
        // No signed-in user, initiate login
        await msalInstance.loginRedirect(loginRequest);
        return null; // will redirect and not return
    }
    // Try to silently acquire token
    try {
        let response = await msalInstance.acquireTokenSilent({
            ...loginRequest,
            account
        });
        return response.accessToken;
    } catch (e) {
        // If silent fails, do interactive login
        await msalInstance.loginRedirect(loginRequest);
        return null;
    }
}