import React, { useState } from 'react';
import { ResourceList } from './ResourceList';
import { ApprovalInbox } from './ApprovalInbox';
import { ScanTrigger } from './ScanTrigger';

export const Dashboard = () => {
  const [resources, setResources] = useState([]);
  return (
    <div>
      <ScanTrigger onResults={setResources} />
      <ResourceList resources={resources} />
      <ApprovalInbox />
    </div>
  );
};