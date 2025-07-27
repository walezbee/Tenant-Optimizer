export const msalConfig = {
    auth: {
        clientId: "9a164f91-1339-4504-b38e-cf089a90f6fb", // from frontend app registration
        authority: "https://login.microsoftonline.com/36d8a1ac-8d2d-4744-b032-9074fd822ec5",
        redirectUri: "https://tenant-optimizer-web.azurewebsites.net/"
    }
};

export const loginRequest = {
    scopes: ["api://b0a762fa-2904-4726-b991-871dbfe84f28/user_impersonation"]
};