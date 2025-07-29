import React, { useEffect, useState } from "react";
import { PublicClientApplication, AccountInfo } from "@azure/msal-browser";
import { msalConfig, loginRequest, armRequest, apiRequest } from "./authConfig";
import ConsentHelper from "./components/ConsentHelper";
import "./App.css";

const msalInstance = new PublicClientApplication(msalConfig);

const backendApiScope = "api://b0a762fa-2904-4726-b991-871dbfe84f28/user_impersonation";
const azureArmScope = "https://management.azure.com/.default";

// Get backend base URL based on environment
const getBackendUrl = () => {
  if (window.location.hostname === 'localhost') {
    return 'http://localhost:8000';
  }
  return ''; // Use relative URLs for production (same domain)
};

async function fetchWithAuth(url: string, token: string, options: any = {}) {
  const fullUrl = url.startsWith('http') ? url : `${getBackendUrl()}${url}`;
  return fetch(fullUrl, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
}

interface Subscription {
  subscriptionId: string;
  displayName: string;
  state: string;
}

interface ScanResult {
  resourceId: string;
  resourceName: string;
  resourceType: string;
  location: string;
  resourceGroup: string;
  issue: string;
  recommendation: string;
}

function App() {
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [apiToken, setApiToken] = useState<string | null>(null);
  const [armToken, setArmToken] = useState<string | null>(null);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [selectedSubscriptions, setSelectedSubscriptions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [msalReady, setMsalReady] = useState(false);
  const [scanResults, setScanResults] = useState<{
    orphaned?: ScanResult[];
    deprecated?: ScanResult[];
  }>({});
  const [scanLoading, setScanLoading] = useState<{
    orphaned: boolean;
    deprecated: boolean;
  }>({ orphaned: false, deprecated: false });

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
      const resp = await fetchWithAuth("/api/subscriptions", armToken);
      const data = await resp.json();
      if (!resp.ok) {
        setError(`Failed to fetch subscriptions: ${JSON.stringify(data)}`);
        setSubscriptions([]);
        setLoading(false);
        return;
      }
      if (data.subscriptions && Array.isArray(data.subscriptions)) {
        setSubscriptions(data.subscriptions);
      } else {
        setError("Subscriptions response format is invalid.");
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

  const handleSubscriptionSelection = (subscriptionId: string) => {
    setSelectedSubscriptions(prev => {
      if (prev.includes(subscriptionId)) {
        return prev.filter(id => id !== subscriptionId);
      } else {
        return [...prev, subscriptionId];
      }
    });
  };

  const scanOrphanedResources = async () => {
    if (selectedSubscriptions.length === 0) {
      setError("Please select at least one subscription to scan.");
      return;
    }
    
    if (!armToken) {
      setError("No authentication token available. Please sign in again.");
      return;
    }
    
    setScanLoading(prev => ({ ...prev, orphaned: true }));
    setError(null);
    
    try {
      const resp = await fetchWithAuth("/api/scan/orphaned", armToken, {
        method: "POST",
        body: JSON.stringify({ subscriptions: selectedSubscriptions }),
      });
      
      const data = await resp.json();
      if (!resp.ok) {
        setError(`Orphaned scan failed: ${JSON.stringify(data)}`);
        return;
      }
      
      setScanResults(prev => ({ ...prev, orphaned: data.orphaned || [] }));
    } catch (e: any) {
      setError(`Error scanning orphaned resources: ${e.message || e.toString()}`);
    } finally {
      setScanLoading(prev => ({ ...prev, orphaned: false }));
    }
  };

  const scanDeprecatedResources = async () => {
    if (selectedSubscriptions.length === 0) {
      setError("Please select at least one subscription to scan.");
      return;
    }
    
    if (!armToken) {
      setError("No authentication token available. Please sign in again.");
      return;
    }
    
    setScanLoading(prev => ({ ...prev, deprecated: true }));
    setError(null);
    
    try {
      const resp = await fetchWithAuth("/api/scan/deprecated", armToken, {
        method: "POST",
        body: JSON.stringify({ subscriptions: selectedSubscriptions }),
      });
      
      const data = await resp.json();
      if (!resp.ok) {
        setError(`Deprecated scan failed: ${JSON.stringify(data)}`);
        return;
      }
      
      setScanResults(prev => ({ ...prev, deprecated: data.deprecated || [] }));
    } catch (e: any) {
      setError(`Error scanning deprecated resources: ${e.message || e.toString()}`);
    } finally {
      setScanLoading(prev => ({ ...prev, deprecated: false }));
    }
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
        <header className="app-header">
          <h1 className="app-title">
            <span className="title-icon">🚀</span>
            Tenant Optimizer AI Agent
          </h1>
          <p className="app-subtitle">
            <b>Optimize and secure your Azure Tenant!</b>
          </p>
          <p className="app-description">
            Tenant Optimizer is your AI-powered tool for Azure Tenant organizations. It scans your environment to detect <b>orphaned</b> (unused) and <b>deprecated</b> (outdated) resources.
            The app walks you through reviewing, approving, and fixing these resources; <b>it never deletes or upgrades anything automatically without your explicit approval.</b>
          </p>
        </header>

        {!account ? (
          <div className="auth-section">
            <button
              onClick={handleLogin}
              className="login-btn"
              disabled={!msalReady}
            >
              {msalReady ? "🔐 Sign in with Microsoft" : "⏳ Initializing..."}
            </button>
          </div>
        ) : (
          <div className="main-content">
            <div className="user-info">
              <span className="user-avatar">👤</span>
              <span className="user-name">Signed in as: {account.username}</span>
            </div>

            <div className="subscriptions-section">
              <div className="section-header">
                <h2 className="section-title">📋 Azure Subscriptions</h2>
                <button 
                  onClick={fetchSubscriptions} 
                  disabled={loading}
                  className="refresh-btn"
                >
                  {loading ? "⏳ Loading..." : "🔄 Select Subscriptions to Scan"}
                </button>
              </div>

              {subscriptions.length > 0 && (
                <div className="subscription-list">
                  <h3 className="list-title">Select subscriptions to scan:</h3>
                  <div className="checkbox-list">
                    {subscriptions.map((sub) => (
                      <label key={sub.subscriptionId} className="subscription-item">
                        <input
                          type="checkbox"
                          checked={selectedSubscriptions.includes(sub.subscriptionId)}
                          onChange={() => handleSubscriptionSelection(sub.subscriptionId)}
                          className="subscription-checkbox"
                        />
                        <div className="subscription-info">
                          <div className="subscription-name">{sub.displayName}</div>
                          <div className="subscription-id">{sub.subscriptionId}</div>
                          <div className="subscription-state">{sub.state}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                  
                  {selectedSubscriptions.length > 0 && (
                    <div className="selected-info">
                      ✅ {selectedSubscriptions.length} subscription{selectedSubscriptions.length > 1 ? 's' : ''} selected
                    </div>
                  )}
                </div>
              )}

              {subscriptions.length === 0 && !loading && (
                <div className="no-subscriptions">
                  📭 No subscriptions detected or available. Click "Select Subscriptions to Scan" to refresh.
                </div>
              )}
            </div>

            {selectedSubscriptions.length > 0 && (
              <div className="scan-section">
                <h2 className="section-title">🔍 Resource Scanning</h2>
                <div className="scan-buttons">
                  <button
                    onClick={scanOrphanedResources}
                    disabled={scanLoading.orphaned}
                    className="scan-btn orphaned-btn"
                  >
                    {scanLoading.orphaned ? "⏳ Scanning..." : "🗑️ Scan Orphaned Resources"}
                  </button>
                  
                  <button
                    onClick={scanDeprecatedResources}
                    disabled={scanLoading.deprecated}
                    className="scan-btn deprecated-btn"
                  >
                    {scanLoading.deprecated ? "⏳ Scanning..." : "⚠️ Scan Deprecated Resources"}
                  </button>
                </div>
              </div>
            )}

            {/* Scan Results */}
            {(scanResults.orphaned?.length || scanResults.deprecated?.length) && (
              <div className="results-section">
                <h2 className="section-title">📊 Scan Results</h2>
                
                {scanResults.orphaned && scanResults.orphaned.length > 0 && (
                  <div className="result-category">
                    <h3 className="result-title">🗑️ Orphaned Resources ({scanResults.orphaned.length})</h3>
                    <div className="result-list">
                      {scanResults.orphaned.map((resource, index) => (
                        <div key={index} className="result-item orphaned-item">
                          <div className="resource-info">
                            <div className="resource-name">{resource.resourceName}</div>
                            <div className="resource-type">{resource.resourceType}</div>
                            <div className="resource-location">{resource.location} • {resource.resourceGroup}</div>
                          </div>
                          <div className="resource-issue">
                            <div className="issue">{resource.issue}</div>
                            <div className="recommendation">{resource.recommendation}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {scanResults.deprecated && scanResults.deprecated.length > 0 && (
                  <div className="result-category">
                    <h3 className="result-title">⚠️ Deprecated Resources ({scanResults.deprecated.length})</h3>
                    <div className="result-list">
                      {scanResults.deprecated.map((resource, index) => (
                        <div key={index} className="result-item deprecated-item">
                          <div className="resource-info">
                            <div className="resource-name">{resource.resourceName}</div>
                            <div className="resource-type">{resource.resourceType}</div>
                            <div className="resource-location">{resource.location} • {resource.resourceGroup}</div>
                          </div>
                          <div className="resource-issue">
                            <div className="issue">{resource.issue}</div>
                            <div className="recommendation">{resource.recommendation}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="error-section">
            <div className="error">
              ❌ {error}
            </div>
            <ConsentHelper error={error} onRetry={handleLogin} />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;