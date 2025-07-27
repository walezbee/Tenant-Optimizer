import React, { useEffect, useState } from "react";
import { PublicClientApplication, AccountInfo } from "@azure/msal-browser";
import { msalConfig } from "./authConfig";
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
    try {
      // 1. Login: Only use app scopes (no ARM .default here!)
      const loginResponse = await msalInstance.loginPopup({
        scopes: [
          "openid",
          "profile",
          "offline_access",
          backendApiScope,
        ],
      });
      setAccount(loginResponse.account);

      // 2. Get API token (optional, you can also use loginResponse.accessToken)
      const apiTokenResp = await msalInstance.acquireTokenSilent({
        account: loginResponse.account,
        scopes: [backendApiScope],
      });
      setApiToken(apiTokenResp.accessToken);

      // 3. Get ARM token (separate call, after login!)
      let armTokenResp;
      try {
        armTokenResp = await msalInstance.acquireTokenSilent({
          account: loginResponse.account,
          scopes: [azureArmScope],
        });
      } catch (e: any) {
        // Interactive consent if needed
        if (
          e.errorCode === "interaction_required" ||
          e.errorCode === "consent_required" ||
          e.errorCode === "login_required"
        ) {
          armTokenResp = await msalInstance.acquireTokenPopup({
            account: loginResponse.account,
            scopes: [azureArmScope],
          });
        } else {
          throw e;
        }
      }
      setArmToken(armTokenResp.accessToken);

      setError(null);
    } catch (e: any) {
      setError(`Login failed: ${e.message || e.toString()}`);
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
          <div className="error" style={{ color: "red", margin: "1em" }}>
            {error}
          </div>
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