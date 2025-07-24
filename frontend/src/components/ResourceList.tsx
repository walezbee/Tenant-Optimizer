import React from 'react';

export const ResourceList = ({ resources }: { resources: any[] }) => (
  <div>
    <h3>Detected Resources</h3>
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {resources.map(res => (
          <tr key={res.id}>
            <td>{res.name}</td>
            <td>{res.type}</td>
            <td>{res.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);