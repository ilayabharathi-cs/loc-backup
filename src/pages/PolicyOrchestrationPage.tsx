import React, { useState, useEffect } from 'react';
import { v11Api } from '../api/v11';
import type { PolicyLifecycle } from '../api/v11';

export const PolicyOrchestrationPage: React.FC = () => {
  const [lifecycles, setLifecycles] = useState<PolicyLifecycle[]>([]);
  const [selectedLc, setSelectedLc] = useState<PolicyLifecycle | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await v11Api.getPolicyLifecycles();
      setLifecycles(data);
      if (data.length > 0 && !selectedLc) {
        setSelectedLc(data[0]);
      }
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApprove = async (id: number) => {
    try {
      const res = await v11Api.approvePolicyVersion(id, 'Approved via Win95 Orchestration Console');
      setActionMsg(`Policy version ${res.version} approved!`);
      await loadData();
    } catch (e: any) {
      setActionMsg('Approval error: ' + (e.response?.data?.detail || e.message));
    }
  };

  const handleActivate = async (id: number) => {
    try {
      const res = await v11Api.activatePolicyVersion(id);
      setActionMsg(`Policy version ${res.version} activated successfully!`);
      await loadData();
    } catch (e: any) {
      setActionMsg('Activation error: ' + (e.response?.data?.detail || e.message));
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span className="bg-[#000080] text-white px-1.5 py-0.5 rounded text-[10px]">V11</span>
            Policy Orchestration & Lifecycle Governance
          </h2>
          <p className="text-[11px] text-gray-700">
            Immutable versioning, formal approval gates, deterministic rollbacks, and affected resource tracking
          </p>
        </div>
        <button onClick={loadData} className="win-btn px-3 py-1 font-bold">
          Refresh
        </button>
      </div>

      {actionMsg && (
        <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-xs font-semibold">
          {actionMsg}
        </div>
      )}

      <div className="flex-1 flex gap-2 min-h-0">
        <div className="flex-1 win-inset bg-white overflow-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="bg-[#e0e0e0] sticky top-0 border-b border-[#808080]">
              <tr>
                <th className="p-1.5 border-r border-[#808080]">Policy ID</th>
                <th className="p-1.5 border-r border-[#808080]">Version</th>
                <th className="p-1.5 border-r border-[#808080]">State</th>
                <th className="p-1.5 border-r border-[#808080]">Created By</th>
                <th className="p-1.5 border-r border-[#808080]">Effective At</th>
                <th className="p-1.5">Lifecycle Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && lifecycles.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-4 text-center text-gray-500">
                    Loading policy lifecycles...
                  </td>
                </tr>
              ) : lifecycles.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-4 text-center text-gray-500">
                    No policy versions registered yet.
                  </td>
                </tr>
              ) : (
                lifecycles.map((lc) => {
                  const isSelected = selectedLc?.id === lc.id;
                  const isActive = lc.lifecycle_state === 'ACTIVE';
                  const isApproved = lc.lifecycle_state === 'APPROVED';
                  const isDraft = lc.lifecycle_state === 'DRAFT';
                  return (
                    <tr
                      key={lc.id}
                      onClick={() => setSelectedLc(lc)}
                      className={`cursor-pointer hover:bg-[#e8f0fe] border-b border-gray-100 ${
                        isSelected ? 'bg-[#000080] text-white hover:bg-[#000080]' : ''
                      }`}
                    >
                      <td className="p-1.5 font-mono">{lc.policy_id}</td>
                      <td className="p-1.5 font-bold">v{lc.version}</td>
                      <td className="p-1.5">
                        <span className={`px-1.5 py-0.5 rounded font-bold text-[10px] ${
                          isActive
                            ? 'bg-green-100 text-green-800'
                            : isApproved
                            ? 'bg-blue-100 text-blue-800'
                            : isDraft
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {lc.lifecycle_state}
                        </span>
                      </td>
                      <td className="p-1.5">{lc.created_by}</td>
                      <td className="p-1.5 text-[11px]">
                        {lc.effective_at ? new Date(lc.effective_at).toLocaleString() : 'Pending'}
                      </td>
                      <td className="p-1.5 flex gap-1">
                        {isDraft && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleApprove(lc.id);
                            }}
                            className="win-btn px-2 py-0.5 text-[10px] text-black font-bold"
                          >
                            Approve
                          </button>
                        )}
                        {isApproved && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleActivate(lc.id);
                            }}
                            className="win-btn px-2 py-0.5 text-[10px] text-black font-bold"
                          >
                            Activate
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {selectedLc && (
          <div className="w-80 win-outset bg-[#dcdcdc] p-2.5 flex flex-col gap-2 overflow-auto">
            <h3 className="font-bold text-xs border-b border-gray-400 pb-1">
              Policy Version Inspector
            </h3>
            <div>
              <span className="font-bold">Policy:</span> {selectedLc.policy_id}
            </div>
            <div>
              <span className="font-bold">Version:</span> v{selectedLc.version}
            </div>
            <div>
              <span className="font-bold">Lifecycle State:</span> {selectedLc.lifecycle_state}
            </div>
            <div>
              <span className="font-bold">Author:</span> {selectedLc.created_by}
            </div>

            <div className="mt-2">
              <span className="font-bold">Definition JSON:</span>
              <pre className="win-inset bg-white p-1 text-[10px] font-mono overflow-auto max-h-56 mt-1">
                {JSON.stringify(selectedLc.definition, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
