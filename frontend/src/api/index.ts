// Basic API wrapper for backend
export async function fetchOrphanedResources() {
    const res = await fetch('/api/scan/orphaned');
    return await res.json();
}
export async function fetchDeprecatedResources() {
    const res = await fetch('/api/scan/deprecated');
    return await res.json();
}
export async function approveDeleteOrphaned(resources: any[]) {
    const res = await fetch('/api/delete/orphaned', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ resources })
    });
    return await res.json();
}
export async function approveUpgradeDeprecated(resources: any[]) {
    const res = await fetch('/api/upgrade/deprecated', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ resources })
    });
    return await res.json();
}