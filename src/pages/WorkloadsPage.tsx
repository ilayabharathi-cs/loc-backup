import React, { useState, useEffect } from 'react';
import { v11Api } from '../api/v11';
import type { Workload } from '../api/v11';

export const WorkloadsPage: React.FC = () => {
  const [workloads, setWorkloads] = useState<Workload[]>([]);
  const [selectedWorkload, setSelectedWorkload] = useState<Workload | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [protecting, setProtecting] = useState<boolean>(false);
  const [discoveryClient, setDiscoveryClient] = useState<string>('1');
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadWorkloads = async () => {
    setLoading(true);
    try {
      const data = await v11Api.getWorkloads();
      setWorkloads(data);
      if (data.length > 0 && !selectedWorkload) {
        setSelectedWorkload(data[0]);
      }
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkloads();
  }, []);

  const handleDiscover = async () => {
    setLoading(true);
    setActionMessage('Scanning client endpoint for application workloads...');
    try {
      const items = await v11Api.discoverWorkloads(discoveryClient);
      setActionMessage(`Discovered ${items.length} workload components.`);
      await loadWorkloads();
    } catch (e: any) {
      setActionMessage('Discovery error: ' + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  };

  const handleProtectNow = async (w: Workload) => {
    setProtecting(true);
    setActionMessage(`Executing application-aware backup for ${w.name}...`);
    try {
      const res = await v11Api.protectWorkload(w.workload_id, 'FULL');
      setActionMessage(`Backup succeeded! Consistency: ${res.consistency_state}, Bytes: ${res.total_bytes}`);
      await loadWorkloads();
    } catch (e: any) {
      setActionMessage('Backup error: ' + (e.response?.data?.detail || e.message));
    } finally {
      setProtecting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Title Bar */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span className="bg-[#000080] text-white px-1.5 py-0.5 rounded text-[10px]">V11</span>
            Application-Aware Workload Management Console
          </h2>
          <p className="text-[11px] text-gray-700">
            Provider-driven application consistency, database quiescing, and transaction log protection
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <input
            type="text"
            className="win-inset px-2 py-1 text-xs bg-white w-24"
            placeholder="Client ID"
            value={discoveryClient}
            onChange={(e) => setDiscoveryClient(e.target.value)}
          />
          <button onClick={handleDiscover} className="win-btn px-3 py-1 font-bold">
            Scan Workloads
          </button>
          <button onClick={loadWorkloads} className="win-btn px-3 py-1">
            Refresh
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-xs font-semibold">
          {actionMessage}
        </div>
      )}

      {/* Main Grid: Workload List + Inspector */}
      <div className="flex-1 flex gap-2 min-h-0">
        {/* Table View */}
        <div className="flex-1 win-inset bg-white overflow-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="bg-[#e0e0e0] sticky top-0 border-b border-[#808080]">
              <tr>
                <th className="p-1.5 border-r border-[#808080]">Workload ID</th>
                <th className="p-1.5 border-r border-[#808080]">Type</th>
                <th className="p-1.5 border-r border-[#808080]">Application Name</th>
                <th className="p-1.5 border-r border-[#808080]">Consistency Capability</th>
                <th className="p-1.5 border-r border-[#808080]">Protection State</th>
                <th className="p-1.5 border-r border-[#808080]">Status</th>
                <th className="p-1.5 border-r border-[#808080]">Last Protected</th>
                <th className="p-1.5">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && workloads.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-4 text-center text-gray-500">
                    Loading application workloads...
                  </td>
                </tr>
              ) : workloads.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-4 text-center text-gray-500">
                    No workloads discovered. Enter a Client ID above and click "Scan Workloads".
                  </td>
                </tr>
              ) : (
                workloads.map((w) => {
                  const isSelected = selectedWorkload?.workload_id === w.workload_id;
                  return (
                    <tr
                      key={w.workload_id}
                      onClick={() => setSelectedWorkload(w)}
                      className={`cursor-pointer hover:bg-[#e8f0fe] border-b border-gray-100 ${
                        isSelected ? 'bg-[#000080] text-white hover:bg-[#000080]' : ''
                      }`}
                    >
                      <td className="p-1.5 font-mono">{w.workload_id}</td>
                      <td className="p-1.5 font-semibold">{w.type}</td>
                      <td className="p-1.5">{w.name}</td>
                      <td className="p-1.5">
                        <span className={`px-1 py-0.5 rounded text-[10px] font-mono ${
                          w.consistency_capability === 'APPLICATION_CONSISTENT'
                            ? 'bg-green-100 text-green-800'
                            : w.consistency_capability === 'FILE_SYSTEM_CONSISTENT'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-yellow-100 text-yellow-800'
                        }`}>
                          {w.consistency_capability}
                        </span>
                      </td>
                      <td className="p-1.5">
                        <span className={`px-1 py-0.5 font-bold ${
                          w.protection_state === 'PROTECTED' ? 'text-green-700' : 'text-amber-700'
                        }`}>
                          {w.protection_state}
                        </span>
                      </td>
                      <td className="p-1.5">{w.status}</td>
                      <td className="p-1.5 font-mono text-[11px]">
                        {w.last_protected_at ? new Date(w.last_protected_at).toLocaleString() : 'Never'}
                      </td>
                      <td className="p-1.5">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleProtectNow(w);
                          }}
                          disabled={protecting}
                          className="win-btn px-2 py-0.5 text-[10px] font-bold text-black"
                        >
                          Protect Now
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Inspector Pane */}
        {selectedWorkload && (
          <div className="w-80 win-outset bg-[#dcdcdc] p-2.5 flex flex-col gap-2 overflow-auto">
            <h3 className="font-bold text-xs border-b border-gray-400 pb-1">
              Workload Diagnostic Inspector
            </h3>
            <div>
              <span className="font-bold">ID:</span> <span className="font-mono">{selectedWorkload.workload_id}</span>
            </div>
            <div>
              <span className="font-bold">Name:</span> {selectedWorkload.name}
            </div>
            <div>
              <span className="font-bold">Engine Type:</span> {selectedWorkload.type}
            </div>
            <div>
              <span className="font-bold">Client ID:</span> {selectedWorkload.client_id}
            </div>
            <div>
              <span className="font-bold">Health:</span> {selectedWorkload.health}
            </div>
            <div>
              <span className="font-bold">Consistency:</span> {selectedWorkload.consistency_capability}
            </div>
            <div>
              <span className="font-bold">Last Verified:</span>{' '}
              {selectedWorkload.last_verified_at ? new Date(selectedWorkload.last_verified_at).toLocaleString() : 'Not verified'}
            </div>

            <div className="mt-2">
              <span className="font-bold">Configuration JSON:</span>
              <pre className="win-inset bg-white p-1 text-[10px] font-mono overflow-auto max-h-36">
                {JSON.stringify(selectedWorkload.config || {}, null, 2)}
              </pre>
            </div>

            <div className="mt-1">
              <span className="font-bold">Metadata Attributes:</span>
              <pre className="win-inset bg-white p-1 text-[10px] font-mono overflow-auto max-h-36">
                {JSON.stringify(selectedWorkload.metadata || {}, null, 2)}
              </pre>
            </div>

            <button
              onClick={() => handleProtectNow(selectedWorkload)}
              disabled={protecting}
              className="win-btn mt-2 py-1 font-bold bg-[#008000] text-white"
            >
              Trigger Consistency Backup
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
