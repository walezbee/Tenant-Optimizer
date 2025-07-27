import React, { useEffect, useState } from "react";
import { PublicClientApplication, AccountInfo } from "@azure/msal-browser";

// === MSAL Configuration ===
// Replace these with your real values!
const msalConfig = {
  auth: {
    clientId: "9a164f91-1339-4504-b38e-cf089a90f6fb", // <-- Replace with your SPA App Registration's clientId
    authority: "https://login.microsoftonline.com/36d8a1ac-8d2d-4744-b032-9074fd822ec5", // <-- Replace with your Tenant ID
    redirectUri: "https://tenant-optimizer-web.azurewebsites.net/", // <-- Or your localhost for dev
  },
};
const apiScope = "api://b0a762fa-2904-4726-b991-871dbfe84f28/user_impersonation"; // <-- Replace with your API App Registration's clientId

const msalInstance = new PublicClientApplication(msalConfig);

const styles = {
  body: {
    fontFamily: "Segoe UI, Arial, sans-serif",
    background: "linear-gradient(120deg, #e0c3fc 0%, #8ec5fc 100%)",
    minHeight: "100vh",
    margin: 0,
    padding: 0,
  } as React.CSSProperties,
  container: {
    maxWidth: 700,
    margin: "40px auto",
    background: "white",
    borderRadius: 16,
    boxShadow: "0 2px 32px rgba(60,60,180,0.15)",
    padding: "32px 40px 40px 40px",
  },
  header: {
    fontSize: 38,
    fontWeight: 700,
    color: "#512da8",
    marginBottom: 10,
  },
  description: {
    fontSize: 18,
    fontWeight: 400,
    color: "#555",
    marginBottom: 34,
  },
  button: {
    background: "linear-gradient(90deg, #6a11cb 0%, #2575fc 100%)",
    color: "white",
    fontSize: 16,
    fontWeight: 600,
    border: "none",
    borderRadius: 7,
    padding: "12px 24px",
    margin: "0 10px 20px 0",
    cursor: "pointer",
    boxShadow: "0 2px 8px #6a11cb33",
    transition: "background 0.2s",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    margin: "24px 0",
  } as React.CSSProperties,
  th: {
    borderBottom: "2px solid #6a11cb",
    textAlign: "left" as const,
    padding: "8px",
    background: "#f3e7ff",
    color: "#512da8",
  },
  td: {
    padding: "8px",
    borderBottom: "1px solid #ddd",
    fontSize: 16,
  },
  sectionTitle: {
    marginTop: 32,
    marginBottom: 8,
    fontSize: 22,
    color: "#2575fc",
    fontWeight: 600,
  },
  approvalList: {
    listStyle: "none",
    padding: 0,
  },
  approvalItem: {
    background: "#e3f0ff",
    borderRadius: 7,
    padding: "8px 14px",
    marginBottom: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  approveButton: {
    background: "linear-gradient(90deg, #00c853 0%, #b2ff59 100%)",
    color: "#222",
    fontWeight: 600,
    border: "none",
    borderRadius: 6,
    padding: "7px 18px",
    cursor: "pointer",
    marginLeft: 12,
    fontSize: 15,
    boxShadow: "0 2px 6px #00c85344",
    transition: "background 0.2s",
  },
  signInOut: {
    float: "right" as "right",
    marginTop: -10,
    marginBottom: 28,
  },
  status: {
    padding: "4px 10px",
    borderRadius: 6,
    background: "#fff3e0",
    color: "#fb8c00",
    fontWeight: 500,
    fontSize: 14,
    marginLeft: 10,
  },
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
  // === MSAL state ===
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // === Data state ===
  const [resources, setResources] = useState<Resource[]>([]);
  const [approvals, setApprovals] = useState<ApprovalAction[]>([]);
  const [error, setError] = useState<string | null>(null);

  // On mount, check if user is signed in
  useEffect(() => {
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
  }, []);

  // Sign in/out handlers
  const signIn = async () => {
    await msalInstance.loginRedirect({ scopes: [apiScope] });
  };
  const signOut = () => {
    msalInstance.logoutRedirect();
  };

  // Acquire token
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

  // Scan for orphaned resources
  async function onScan() {
    setIsLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const resp = await fetch("/scan/orphaned", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error("Scan failed: " + resp.statusText);
      const data = await resp.json();
      // Example response processing (adapt this to your backend response)
      setResources(data.resources || []);
      setApprovals(data.approvals || []);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setIsLoading(false);
    }
  }

  // Approve action (delete or upgrade)
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
          body: JSON.stringify({ id: approval.id }),
        }
      );
      if (!resp.ok) throw new Error("Approval failed: " + resp.statusText);

      // Optionally, refetch data
      await onScan();
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setIsLoading(false);
    }
  }

  // --- UI ---
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
            <span>
              Tenant Optimizer is your AI-powered assistant for Azure Tenant organizations.
              It scans your environment to detect <b>orphaned</b> (unused) and <b>deprecated</b> (outdated) resources,
              helping you identify cost savings and improve security. The app guides you through reviewing, approving, and remediating these resources—
              <b>never deleting or upgrading anything automatically without your explicit approval</b>.
              <br />
              <br />
              <span style={{ color: "#2575fc" }}>
                Sign in with your Microsoft Entra ID (Azure AD) account to get started.
              </span>
            </span>
          </div>
          <button
            style={{
              ...styles.button,
              opacity: account ? 1 : 0.6,
              pointerEvents: account ? "auto" : "none",
              marginBottom: 30,
            }}
            onClick={onScan}
            disabled={!account || isLoading}
          >
            {isLoading ? "Scanning..." : "Scan for Orphaned Resources"}
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