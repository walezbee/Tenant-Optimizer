// API wrapper for backend with authentication
const API_BASE = window.location.origin; // Uses same domain as frontend

async function apiCall(endpoint: string, options: RequestInit = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });
    
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API call failed: ${response.status} ${errorText}`);
    }
    
    return await response.json();
}

export async function fetchSubscriptions(armToken: string) {
    return apiCall('/api/subscriptions', {
        headers: {
            'Authorization': `Bearer ${armToken}`,
        },
    });
}

export async function fetchOrphanedResources(armToken: string, subscriptions: string[]) {
    return apiCall('/api/scan/orphaned', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${armToken}`,
        },
        body: JSON.stringify({ subscriptions }),
    });
}

export async function fetchDeprecatedResources(armToken: string, subscriptions: string[]) {
    return apiCall('/api/scan/deprecated', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${armToken}`,
        },
        body: JSON.stringify({ subscriptions }),
    });
}

export async function approveDeleteOrphaned(armToken: string, approvalPayload: any) {
    return apiCall('/api/delete/orphaned', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${armToken}`,
        },
        body: JSON.stringify(approvalPayload),
    });
}

export async function approveUpgradeDeprecated(armToken: string, approvalPayload: any) {
    return apiCall('/api/upgrade/deprecated', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${armToken}`,
        },
        body: JSON.stringify(approvalPayload),
    });
}