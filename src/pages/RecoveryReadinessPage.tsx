import React, { useState, useEffect } from 'react';
import { v11Api } from '../api/v11';
import type { RecoveryReadiness } from '../api/v11';

export const RecoveryReadinessPage: React.FC = () => {
  const [readinessList, setReadinessList] = useState<RecoveryReadiness[]>([]);
  const [selectedReadiness, setSelectedReadiness] = useState<RecoveryReadiness | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await v11Api.getAllReadiness();
      setReadinessList(data);
      if (data.length > 0 && !selectedReadiness) {
        setSelectedReadiness(data[0]);
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

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Title */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span className="bg-[#000080] text-white px-1.5 py-0.5 rounded text-[10px]">V11</span>
            Factual Recovery Readiness Intelligence Engine
          </h2>
          <p className="text-[11px] text-gray-700">
            Objective evaluation of 11 measurable signals: RPO, RTO, CAS integrity, replication, holds & verification
          </p>
        </div>
        <button onClick={loadData} className="win-btn px-3 py-1 font-bold">
          Re-evaluate All
        </button>
      </div>

      <div className="flex-1 flex gap-2 min-h-0">
        {/* Table View */}
        <div className="flex-1 win-inset bg-white overflow-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="bg-[#e0e0e0] sticky top-0 border-b border-[#808080]">
              <tr>
                <th className="p-1.5 border-r border-[#808080]">Workload ID</th>
                <th className="p-1.5 border-r border-[#808080]">Readiness State</th>
                <th className="p-1.5 border-r border-[#808080]">RPO Compliance</th>
                <th className="p-1.5 border-r border-[#808080]">Est. RTO</th>
                <th className="p-1.5 border-r border-[#808080]">Blocking Factors</th>
                <th className="p-1.5 border-r border-[#808080]">Degrading Factors</th>
                <th className="p-1.5">Evaluated At</th>
              </tr>
            </thead>
            <tbody>
              {loading && readinessList.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-4 text-center text-gray-500">
                    Evaluating recovery readiness signals...
                  </td>
                </tr>
              ) : readinessList.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-4 text-center text-gray-500">
                    No workloads found to evaluate.
                  </td>
                </tr>
              ) : (
                readinessList.map((r) => {
                  const isSelected = selectedReadiness?.workload_id === r.workload_id;
                  const isReady = r.readiness_state === 'READY';
                  const isDegraded = r.readiness_state === 'DEGRADED';
                  return (
                    <tr
                      key={r.workload_id}
                      onClick={() => setSelectedReadiness(r)}
                      className={`cursor-pointer hover:bg-[#e8f0fe] border-b border-gray-100 ${
                        isSelected ? 'bg-[#000080] text-white hover:bg-[#000080]' : ''
                      }`}
                    >
                      <td className="p-1.5 font-mono">{r.workload_id}</td>
                      <td className="p-1.5">
                        <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                          isReady
                            ? 'bg-green-100 text-green-800'
                            : isDegraded
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {r.readiness_state}
                        </span>
                      </td>
                      <td className="p-1.5 font-mono">{r.rpo_compliance_percent.toFixed(0)}%</td>
                      <td className="p-1.5 font-mono">{r.rto_estimate_seconds ? `${r.rto_estimate_seconds}s` : 'N/A'}</td>
                      <td className="p-1.5 text-red-600 font-semibold">{r.blocking_factors.length}</td>
                      <td className="p-1.5 text-yellow-600">{r.degrading_factors.length}</td>
                      <td className="p-1.5 text-[11px]">{new Date(r.evaluated_at).toLocaleTimeString()}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Breakdown Panel */}
        {selectedReadiness && (
          <div className="w-80 win-outset bg-[#dcdcdc] p-2.5 flex flex-col gap-2 overflow-auto">
            <h3 className="font-bold text-xs border-b border-gray-400 pb-1">
              Readiness Signal Explanation
            </h3>
            <div>
              <span className="font-bold">Workload:</span>{' '}
              <span className="font-mono">{selectedReadiness.workload_id}</span>
            </div>
            <div>
              <span className="font-bold">Overall Verdict:</span>{' '}
              <span className="font-bold">{selectedReadiness.readiness_state}</span>
            </div>

            {selectedReadiness.blocking_factors.length > 0 && (
              <div className="bg-red-50 p-2 win-inset border-l-4 border-red-600">
                <span className="font-bold text-red-800">Blocking Factors:</span>
                <ul className="list-disc pl-4 mt-1 text-[11px] text-red-700">
                  {selectedReadiness.blocking_factors.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>
            )}

            {selectedReadiness.degrading_factors.length > 0 && (
              <div className="bg-yellow-50 p-2 win-inset border-l-4 border-yellow-600">
                <span className="font-bold text-yellow-800">Degrading Factors:</span>
                <ul className="list-disc pl-4 mt-1 text-[11px] text-yellow-700">
                  {selectedReadiness.degrading_factors.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-2">
              <span className="font-bold">11 Measurable Telemetry Signals:</span>
              <pre className="win-inset bg-white p-1 text-[10px] font-mono overflow-auto max-h-56 mt-1">
                {JSON.stringify(selectedReadiness.contributing_signals, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
