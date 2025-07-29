import React, { useEffect, useState } from "react";
import { PublicClientApplication, AccountInfo } from "@azure/msal-browser";
import { msalConfig, loginRequest, armRequest, apiRequest } from "./authConfig";
import ConsentHelper from "./components/ConsentHelper";
import "./App.css";

const msalInstance = new PublicClientApplication(msalConfig);

const backendApiScope = "api://b0a762fa-2904-4726-b991-871dbfe84f28/user_impersonation";
const azureArmScope = "https://management.azure.com/.default";

async function fetchWithAuth(url: string, token: string, options: any = {}) {
  return fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
}

function App() {
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [apiToken, setApiToken] = useState<string | null>(null);
  const [armToken, setArmToken] = useState<string | null>(null);
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [msalReady, setMsalReady] = useState(false);

  // Initialize MSAL on startup and handle redirects
  useEffect(() => {
    const initializeMsal = async () => {
      try {
        await msalInstance.initialize();
        console.log("✅ MSAL initialized");
        
        // Handle redirect response (from login or token acquisition)
        const response = await msalInstance.handleRedirectPromise();
        
        if (response) {
          console.log("✅ Redirect response received:", response);
          
          if (response.account) {
            setAccount(response.account);
            console.log("✅ Account set from redirect:", response.account.username);
          }
          
          if (response.accessToken) {
            // Check what kind of token we got
            if (response.scopes?.includes("https://management.azure.com/user_impersonation")) {
              setArmToken(response.accessToken);
              console.log("✅ ARM token set from redirect");
            }
          }
        } else {
          // No redirect response, check if user is already signed in
          const accounts = msalInstance.getAllAccounts();
          if (accounts.length > 0) {
            setAccount(accounts[0]);
            console.log("✅ Existing account found:", accounts[0].username);
          }
        }
        
        setMsalReady(true);
      } catch (e: any) {
        console.error("MSAL initialization failed:", e);
        setError("MSAL initialization failed: " + (e.message || e.toString()));
      }
    };
    
    initializeMsal();
  }, []);

  const handleLogin = async () => {
    if (!msalReady) {
      setError(
        "MSAL is not initialized yet. Please wait a moment and try again."
      );
      return;
    }
    setError(null);
    setLoading(true);
    
    try {
      // Check if user is already signed in
      const accounts = msalInstance.getAllAccounts();
      
      if (accounts.length === 0) {
        // No user signed in, redirect to login
        console.log("🔐 No user signed in, redirecting to login...");
        await msalInstance.loginRedirect(loginRequest);
        return; // This will redirect and reload the page
      }
      
      // User is already signed in, get ARM token
      const account = accounts[0];
      setAccount(account);
      console.log("✅ User already signed in:", account.username);
      
      // Get ARM token
      try {
        console.log("🔑 Getting ARM token...");
        const armTokenResp = await msalInstance.acquireTokenSilent({
          account: account,
          scopes: armRequest.scopes,
        });
        setArmToken(armTokenResp.accessToken);
        console.log("✅ ARM token acquired successfully");
      } catch (armError: any) {
        console.log("⚠️ Silent ARM token failed, trying redirect:", armError.errorCode);
        // Use redirect instead of popup to avoid blocking
        if (
          armError.errorCode === "interaction_required" ||
          armError.errorCode === "consent_required" ||
          armError.errorCode === "login_required" ||
          armError.errorCode === "admin_consent_required"
        ) {
          await msalInstance.acquireTokenRedirect({
            account: account,
            scopes: armRequest.scopes,
          });
          return; // This will redirect and reload the page
        } else {
          throw armError;
        }
      }

      setError(null);
    } catch (e: any) {
      console.error("Login error:", e);
      const errorMessage = e.errorMessage || e.message || e.toString();
      setError(`Login failed: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchSubscriptions = async () => {
    if (!armToken) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetchWithAuth("/subscriptions", armToken);
      const data = await resp.json();
      if (!resp.ok) {
        setError(`Failed to fetch subscriptions: ${JSON.stringify(data)}`);
        setSubscriptions([]);
        setLoading(false);
        return;
      }
      if (Array.isArray(data)) {
        setSubscriptions(data);
      } else {
        setError("Subscriptions response was not an array.");
        setSubscriptions([]);
      }
    } catch (e: any) {
      setError(
        `Error fetching subscriptions: ${e.message || e.toString()}`
      );
      setSubscriptions([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (armToken) {
      fetchSubscriptions();
    }
    // eslint-disable-next-line
  }, [armToken]);

  return (
    <div className="App">
      <div className="app-container">
        <h1>Tenant Optimizer AI Agent App</h1>
        <p>
          <b>Optimize and secure your Azure Tenant!</b>
        </p>
        <p>
          Tenant Optimizer is your AI-powered tool for Azure Tenant organizations. It scans your environment to detect <b>orphaned</b> (unused) and <b>deprecated</b> (outdated) resources.
          The app walks you through reviewing, approving, and fixing these resources; <b>it never deletes or upgrades anything automatically without your explicit approval.</b>
        </p>
        {!account ? (
          <button
            onClick={handleLogin}
            className="login-btn"
            disabled={!msalReady}
          >
            {msalReady ? "Sign in with Microsoft" : "Initializing..."}
          </button>
        ) : (
          <div>
            <div>Signed in as: {account.username}</div>
            <button onClick={fetchSubscriptions} disabled={loading}>
              {loading ? "Loading..." : "Refresh Azure Subscriptions"}
            </button>
          </div>
        )}

        {error && (
          <>
            <div className="error" style={{ color: "red", margin: "1em" }}>
              {error}
            </div>
            <ConsentHelper error={error} onRetry={handleLogin} />
          </>
        )}

        <h2>Detected Subscriptions</h2>
        {subscriptions.length > 0 ? (
          <ul>
            {subscriptions.map((sub) => (
              <li key={sub.subscriptionId}>
                {sub.displayName} ({sub.subscriptionId})
              </li>
            ))}
          </ul>
        ) : (
          <div>No subscriptions detected or available.</div>
        )}
      </div>
    </div>
  );
}

export default App;