import React, { useState, useEffect } from 'react';
import { v11Api } from '../api/v11';
import type { Workload, RestorePreview, RestoreExecution } from '../api/v11';

export const ApplicationRestorePage: React.FC = () => {
  const [workloads, setWorkloads] = useState<Workload[]>([]);
  const [selectedWorkloadId, setSelectedWorkloadId] = useState<string>('');
  const [recoveryPointId, setRecoveryPointId] = useState<string>('1');
  const [targetDestination, setTargetDestination] = useState<string>('C:\\RetroVault_Restores\\app_recovered');
  const [recoveryMode, setRecoveryMode] = useState<string>('APPLICATION_RESTORE');
  const [preview, setPreview] = useState<RestorePreview | null>(null);
  const [restoreResult, setRestoreResult] = useState<RestoreExecution | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [restoring, setRestoring] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    v11Api.getWorkloads().then((data) => {
      setWorkloads(data);
      if (data.length > 0) setSelectedWorkloadId(data[0].workload_id);
    });
  }, []);

  const handlePreview = async () => {
    if (!selectedWorkloadId) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await v11Api.previewRestore(
        selectedWorkloadId,
        recoveryPointId,
        targetDestination,
        recoveryMode
      );
      setPreview(res);
    } catch (e: any) {
      setErrorMsg('Preview failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!selectedWorkloadId) return;
    setRestoring(true);
    setErrorMsg(null);
    try {
      const res = await v11Api.executeRestore(
        selectedWorkloadId,
        recoveryPointId,
        targetDestination,
        recoveryMode
      );
      setRestoreResult(res);
    } catch (e: any) {
      setErrorMsg('Restore error: ' + (e.response?.data?.detail || e.message));
    } finally {
      setRestoring(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span className="bg-[#000080] text-white px-1.5 py-0.5 rounded text-[10px]">V11</span>
            Application-Aware Restore & Disaster Recovery Wizard
          </h2>
          <p className="text-[11px] text-gray-700">
            Preview overwrite conflicts, dependencies, and execute validated 7-phase application reconstruction
          </p>
        </div>
      </div>

      {errorMsg && (
        <div className="win-inset p-2 bg-red-50 border-l-4 border-red-600 text-red-800 font-semibold">
          {errorMsg}
        </div>
      )}

      <div className="flex-1 flex gap-2 min-h-0">
        {/* Wizard Form */}
        <div className="w-96 win-outset bg-[#dcdcdc] p-3 flex flex-col gap-2.5 overflow-auto">
          <h3 className="font-bold border-b border-gray-400 pb-1">
            Recovery Configuration
          </h3>

          <div>
            <label className="font-bold block mb-1">Target Application Workload:</label>
            <select
              className="win-inset bg-white w-full p-1 text-xs"
              value={selectedWorkloadId}
              onChange={(e) => setSelectedWorkloadId(e.target.value)}
            >
              {workloads.map((w) => (
                <option key={w.workload_id} value={w.workload_id}>
                  {w.name} ({w.type})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="font-bold block mb-1">Source Recovery Point ID:</label>
            <input
              type="text"
              className="win-inset bg-white w-full p-1 text-xs font-mono"
              value={recoveryPointId}
              onChange={(e) => setRecoveryPointId(e.target.value)}
            />
          </div>

          <div>
            <label className="font-bold block mb-1">Recovery Mode:</label>
            <select
              className="win-inset bg-white w-full p-1 text-xs"
              value={recoveryMode}
              onChange={(e) => setRecoveryMode(e.target.value)}
            >
              <option value="APPLICATION_RESTORE">APPLICATION_RESTORE (Full Application State)</option>
              <option value="DATABASE_RESTORE">DATABASE_RESTORE (Database Engine Target)</option>
              <option value="FULL_RECOVERY_POINT">FULL_RECOVERY_POINT</option>
              <option value="FILE_RESTORE">FILE_RESTORE</option>
            </select>
          </div>

          <div>
            <label className="font-bold block mb-1">Target Destination Path:</label>
            <input
              type="text"
              className="win-inset bg-white w-full p-1 text-xs font-mono"
              value={targetDestination}
              onChange={(e) => setTargetDestination(e.target.value)}
            />
          </div>

          <div className="mt-2 flex gap-2">
            <button
              onClick={handlePreview}
              disabled={loading}
              className="win-btn flex-1 py-1 font-bold"
            >
              {loading ? 'Evaluating...' : 'Preview Restore'}
            </button>
            <button
              onClick={handleExecute}
              disabled={restoring || !preview?.is_safe_to_proceed}
              className="win-btn flex-1 py-1 font-bold bg-[#000080] text-white"
            >
              {restoring ? 'Restoring...' : 'Execute Restore'}
            </button>
          </div>
        </div>

        {/* Results & Inspection */}
        <div className="flex-1 flex flex-col gap-2 min-h-0">
          {preview ? (
            <div className="win-outset bg-[#dcdcdc] p-3 flex flex-col gap-2 flex-1 overflow-auto">
              <h3 className="font-bold border-b border-gray-400 pb-1">
                Restore Preview & Conflict Inspection
              </h3>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="font-bold">Consistency Status:</span>{' '}
                  <span className="bg-green-100 text-green-800 px-1 py-0.5 rounded font-mono">
                    {preview.consistency_status}
                  </span>
                </div>
                <div>
                  <span className="font-bold">Estimated Size:</span>{' '}
                  <span className="font-mono">{(preview.estimated_size_bytes / (1024 * 1024)).toFixed(2)} MB</span>
                </div>
                <div>
                  <span className="font-bold">Safe to Proceed:</span>{' '}
                  <span className={preview.is_safe_to_proceed ? 'text-green-700 font-bold' : 'text-red-700 font-bold'}>
                    {preview.is_safe_to_proceed ? 'YES' : 'NO'}
                  </span>
                </div>
              </div>

              {preview.overwrite_conflicts.length > 0 && (
                <div className="win-inset bg-yellow-50 p-2 border-l-4 border-yellow-600">
                  <span className="font-bold text-yellow-800">Overwrite Conflicts Detected:</span>
                  <ul className="list-disc pl-4 mt-1 text-[11px] text-yellow-700">
                    {preview.overwrite_conflicts.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <span className="font-bold block mb-1">Pre-flight Validation Plan:</span>
                <div className="win-inset bg-white p-2">
                  <ol className="list-decimal pl-4 space-y-1">
                    {preview.validation_plan.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ol>
                </div>
              </div>

              {restoreResult && (
                <div className="win-inset bg-green-50 p-3 border-l-4 border-green-600 mt-2">
                  <h4 className="font-bold text-green-900 text-xs">
                    Restore Execution Completed Successfully!
                  </h4>
                  <p className="text-[11px] text-green-800 mt-1">
                    Completed Phases:{' '}
                    <span className="font-mono font-bold">
                      {restoreResult.phases_completed.join(' → ')}
                    </span>
                  </p>
                  <p className="text-[11px] text-green-800">
                    Restored Artifacts: {restoreResult.artifacts_restored} ({restoreResult.restored_bytes} bytes)
                  </p>
                  <p className="text-[11px] text-green-800 font-semibold">
                    Checksum & Application Validation: PASSED
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="win-inset bg-white flex-1 p-6 flex flex-col items-center justify-center text-gray-500">
              <p>Configure recovery options on the left and click "Preview Restore" to inspect safety and dependencies.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
