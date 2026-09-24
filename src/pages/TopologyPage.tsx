import React, { useState, useEffect } from 'react';
import { getRepositories, getTopology } from '../api/v7';
import type { StorageRepository, TopologyStatus } from '../api/v7';

export const TopologyPage: React.FC = () => {
  const [repos, setRepos] = useState<StorageRepository[]>([]);
  const [topology, setTopology] = useState<TopologyStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [rRes, tRes] = await Promise.all([getRepositories(), getTopology()]);
      if (rRes.success) setRepos(rRes.data);
      if (tRes.success) setTopology(tRes.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-3 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Header Panel */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold">Storage Repository Topology & 3-2-1 Architecture</h2>
          <p className="text-[11px] text-gray-700">Physical and logical multi-repository distribution matrix</p>
        </div>
        <div className="flex items-center gap-2">
          {loading && <span className="text-[11px] text-gray-500 font-mono">Syncing...</span>}
          <button onClick={loadData} className="win-btn px-3 py-1 font-bold">Refresh Topology</button>
        </div>
      </div>

      {/* 3-2-1 Rule Evaluation Badge Box */}
      <div className="win-outset p-3 bg-white flex flex-col gap-2">
        <div className="flex items-center justify-between border-b pb-2">
          <div className="flex items-center gap-3">
            <span className="font-bold text-sm">3-2-1 Backup Protection Status:</span>
            {topology?.is_compliant ? (
              <span className="px-3 py-1 bg-[#008000] text-white font-bold font-mono text-xs">
                ● 3-2-1 COMPLIANT
              </span>
            ) : (
              <span className="px-3 py-1 bg-[#800000] text-white font-bold font-mono text-xs">
                ▲ NOT COMPLIANT
              </span>
            )}
          </div>
          <span className="text-gray-600 text-[11px]">
            {topology?.recommendation}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-3 pt-1">
          <div className="win-inset p-2 bg-[#f8f8f8]">
            <div className="font-bold text-[#000080] mb-1">1. Three (3) Total Copies</div>
            <div className="font-mono text-sm font-bold">{topology?.total_copies || 0} / 3 Copies</div>
            <div className="text-[10px] text-gray-600 mt-1">Configured repositories available for data storage.</div>
          </div>
          <div className="win-inset p-2 bg-[#f8f8f8]">
            <div className="font-bold text-[#000080] mb-1">2. Two (2) Different Media Types</div>
            <div className="font-mono text-sm font-bold">{topology?.media_types_count || 0} / 2 Media Types</div>
            <div className="text-[10px] text-gray-600 mt-1">Found types: {topology?.media_types.join(', ') || 'None'}.</div>
          </div>
          <div className="win-inset p-2 bg-[#f8f8f8]">
            <div className="font-bold text-[#000080] mb-1">3. One (1) Offsite / Remote Copy</div>
            <div className={`font-mono text-sm font-bold ${topology?.has_offsite ? 'text-[#008000]' : 'text-[#800000]'}`}>
              {topology?.has_offsite ? 'YES (Verified Offsite Target)' : 'NO OFFSITE REPOSITORY'}
            </div>
            <div className="text-[10px] text-gray-600 mt-1">Targets: {topology?.offsite_repositories.join(', ') || 'None'}.</div>
          </div>
        </div>
      </div>

      {/* Visual Topology Diagram */}
      <div className="win-outset p-4 bg-[#c0c0c0] flex flex-col gap-4">
        <div className="font-bold text-xs border-b border-[#808080] pb-1">Topology Map</div>
        
        <div className="flex items-center justify-around py-4">
          {/* Workstations / Agents Node */}
          <div className="win-outset p-3 bg-white w-44 flex flex-col items-center gap-1.5 shadow-md">
            <div className="w-10 h-10 bg-[#000080] text-white flex items-center justify-center font-bold text-lg">PC</div>
            <div className="font-bold text-center">Windows Clients</div>
            <div className="text-[10px] text-gray-600 text-center font-mono">Agent TLS Encrypted</div>
            <span className="px-1.5 py-0.5 bg-[#008000] text-white font-mono text-[9px] font-bold">ONLINE</span>
          </div>

          <div className="text-xl font-bold text-gray-600">➔</div>

          {/* Primary Repository */}
          <div className="win-outset p-3 bg-white w-52 flex flex-col items-center gap-1.5 shadow-md">
            <div className="w-10 h-10 bg-[#008080] text-white flex items-center justify-center font-bold text-lg">PRI</div>
            <div className="font-bold text-center">{topology?.primary_repositories[0] || 'Primary Repo'}</div>
            <div className="text-[10px] text-gray-600 text-center font-mono">Local CAS / Deduplication</div>
            <span className="px-1.5 py-0.5 bg-[#008000] text-white font-mono text-[9px] font-bold">ONLINE</span>
          </div>

          <div className="text-xl font-bold text-gray-600">➔</div>

          {/* Secondary Repository */}
          <div className="win-outset p-3 bg-white w-52 flex flex-col items-center gap-1.5 shadow-md">
            <div className="w-10 h-10 bg-[#708090] text-white flex items-center justify-center font-bold text-lg">SEC</div>
            <div className="font-bold text-center">{topology?.secondary_repositories[0] || 'Secondary NAS'}</div>
            <div className="text-[10px] text-gray-600 text-center font-mono">Secondary Replicated Copy</div>
            <span className={`px-1.5 py-0.5 text-white font-mono text-[9px] font-bold ${topology?.secondary_repositories.length ? 'bg-[#008000]' : 'bg-[#800000]'}`}>
              {topology?.secondary_repositories.length ? 'ONLINE' : 'NOT CONFIGURED'}
            </span>
          </div>

          <div className="text-xl font-bold text-gray-600">➔</div>

          {/* Offsite Cloud / S3 Repository */}
          <div className="win-outset p-3 bg-white w-52 flex flex-col items-center gap-1.5 shadow-md">
            <div className="w-10 h-10 bg-[#4b0082] text-white flex items-center justify-center font-bold text-lg">OFF</div>
            <div className="font-bold text-center">{topology?.offsite_repositories[0] || 'Offsite / S3 Cloud'}</div>
            <div className="text-[10px] text-gray-600 text-center font-mono">Remote Disaster Recovery</div>
            <span className={`px-1.5 py-0.5 text-white font-mono text-[9px] font-bold ${topology?.has_offsite ? 'bg-[#008000]' : 'bg-[#800000]'}`}>
              {topology?.has_offsite ? 'ONLINE' : 'MISSING'}
            </span>
          </div>
        </div>
      </div>

      {/* Repositories Detail Grid */}
      <div className="flex-1 win-inset bg-white p-2 overflow-auto">
        <div className="font-bold text-xs mb-2">Registered Storage Repositories ({repos.length})</div>
        <table className="w-full border-collapse text-[11px] text-left">
          <thead>
            <tr className="bg-[#000080] text-white">
              <th className="p-1.5 border border-[#808080]">ID</th>
              <th className="p-1.5 border border-[#808080]">Name</th>
              <th className="p-1.5 border border-[#808080]">Type</th>
              <th className="p-1.5 border border-[#808080]">Path / Endpoint</th>
              <th className="p-1.5 border border-[#808080]">Protection Mode</th>
              <th className="p-1.5 border border-[#808080]">Used / Total</th>
              <th className="p-1.5 border border-[#808080]">Status</th>
            </tr>
          </thead>
          <tbody>
            {repos.map(r => (
              <tr key={r.id} className="border-b border-[#e0e0e0] hover:bg-[#f5f5f5]">
                <td className="p-1 font-mono font-bold">#{r.id}</td>
                <td className="p-1 font-bold">{r.name}</td>
                <td className="p-1 font-mono">{r.repository_type}</td>
                <td className="p-1 font-mono text-[10px]">{r.endpoint || r.path}</td>
                <td className="p-1 font-mono">{r.protection_mode}</td>
                <td className="p-1 font-mono">{formatBytes(r.used_bytes)} / {formatBytes(r.total_bytes)}</td>
                <td className="p-1">
                  <span className={`px-1.5 py-0.5 text-[9px] font-bold font-mono text-white ${
                    r.status === 'ONLINE' ? 'bg-[#008000]' :
                    r.status === 'MAINTENANCE' ? 'bg-[#d4a017]' : 'bg-[#800000]'
                  }`}>
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
