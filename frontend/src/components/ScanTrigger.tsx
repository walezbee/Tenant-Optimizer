import React from 'react';
export const ScanTrigger = ({ onResults }: any) => {
  const scanOrphaned = async () => {
    const res = await fetch('/api/scan/orphaned');
    const data = await res.json();
    onResults(data);
  };
  return <button onClick={scanOrphaned}>Scan for Orphaned Resources</button>;
};