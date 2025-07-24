import React, { useState } from 'react';
import { approveDeleteOrphaned, approveUpgradeDeprecated } from '../api';

export const ApprovalInbox = () => {
  const [pending, setPending] = useState<any[]>([
    // Example static data; replace with real fetch from backend
    { id: 'res-123', name: 'orphaned-disk', type: 'disk', action: 'delete' },
    { id: 'res-456', name: 'deprecated-sql', type: 'sql', action: 'upgrade' }
  ]);
  const handleApprove = async (res: any) => {
    if (res.action === 'delete') {
      await approveDeleteOrphaned([res]);
    } else if (res.action === 'upgrade') {
      await approveUpgradeDeprecated([res]);
    }
    setPending(pending.filter(r => r.id !== res.id));
  };
  return (
    <div>
      <h3>Approval Inbox</h3>
      <ul>
        {pending.map(res => (
          <li key={res.id}>
            {res.name} ({res.type}) - {res.action}
            <button onClick={() => handleApprove(res)}>Approve</button>
          </li>
        ))}
      </ul>
    </div>
  );
};