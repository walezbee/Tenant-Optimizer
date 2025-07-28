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

  // Initialize MSAL on startup
  useEffect(() => {
    msalInstance
      .initialize()
      .then(() => setMsalReady(true))
      .catch((e) =>
        setError(
          "MSAL initialization failed: " + (e.message || e.toString())
        )
      );
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
      // 1. Login with basic scopes first
      const loginResponse = await msalInstance.loginPopup(loginRequest);
      setAccount(loginResponse.account);

      // 2. Get API token for backend
      try {
        const apiTokenResp = await msalInstance.acquireTokenSilent({
          account: loginResponse.account,
          scopes: apiRequest.scopes,
        });
        setApiToken(apiTokenResp.accessToken);
      } catch (apiError: any) {
        console.warn("Could not get API token silently:", apiError);
        // Try interactive consent for API
        try {
          const apiTokenResp = await msalInstance.acquireTokenPopup({
            account: loginResponse.account,
            scopes: apiRequest.scopes,
          });
          setApiToken(apiTokenResp.accessToken);
        } catch (apiInteractiveError: any) {
          console.error("API token interactive consent failed:", apiInteractiveError);
          // Continue without API token for now
        }
      }

      // 3. Get ARM token (separate call, after login!)
      try {
        const armTokenResp = await msalInstance.acquireTokenSilent({
          account: loginResponse.account,
          scopes: armRequest.scopes,
        });
        setArmToken(armTokenResp.accessToken);
      } catch (armError: any) {
        // Interactive consent if needed
        if (
          armError.errorCode === "interaction_required" ||
          armError.errorCode === "consent_required" ||
          armError.errorCode === "login_required" ||
          armError.errorCode === "admin_consent_required"
        ) {
          try {
            const armTokenResp = await msalInstance.acquireTokenPopup({
              account: loginResponse.account,
              scopes: armRequest.scopes,
              prompt: "consent"
            });
            setArmToken(armTokenResp.accessToken);
          } catch (armInteractiveError: any) {
            console.error("ARM token interactive consent failed:", armInteractiveError);
            throw armInteractiveError;
          }
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