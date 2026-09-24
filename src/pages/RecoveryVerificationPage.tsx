import React, { useState, useEffect } from 'react';
import { v11Api } from '../api/v11';
import type { RecoveryVerification } from '../api/v11';

export const RecoveryVerificationPage: React.FC = () => {
  const [verifications, setVerifications] = useState<RecoveryVerification[]>([]);
  const [selectedVerif, setSelectedVerif] = useState<RecoveryVerification | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [retrying, setRetrying] = useState<boolean>(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await v11Api.getRecoveryVerifications();
      setVerifications(data);
      if (data.length > 0 && !selectedVerif) {
        setSelectedVerif(data[0]);
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

  const handleRetry = async (verificationId: string) => {
    setRetrying(true);
    setActionMsg(`Retrying verification execution ${verificationId}...`);
    try {
      const res = await v11Api.retryVerification(verificationId);
      setActionMsg(`Retry completed with status: ${res.status}`);
      await loadData();
    } catch (e: any) {
      setActionMsg('Retry failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Header */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span className="bg-[#000080] text-white px-1.5 py-0.5 rounded text-[10px]">V11</span>
            Synthetic Recovery & Automated Restore Verification Center
          </h2>
          <p className="text-[11px] text-gray-700">
            Isolated sandbox extraction, CAS object checksum validation, and payload integrity verification
          </p>
        </div>
        <button onClick={loadData} className="win-btn px-3 py-1 font-bold">
          Refresh Queue
        </button>
      </div>

      {actionMsg && (
        <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-xs font-semibold">
          {actionMsg}
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 flex gap-2 min-h-0">
        <div className="flex-1 win-inset bg-white overflow-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="bg-[#e0e0e0] sticky top-0 border-b border-[#808080]">
              <tr>
                <th className="p-1.5 border-r border-[#808080]">Verification ID</th>
                <th className="p-1.5 border-r border-[#808080]">Workload</th>
                <th className="p-1.5 border-r border-[#808080]">Recovery Point</th>
                <th className="p-1.5 border-r border-[#808080]">Verification Type</th>
                <th className="p-1.5 border-r border-[#808080]">Status</th>
                <th className="p-1.5 border-r border-[#808080]">Duration</th>
                <th className="p-1.5 border-r border-[#808080]">Completed At</th>
                <th className="p-1.5">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && verifications.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-4 text-center text-gray-500">
                    Loading verification history...
                  </td>
                </tr>
              ) : verifications.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-4 text-center text-gray-500">
                    No automated recovery verifications executed yet. Trigger a verification from Workloads.
                  </td>
                </tr>
              ) : (
                verifications.map((v) => {
                  const isSelected = selectedVerif?.verification_id === v.verification_id;
                  const isVerified = v.status === 'VERIFIED';
                  return (
                    <tr
                      key={v.verification_id}
                      onClick={() => setSelectedVerif(v)}
                      className={`cursor-pointer hover:bg-[#e8f0fe] border-b border-gray-100 ${
                        isSelected ? 'bg-[#000080] text-white hover:bg-[#000080]' : ''
                      }`}
                    >
                      <td className="p-1.5 font-mono">{v.verification_id}</td>
                      <td className="p-1.5">{v.workload_id}</td>
                      <td className="p-1.5 font-mono">RP #{v.recovery_point_id}</td>
                      <td className="p-1.5 font-semibold">{v.verification_type}</td>
                      <td className="p-1.5">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          isVerified ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {v.status}
                        </span>
                      </td>
                      <td className="p-1.5 font-mono">{v.duration_ms.toFixed(1)} ms</td>
                      <td className="p-1.5 text-[11px]">
                        {v.completed_at ? new Date(v.completed_at).toLocaleString() : 'Running...'}
                      </td>
                      <td className="p-1.5">
                        {!isVerified && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRetry(v.verification_id);
                            }}
                            disabled={retrying}
                            className="win-btn px-2 py-0.5 text-[10px] text-black font-bold"
                          >
                            Retry
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

        {/* Detailed Verification Inspector */}
        {selectedVerif && (
          <div className="w-80 win-outset bg-[#dcdcdc] p-2.5 flex flex-col gap-2 overflow-auto">
            <h3 className="font-bold text-xs border-b border-gray-400 pb-1">
              Sandbox Execution Breakdown
            </h3>
            <div>
              <span className="font-bold">ID:</span> <span className="font-mono">{selectedVerif.verification_id}</span>
            </div>
            <div>
              <span className="font-bold">Sandbox Target:</span>{' '}
              <span className="font-mono text-[10px] break-all">{selectedVerif.sandbox_path}</span>
            </div>
            <div>
              <span className="font-bold">Status:</span> {selectedVerif.status}
            </div>
            {selectedVerif.error_message && (
              <div className="text-red-700 bg-red-50 p-1 win-inset">
                <span className="font-bold">Diagnostic:</span> {selectedVerif.error_message}
              </div>
            )}

            <div className="mt-2">
              <span className="font-bold">Execution Steps:</span>
              <div className="win-inset bg-white p-1 text-[11px] flex flex-col gap-1 max-h-48 overflow-auto mt-1">
                {(selectedVerif.steps || []).length === 0 ? (
                  <div className="text-gray-500 italic p-1">No individual step records logged.</div>
                ) : (
                  (selectedVerif.steps || []).map((s, idx) => (
                    <div key={idx} className="flex justify-between items-center border-b border-gray-100 py-0.5">
                      <span>{s.step_name}</span>
                      <span className={`font-bold px-1 rounded text-[9px] ${
                        s.status === 'PASSED' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {s.status}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="mt-2">
              <span className="font-bold">Evidence Payload:</span>
              <pre className="win-inset bg-white p-1 text-[10px] font-mono overflow-auto max-h-36">
                {JSON.stringify(selectedVerif.evidence || {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
