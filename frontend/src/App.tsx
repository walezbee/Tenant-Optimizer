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
  estimatedMonthlyCost?: string;
  priority?: string;
  actions?: Array<{
    type: string;
    description: string;
    riskLevel: string;
    confirmationRequired: boolean;
    estimatedSavings?: string;
    estimatedTimeToComplete?: string;
  }>;
  migrationComplexity?: string;
  estimatedMigrationTime?: string;
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
          console.log("🔍 Response scopes:", response.scopes);
          console.log("🔍 Response account:", response.account?.username);
          
          if (response.account) {
            setAccount(response.account);
            console.log("✅ Account set from redirect:", response.account.username);
            
            // If this was a login redirect (not ARM token redirect), get ARM token
            if (!response.scopes?.includes("https://management.azure.com/user_impersonation")) {
              console.log("🔄 Login redirect completed, now getting ARM token...");
              setTimeout(() => acquireArmToken(response.account!), 1000);
            }
          }
          
          if (response.accessToken) {
            // Check what kind of token we got
            console.log("🔑 Access token received from redirect");
            console.log("🔑 Token scopes:", response.scopes);
            
            if (response.scopes?.includes("https://management.azure.com/user_impersonation")) {
              setArmToken(response.accessToken);
              console.log("✅ ARM token set from redirect");
            } else {
              console.log("ℹ️ Non-ARM token received:", response.scopes);
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

  // Auto-fetch subscriptions when ARM token becomes available
  useEffect(() => {
    if (armToken) {
      console.log("🔄 ARM token available, auto-fetching subscriptions...");
      fetchSubscriptions();
    }
    // eslint-disable-next-line
  }, [armToken]);

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
      
      // Get ARM token immediately after login
      await acquireArmToken(account);

      setError(null);
    } catch (e: any) {
      console.error("Login error:", e);
      const errorMessage = e.errorMessage || e.message || e.toString();
      setError(`Login failed: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  const acquireArmToken = async (account: AccountInfo) => {
    try {
      console.log("🔑 Getting ARM token...");
      console.log("🔑 ARM request scopes:", armRequest.scopes);
      
      const armTokenResp = await msalInstance.acquireTokenSilent({
        account: account,
        scopes: armRequest.scopes,
      });
      
      console.log("✅ ARM token acquired successfully");
      console.log("🔑 ARM token audience:", armTokenResp.account?.idTokenClaims?.aud);
      console.log("🔑 ARM token length:", armTokenResp.accessToken.length);
      
      setArmToken(armTokenResp.accessToken);
      return armTokenResp.accessToken;
    } catch (armError: any) {
      console.log("⚠️ Silent ARM token failed:", armError.errorCode);
      console.log("⚠️ ARM error details:", armError);
      
      // Use redirect instead of popup to avoid blocking
      if (
        armError.errorCode === "interaction_required" ||
        armError.errorCode === "consent_required" ||
        armError.errorCode === "login_required" ||
        armError.errorCode === "admin_consent_required"
      ) {
        console.log("🔄 Redirecting for ARM token consent...");
        setError("Redirecting to Azure for permissions. Please accept the Azure Resource Manager access consent.");
        
        // Use a more explicit consent request
        await msalInstance.acquireTokenRedirect({
          account: account,
          scopes: armRequest.scopes,
          prompt: "consent", // Force consent screen
          extraQueryParameters: {
            "response_mode": "fragment"
          }
        });
        return null; // This will redirect and reload the page
      } else {
        // For other errors, provide more specific guidance
        const errorMessage = armError.errorMessage || armError.message || armError.toString();
        console.error("❌ ARM token acquisition failed:", errorMessage);
        
        if (armError.errorCode === "user_cancelled") {
          throw new Error("Permission request was cancelled. Azure Resource Manager access is required to view subscriptions.");
        } else if (armError.errorCode === "access_denied") {
          throw new Error("Access denied. Please contact your Azure administrator to grant Azure Resource Manager permissions.");
        } else {
          throw new Error(`Failed to get Azure permissions: ${errorMessage}`);
        }
      }
    }
  };

  const fetchSubscriptions = async () => {
    if (!armToken) {
      console.error("❌ No ARM token available, trying to acquire one...");
      
      // Try to get ARM token first
      const accounts = msalInstance.getAllAccounts();
      if (accounts.length > 0) {
        setLoading(true);
        setError("Getting Azure access permissions...");
        try {
          const token = await acquireArmToken(accounts[0]);
          if (!token) {
            // Redirect was triggered, function will return
            return;
          }
          // Token was acquired, continue with subscription fetch
          setError(null);
        } catch (e: any) {
          console.error("❌ ARM token acquisition failed:", e.message);
          setError(e.message || "Failed to get Azure access permissions. Please try signing in again.");
          setLoading(false);
          return;
        }
      } else {
        setError("Please sign in to access your subscriptions.");
        return;
      }
    }
    
    console.log("🔄 Starting subscription fetch...");
    console.log("ARM Token present:", !!armToken);
    console.log("ARM Token length:", armToken?.length);
    
    setLoading(true);
    setError(null);
    
    try {
      const fullUrl = `${getBackendUrl()}/api/subscriptions`;
      console.log("📡 Calling URL:", fullUrl);
      
      const resp = await fetchWithAuth("/api/subscriptions", armToken!);
      console.log("📡 Response status:", resp.status);
      console.log("📡 Response headers:", Object.fromEntries(resp.headers.entries()));
      
      const data = await resp.json();
      console.log("📡 Response data:", data);
      
      if (!resp.ok) {
        console.error("❌ API call failed:", resp.status, data);
        
        // Provide more specific error messages based on status code
        if (resp.status === 401) {
          setError("Authentication failed. Please sign in again and accept Azure permissions.");
        } else if (resp.status === 403) {
          setError("Access denied. You may not have permissions to view subscriptions in this tenant, or admin consent may be required.");
        } else if (resp.status === 429) {
          setError("Too many requests. Please wait a moment and try again.");
        } else {
          setError(`Failed to fetch subscriptions (${resp.status}): ${data.detail || JSON.stringify(data)}`);
        }
        
        setSubscriptions([]);
        setLoading(false);
        return;
      }
      
      if (data.subscriptions && Array.isArray(data.subscriptions)) {
        console.log("✅ Subscriptions loaded:", data.subscriptions.length);
        if (data.subscriptions.length === 0) {
          setError("No subscriptions found. You may not have access to any Azure subscriptions in this tenant.");
        }
        setSubscriptions(data.subscriptions);
      } else {
        console.error("❌ Invalid response format:", data);
        setError("Invalid response from server. Please try again.");
        setSubscriptions([]);
      }
    } catch (e: any) {
      console.error("❌ Subscription fetch error:", e);
      
      // Provide more specific error messages
      if (e.name === 'TypeError' && e.message.includes('fetch')) {
        setError("Network error. Please check your internet connection and try again.");
      } else {
        setError(`Error fetching subscriptions: ${e.message || e.toString()}`);
      }
      
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

  const deleteResource = async (resourceId: string) => {
    if (!armToken) {
      setError("Azure ARM token is required for resource operations");
      return;
    }

    if (!confirm(`Are you sure you want to delete this resource?\n\nResource: ${resourceId}\n\nThis action cannot be undone!`)) {
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const resp = await fetchWithAuth("/api/resources/delete", armToken, {
        method: "POST",
        body: JSON.stringify({ resourceId }),
      });
      
      const data = await resp.json();
      if (!resp.ok) {
        setError(`Resource deletion failed: ${JSON.stringify(data)}`);
        return;
      }

      // Remove the deleted resource from the scan results
      setScanResults(prev => ({
        ...prev,
        orphaned: prev.orphaned?.filter(r => r.resourceId !== resourceId) || []
      }));

      alert(`Resource deletion initiated successfully!\n\nResource: ${resourceId}\nStatus: ${data.status}`);
    } catch (e: any) {
      setError(`Error deleting resource: ${e.message || e.toString()}`);
    } finally {
      setLoading(false);
    }
  };

  const upgradeResource = async (resourceId: string, upgradeType: string = "sku-upgrade") => {
    if (!armToken) {
      setError("Azure ARM token is required for resource operations");
      return;
    }

    if (!confirm(`Are you sure you want to upgrade this resource?\n\nResource: ${resourceId}\nUpgrade Type: ${upgradeType}\n\nThis will modify the resource configuration.`)) {
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const resp = await fetchWithAuth("/api/resources/upgrade", armToken, {
        method: "POST",
        body: JSON.stringify({ resourceId, upgradeType }),
      });
      
      const data = await resp.json();
      if (!resp.ok) {
        setError(`Resource upgrade failed: ${JSON.stringify(data)}`);
        return;
      }

      if (data.manualUpgradeRequired) {
        // Show detailed manual upgrade instructions
        let message = `Manual upgrade required!\n\nResource: ${resourceId}\n\n${data.message}`;
        
        if (data.upgradeSteps) {
          message += "\n\nUpgrade Steps:";
          data.upgradeSteps.forEach((step: string, index: number) => {
            message += `\n${index + 1}. ${step}`;
          });
        }
        
        if (data.attachedTo) {
          message += `\n\nCurrently attached to: ${data.attachedTo}`;
        }
        
        if (data.azurePortalUrl) {
          message += `\n\nAzure Portal Link: ${data.azurePortalUrl}`;
        }
        
        alert(message);
        
        // For Public IPs that are in use, show a special message
        if (data.attachedTo) {
          const shouldOpenPortal = confirm("Would you like to open Azure Portal to perform the manual upgrade?");
          if (shouldOpenPortal && data.azurePortalUrl) {
            window.open(data.azurePortalUrl, '_blank');
          }
        }
      } else if (data.alreadyUpgraded) {
        alert(`Resource is already upgraded!\n\nResource: ${resourceId}\n${data.message}`);
        
        // Remove from deprecated results since it's already upgraded
        setScanResults(prev => ({
          ...prev,
          deprecated: prev.deprecated?.filter(r => r.resourceId !== resourceId) || []
        }));
      } else {
        // Remove the upgraded resource from deprecated results
        setScanResults(prev => ({
          ...prev,
          deprecated: prev.deprecated?.filter(r => r.resourceId !== resourceId) || []
        }));

        let successMessage = `Resource upgrade completed successfully!\n\nResource: ${resourceId}\nStatus: ${data.status}`;
        
        if (data.upgradedFrom && data.upgradedTo) {
          successMessage += `\nUpgraded from: ${data.upgradedFrom}\nUpgraded to: ${data.upgradedTo}`;
        }
        
        alert(successMessage);
      }
    } catch (e: any) {
      setError(`Error upgrading resource: ${e.message || e.toString()}`);
    } finally {
      setLoading(false);
    }
  };

  const handleManualConsent = async () => {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length === 0) {
      setError("Please sign in first.");
      return;
    }

    setLoading(true);
    setError("Redirecting to Azure for permission consent...");
    
    try {
      await msalInstance.acquireTokenRedirect({
        account: accounts[0],
        scopes: armRequest.scopes,
        prompt: "consent", // Force consent screen
        extraQueryParameters: {
          "response_mode": "fragment"
        }
      });
    } catch (e: any) {
      console.error("Manual consent error:", e);
      setError("Failed to initiate permission request. Please try again.");
      setLoading(false);
    }
  };

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
                            {resource.estimatedMonthlyCost && (
                              <div className="resource-cost">💰 {resource.estimatedMonthlyCost}</div>
                            )}
                            {resource.priority && (
                              <div className={`resource-priority priority-${resource.priority.toLowerCase()}`}>
                                {resource.priority} Priority
                              </div>
                            )}
                          </div>
                          <div className="resource-issue">
                            <div className="issue">{resource.issue}</div>
                            <div className="recommendation">{resource.recommendation}</div>
                          </div>
                          {resource.actions && resource.actions.length > 0 && (
                            <div className="resource-actions">
                              {resource.actions.map((action, actionIndex) => (
                                <button
                                  key={actionIndex}
                                  className={`action-button action-${action.type} risk-${action.riskLevel.toLowerCase()}`}
                                  onClick={() => action.type === 'delete' ? deleteResource(resource.resourceId) : console.log('Action not implemented')}
                                  disabled={loading}
                                  title={`${action.description} (Risk: ${action.riskLevel}${action.estimatedSavings ? ', Saves: ' + action.estimatedSavings : ''})`}
                                >
                                  {action.type === 'delete' ? '🗑️ Delete' : '⚡ ' + action.type}
                                  {action.estimatedSavings && (
                                    <span className="action-savings">💰 {action.estimatedSavings}</span>
                                  )}
                                </button>
                              ))}
                            </div>
                          )}
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
                            {resource.priority && (
                              <div className={`resource-priority priority-${resource.priority.toLowerCase()}`}>
                                {resource.priority} Priority
                              </div>
                            )}
                            {resource.migrationComplexity && (
                              <div className="migration-complexity">
                                🔧 {resource.migrationComplexity} Complexity
                              </div>
                            )}
                          </div>
                          <div className="resource-issue">
                            <div className="issue">{resource.issue}</div>
                            <div className="recommendation">{resource.recommendation}</div>
                            {resource.estimatedMigrationTime && (
                              <div className="migration-time">⏱️ Est. Time: {resource.estimatedMigrationTime}</div>
                            )}
                          </div>
                          {resource.actions && resource.actions.length > 0 && (
                            <div className="resource-actions">
                              {resource.actions.map((action, actionIndex) => (
                                <button
                                  key={actionIndex}
                                  className={`action-button action-${action.type} risk-${action.riskLevel.toLowerCase()}`}
                                  onClick={() => action.type === 'upgrade' ? upgradeResource(resource.resourceId) : console.log('Action not implemented')}
                                  disabled={loading}
                                  title={`${action.description} (Risk: ${action.riskLevel}${action.estimatedTimeToComplete ? ', Time: ' + action.estimatedTimeToComplete : ''})`}
                                >
                                  {action.type === 'upgrade' ? '⬆️ Upgrade' : '⚡ ' + action.type}
                                  {action.estimatedTimeToComplete && (
                                    <span className="action-time">⏱️ {action.estimatedTimeToComplete}</span>
                                  )}
                                </button>
                              ))}
                            </div>
                          )}
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
            {(error.includes("permissions") || error.includes("consent") || error.includes("access")) && account && (
              <button 
                onClick={handleManualConsent}
                className="consent-btn"
                disabled={loading}
              >
                🔐 Grant Azure Permissions
              </button>
            )}
            <ConsentHelper error={error} onRetry={handleLogin} />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;