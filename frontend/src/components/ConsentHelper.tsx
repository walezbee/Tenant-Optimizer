import React from 'react';

interface ConsentHelperProps {
  error: string | null;
  onRetry: () => void;
}

export const ConsentHelper: React.FC<ConsentHelperProps> = ({ error, onRetry }) => {
  const isConsentError = error && (
    error.includes('AADSTS65001') || 
    error.includes('consent_required') ||
    error.includes('admin_consent_required')
  );

  if (!isConsentError) return null;

  const generateAdminConsentUrl = () => {
    const clientId = '9a164f91-1339-4504-b38e-cf089a90f6fb';
    const redirectUri = encodeURIComponent('https://tenant-optimizer-web.azurewebsites.net');
    // Add state parameter to track consent completion
    const state = encodeURIComponent('admin_consent_completed');
    return `https://login.microsoftonline.com/common/adminconsent?client_id=${clientId}&redirect_uri=${redirectUri}&state=${state}`;
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      alert('Admin consent URL copied to clipboard!');
    } catch (err) {
      console.error('Failed to copy: ', err);
    }
  };

  return (
    <div style={{
      backgroundColor: '#fff3cd',
      border: '1px solid #ffeaa7',
      borderRadius: '8px',
      padding: '16px',
      margin: '16px 0',
      maxWidth: '600px'
    }}>
      <h3 style={{ color: '#856404', marginTop: 0 }}>🔐 Admin Consent Required</h3>
      
      <p style={{ color: '#856404' }}>
        Your organization's administrator needs to grant consent <strong>once</strong> for this application to access Azure resources.
        After consent is granted, all users in your organization can access the app.
      </p>

      <div style={{ marginBottom: '16px' }}>
        <strong>What to do:</strong>
        <ol style={{ color: '#856404' }}>
          <li>Share the admin consent URL below with your IT administrator</li>
          <li>Ask them to visit the URL and grant consent (one-time setup)</li>
          <li>Try logging in again after consent is granted</li>
        </ol>
      </div>

      <div style={{ marginBottom: '12px' }}>
        <strong>Universal Admin Consent URL (works for any tenant):</strong>
      </div>

      <div style={{ 
        backgroundColor: '#f8f9fa', 
        padding: '12px', 
        borderRadius: '4px',
        fontFamily: 'monospace',
        fontSize: '12px',
        wordBreak: 'break-all',
        marginBottom: '12px'
      }}>
        {generateAdminConsentUrl()}
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button
          onClick={() => copyToClipboard(generateAdminConsentUrl())}
          style={{
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          📋 Copy Admin Consent URL
        </button>
        
        <button
          onClick={() => window.open(generateAdminConsentUrl(), '_blank')}
          style={{
            backgroundColor: '#28a745',
            color: 'white',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          🔗 Open Admin Consent (if you're an admin)
        </button>
        
        <button
          onClick={onRetry}
          style={{
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          🔄 Try Again
        </button>
      </div>

      <details style={{ marginTop: '16px' }}>
        <summary style={{ cursor: 'pointer', color: '#856404' }}>
          📋 Instructions for IT Administrators
        </summary>
        <div style={{ marginTop: '8px', fontSize: '14px', color: '#856404' }}>
          <p><strong>As an IT Administrator, follow these steps:</strong></p>
          <ol>
            <li>Click the admin consent URL above (it works for any Azure tenant)</li>
            <li>Sign in with your administrator account</li>
            <li>Review the requested permissions:
              <ul>
                <li><strong>Azure Service Management:</strong> Read Azure resources</li>
                <li><strong>Microsoft Graph:</strong> Read basic user profile</li>
              </ul>
            </li>
            <li>Click "Accept" to grant consent for your organization</li>
            <li>Inform users they can now access the application</li>
          </ol>
          <p><em>Note: This is a one-time setup per organization. The same URL works for administrators from any Azure tenant.</em></p>
        </div>
      </details>
    </div>
  );
};

export default ConsentHelper;
