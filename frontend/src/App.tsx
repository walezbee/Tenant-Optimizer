import React, { useEffect, useState } from "react";
import { PublicClientApplication, AccountInfo } from "@azure/msal-browser";

// Basic styles object
const styles = {
  body: {
    background: "linear-gradient(90deg, #e3ffe8 0%, #f9f9f9 100%)",
    minHeight: "100vh",
    padding: 0,
    margin: 0,
    fontFamily: "Segoe UI, Arial, sans-serif",
  },
  container: {
    maxWidth: 600,
    margin: "40px auto",
    background: "#fff",
    borderRadius: 12,
    boxShadow: "0 2px 16px #0001",
    padding: 32,
  },
  signInOut: {
    display: "flex",
    justifyContent: "flex-end",
    marginBottom: 16,
  },
  button: {
    background: "linear-gradient(90deg, #2575fc 0%, #6a11cb 100%)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "10px 22px",
    fontSize: 16,
    fontWeight: 600,
    cursor: "pointer",
    marginRight: 8,
    marginBottom: 8,
    transition: "background 0.2s",
  },
  header: {
    fontSize: 28,
    fontWeight: 700,
    color: "#512da8",
    marginBottom: 10,
  },
  description: {
    fontSize: 16,
    color: "#333",
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 600,
    color: "#2575fc",
    margin: "24px 0 10px 0",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    marginBottom: 20,
  },
  th: {
    background: "#f3f6fb",
    color: "#333",
    fontWeight: 600,
    padding: "8px 10px",
    borderBottom: "2px solid #e0e0e0",
    textAlign: "left" as const,
  },
  td: {
    padding: "8px 10px",
    borderBottom: "1px solid #eee",
    fontSize: 15,
  },
  status: {
    display: "inline-block",
    marginLeft: 8,
    padding: "2px 8px",
    borderRadius: 8,
    background: "#e3f2fd",
    color: "#1976d2",
    fontSize: 13,
    fontWeight: 500,
  },
  approvalList: {
    listStyle: "none",
    padding: 0,
    margin: 0,
  },
  approvalItem: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    background: "#f9f9f9",
    borderRadius: 6,
    padding: "10px 16px",
    marginBottom: 10,
    boxShadow: "0 1px 4px #0001",
  },
  approveButton: {
    background: "linear-gradient(90deg, #43e97b 0%, #38f9d7 100%)",
    color: "#222",
    border: "none",
    borderRadius: 6,
    padding: "8px 18px",
    fontWeight: 600,
    fontSize: 15,
    cursor: "pointer",
    transition: "background 0.2s",
  },
};

// MSAL config as before...
const msalConfig = {
  auth: {
    clientId: "9a164f91-1339-4504-b38e-cf089a90f6fb",
    authority: "https://login.microsoftonline.com/36d8a1ac-8d2d-4744-b032-9074fd822ec5",
    redirectUri: "https://tenant-optimizer-web.azurewebsites.net/",
  },
};
const apiScope = "api://b0a762fa-2904-4726-b991-871dbfe84f28/user_impersonation";
const msalInstance = new PublicClientApplication(msalConfig);

// ... styles as before

type Subscription = {
  subscriptionId: string;
  displayName: string;
};
type Resource = {
  name: string;
  type: string;
  status: string;
};
type ApprovalAction = {
  id: string;
  name: string;
  type: string;
  action: "delete" | "upgrade";
  status: string;
};

function App() {
  // MSAL state
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [isMsalReady, setIsMsalReady] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Data state
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [selectedSubs, setSelectedSubs] = useState<string[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [approvals, setApprovals] = useState<ApprovalAction[]>([]);
  const [error, setError] = useState<string | null>(null);

  // On mount, initialize MSAL and check if user is signed in
  useEffect(() => {
    msalInstance.initialize().then(() => {
      setIsMsalReady(true);
      msalInstance.handleRedirectPromise().then((response) => {
        let acc: AccountInfo | null = null;
        if (response && response.account) {
          acc = response.account;
        } else {
          const accts = msalInstance.getAllAccounts();
          if (accts.length > 0) acc = accts[0];
        }
        setAccount(acc);
        if (acc) msalInstance.setActiveAccount(acc);
      });
    });
    // eslint-disable-next-line
  }, []);

  // Fetch subscriptions after sign in
  useEffect(() => {
    if (!account) return;
    getToken().then(token => {
      fetch("/subscriptions", {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(data => {
          setSubscriptions(data);
          if (data.length) setSelectedSubs([data[0].subscriptionId]);
        })
        .catch(err => setError("Failed to fetch subscriptions: " + err));
    });
    // eslint-disable-next-line
  }, [account]);

  // Sign in/out handlers
  const signIn = async () => {
    await msalInstance.loginRedirect({ scopes: [apiScope] });
  };
  const signOut = () => {
    msalInstance.logoutRedirect();
  };

  async function getToken() {
    if (!account) throw new Error("Not signed in");
    try {
      const result = await msalInstance.acquireTokenSilent({
        account,
        scopes: [apiScope],
      });
      return result.accessToken;
    } catch (e) {
      await signIn();
      return ""; // Unreachable, as signIn will redirect
    }
  }

  async function onScanOrphaned() {
    setIsLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const resp = await fetch("/scan/orphaned", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ subscriptions: selectedSubs }),
      });
      if (!resp.ok) throw new Error("Scan failed: " + resp.statusText);
      const data = await resp.json();
      setResources(data.resources || []);
      setApprovals(data.approvals || []);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function onScanDeprecated() {
    setIsLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const resp = await fetch("/scan/deprecated", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ subscriptions: selectedSubs }),
      });
      if (!resp.ok) throw new Error("Scan failed: " + resp.statusText);
      const data = await resp.json();
      setResources(data.resources || []);
      setApprovals(data.approvals || []);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setIsLoading(false);
    }
  }

  async function onApprove(approval: ApprovalAction) {
    setIsLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const resp = await fetch(
        approval.action === "delete"
          ? "/delete/orphaned"
          : "/upgrade/deprecated",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ id: approval.id, subscription_id: selectedSubs[0] }),
        }
      );
      if (!resp.ok) throw new Error("Approval failed: " + resp.statusText);
      // Optionally, refetch data
      await onScanOrphaned();
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const options = Array.from(e.target.selectedOptions);
    setSelectedSubs(options.map(opt => opt.value));
  }

  // --- UI ---
  if (!isMsalReady) {
    return (
      <div style={styles.body as React.CSSProperties}>
        <div style={styles.container}>
          <div style={{ fontSize: 22, color: "#512da8", fontWeight: 600 }}>
            Loading authentication...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.body as React.CSSProperties}>
      <div style={styles.container}>
        <div style={styles.signInOut}>
          {!account ? (
            <button style={styles.button} onClick={signIn}>
              Sign in with Microsoft
            </button>
          ) : (
            <button style={styles.button} onClick={signOut}>
              Sign out ({account.username})
            </button>
          )}
        </div>
        <div>
          <div style={styles.header}>Tenant Optimizer AI Agent App</div>
          <div style={styles.description}>
            <b>Optimize and secure your Azure Tenant!</b>
            <br />
            <br />
            Tenant Optimizer is your AI-powered tool for Azure Tenant organizations.
            It scans your environment to detect <b>orphaned</b> (unused) and <b>deprecated</b> (outdated) resources,
            This helps you spot cost savings and improve security.
            The app walks you through reviewing, approving, and fixing these resources;
            <b> it never deletes or upgrades anything automatically without your explicit approval.</b>
            <br />
            <br />
            <span style={{ color: "#2575fc" }}>
              Sign in with your Microsoft Entra ID (Azure AD) account to begin.
            </span>
          </div>

          {account && (
            <>
              <div style={styles.sectionTitle}>Select Subscription(s) to Scan</div>
              <select multiple size={Math.min(6, subscriptions.length)} value={selectedSubs} onChange={handleSubChange} style={{ marginBottom: 16, width: "100%", fontSize: 16 }}>
                {subscriptions.map(sub => (
                  <option key={sub.subscriptionId} value={sub.subscriptionId}>
                    {sub.displayName} ({sub.subscriptionId})
                  </option>
                ))}
              </select>
            </>
          )}

          <button
            style={{
              ...styles.button,
              opacity: account ? 1 : 0.6,
              pointerEvents: account ? "auto" : "none",
              marginBottom: 10,
            }}
            onClick={onScanOrphaned}
            disabled={!account || isLoading || selectedSubs.length === 0}
          >
            {isLoading ? "Scanning..." : "Scan for Orphaned Resources"}
          </button>
          <button
            style={{
              ...styles.button,
              opacity: account ? 1 : 0.6,
              pointerEvents: account ? "auto" : "none",
              marginBottom: 30,
              background: "linear-gradient(90deg, #ff512f 0%, #dd2476 100%)"
            }}
            onClick={onScanDeprecated}
            disabled={!account || isLoading || selectedSubs.length === 0}
          >
            {isLoading ? "Scanning..." : "Scan for Deprecated Resources"}
          </button>

          {error && (
            <div style={{ color: "#c00", marginBottom: 12 }}>{error}</div>
          )}
          <div style={styles.sectionTitle}>Detected Resources</div>
          {resources.length === 0 ? (
            <div style={{ color: "#999", marginBottom: 20 }}>
              No orphaned or deprecated resources detected yet.
            </div>
          ) : (
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Name</th>
                  <th style={styles.th}>Type</th>
                  <th style={styles.th}>Status</th>
                </tr>
              </thead>
              <tbody>
                {resources.map((res, idx) => (
                  <tr key={idx}>
                    <td style={styles.td}>{res.name}</td>
                    <td style={styles.td}>{res.type}</td>
                    <td style={styles.td}>
                      {res.status}
                      {res.status === "orphaned" && (
                        <span style={styles.status}>Orphaned</span>
                      )}
                      {res.status === "deprecated" && (
                        <span style={{ ...styles.status, background: "#ffebee", color: "#c62828" }}>
                          Deprecated
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div style={styles.sectionTitle}>Approval Inbox</div>
          {approvals.length === 0 ? (
            <div style={{ color: "#999", marginBottom: 30 }}>
              No actions pending approval.
            </div>
          ) : (
            <ul style={styles.approvalList}>
              {approvals.map((app, idx) => (
                <li style={styles.approvalItem} key={idx}>
                  <span>
                    <b>{app.name}</b> ({app.type}) - {app.action}
                    <span style={{ ...styles.status, background: "#fffde7", color: "#fbc02d" }}>
                      {app.status}
                    </span>
                  </span>
                  <button
                    style={styles.approveButton}
                    disabled={isLoading}
                    onClick={() => onApprove(app)}
                  >
                    Approve
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;