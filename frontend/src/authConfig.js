export const msalConfig = {
  auth: {
    clientId: "9a164f91-1339-4504-b38e-cf089a90f6fb", // Replace with your Azure AD App Registration (SPA) clientId
    authority: "https://login.microsoftonline.com/36d8a1ac-8d2d-4744-b032-9074fd822ec5", // Or "common" for multi-tenant: https://login.microsoftonline.com/common
    redirectUri: "https://tenant-optimizer-web.azurewebsites.net", // Or your deployed URL, e.g., "https://tenant-optimizer-web.azurewebsites.net"
  },
  cache: {
    cacheLocation: "localStorage",
    storeAuthStateInCookie: false,
  },
};