import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { v12Api, parseApiError } from '../api/v12';
import type { DRRunbook, DRExecuteRequest } from '../api/v12';
import { WinDialog } from '../components/win95/WinDialog';
import { RunbookIcon, RefreshIcon, WarningIcon, CheckIcon, ErrorIcon } from '../components/win95/WinIcons';

export const DRRunbooksPage: React.FC = () => {
  const navigate = useNavigate();
  const [runbooks, setRunbooks] = useState<DRRunbook[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Failover Confirmation Dialog State
  const [failoverTarget, setFailoverTarget] = useState<DRRunbook | null>(null);
  const [failoverMode, setFailoverMode] = useState<'SIMULATION' | 'ACTUAL_FAILOVER'>('SIMULATION');
  const [failoverAcknowledged, setFailoverAcknowledged] = useState(false);
  const [confirmRunbookName, setConfirmRunbookName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadRunbooks = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await v12Api.listDRRunbooks();
      setRunbooks(data);
    } catch (err: unknown) {
      setError(parseApiError(err, 'Failed to connect to DR orchestration engine'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRunbooks();
  }, []);

  const handleSimulate = async (runbook: DRRunbook) => {
    setActionMessage(`Running pre-flight DAG simulation for "${runbook.name}"...`);
    try {
      const res = await v12Api.simulateDRRunbook(runbook.runbook_id);
      if (res.passed) {
        setActionMessage(
          `Simulation PASSED! Verified ${res.checks_performed.length} pre-flight checks. Simulated RTO: ${res.simulated_rto_seconds}s.`
        );
      } else {
        setActionMessage(
          `Simulation FAILED: ${res.errors.join('; ')}`
        );
      }
      await loadRunbooks();
    } catch (err: unknown) {
      setActionMessage(`Error running simulation: ${parseApiError(err)}`);
    }
  };

  const handleExecuteSubmit = async () => {
    if (!failoverTarget) return;

    if (failoverMode === 'ACTUAL_FAILOVER') {
      if (!failoverAcknowledged) {
        setActionMessage('You must check the acknowledgment checkbox before initiating actual failover.');
        return;
      }
      if (confirmRunbookName.trim() !== failoverTarget.name) {
        setActionMessage('Typed runbook name does not match. Please verify runbook name.');
        return;
      }
    }

    setSubmitting(true);
    try {
      const req: DRExecuteRequest = {
        execution_mode: failoverMode === 'ACTUAL_FAILOVER' ? 'FAILOVER' : 'TEST_DRILL',
        auto_rollback_on_failure: true
      };

      const exec = await v12Api.executeDRRunbook(failoverTarget.runbook_id, req);
      setFailoverTarget(null);
      setFailoverAcknowledged(false);
      setConfirmRunbookName('');
      navigate(`/dr/executions/${exec.execution_id}`);
    } catch (err: unknown) {
      setActionMessage(`Execution error: ${parseApiError(err)}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Header */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span className="bg-[#000080] text-white px-1.5 py-0.5 rounded text-[10px]">V12</span>
            Automated Disaster Recovery Runbook Orchestrator
          </h2>
          <p className="text-[11px] text-gray-700">
            Multi-tier workload failover sequencing, topological DAG dependency resolution, and simulated dry runs
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button onClick={loadRunbooks} className="win-btn px-3 py-1 flex items-center gap-1">
            <RefreshIcon size={12} /> Refresh
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-xs font-semibold flex justify-between items-center">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="win-btn text-[10px] px-1.5 py-0.5">
            Dismiss
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3">
          <div className="text-xs font-bold text-gray-700">Loading disaster recovery runbook inventory...</div>
          <div className="w-64 h-4 win-inset-gray bg-[#dfdfdf] relative overflow-hidden">
            <div className="h-full bg-[#000080] animate-pulse w-3/4" />
          </div>
        </div>
      ) : error ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3 text-center">
          <div className="text-[#cc0000] font-bold text-sm">Failed to Load DR Runbooks</div>
          <div className="text-xs text-gray-700 max-w-md">{error}</div>
          <button onClick={loadRunbooks} className="win-btn px-4 py-1.5 font-bold">
            Retry Connection
          </button>
        </div>
      ) : runbooks.length === 0 ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3 text-center">
          <RunbookIcon size={32} />
          <div className="font-bold text-sm">No Disaster Recovery Runbooks Configured</div>
          <div className="text-xs text-gray-600 max-w-sm">
            Create an automated disaster recovery runbook to define workload boot sequencing and dependency ordering.
          </div>
        </div>
      ) : (
        <div className="flex-1 win-inset bg-white overflow-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="bg-[#e0e0e0] sticky top-0 border-b border-[#808080]">
              <tr>
                <th className="p-2 border-r border-[#808080]">Runbook Name</th>
                <th className="p-2 border-r border-[#808080]">Target DR Environment</th>
                <th className="p-2 border-r border-[#808080]">Workloads</th>
                <th className="p-2 border-r border-[#808080]">Est. RTO</th>
                <th className="p-2 border-r border-[#808080]">DAG Status</th>
                <th className="p-2 border-r border-[#808080]">Last Simulation</th>
                <th className="p-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {runbooks.map((rb) => {
                const isCycleError = rb.status === 'CYCLE_ERROR';

                return (
                  <tr
                    key={rb.runbook_id}
                    className="border-b border-gray-200 hover:bg-[#f4f4f4] transition-colors"
                  >
                    <td className="p-2">
                      <div className="font-bold text-xs text-[#000080] hover:underline cursor-pointer"
                           onClick={() => navigate(`/dr/runbooks/${rb.runbook_id}`)}>
                        {rb.name}
                      </div>
                      <div className="text-[10px] text-gray-500 font-mono">{rb.runbook_id}</div>
                    </td>
                    <td className="p-2">{rb.target_environment}</td>
                    <td className="p-2 font-mono">{rb.step_count} nodes</td>
                    <td className="p-2 font-mono font-bold text-[#000080]">
                      {Math.round(rb.estimated_rto_seconds / 60)} min
                    </td>
                    <td className="p-2">
                      {isCycleError ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-800 border border-red-300 flex items-center gap-1 w-max">
                          <ErrorIcon size={12} /> CYCLE ERROR
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-800 border border-green-300 flex items-center gap-1 w-max">
                          <CheckIcon size={12} /> READY
                        </span>
                      )}
                    </td>
                    <td className="p-2">
                      {rb.last_simulation_passed === true ? (
                        <span className="text-green-700 font-bold flex items-center gap-1 text-[11px]">
                          <CheckIcon size={12} /> Passed
                        </span>
                      ) : rb.last_simulation_passed === false ? (
                        <span className="text-red-700 font-bold flex items-center gap-1 text-[11px]">
                          <ErrorIcon size={12} /> Failed
                        </span>
                      ) : (
                        <span className="text-gray-500 text-[11px]">Never Run</span>
                      )}
                    </td>
                    <td className="p-2">
                      <div className="flex gap-1.5 items-center">
                        <button
                          onClick={() => navigate(`/dr/runbooks/${rb.runbook_id}`)}
                          className="win-btn text-[11px] px-2 py-0.5 font-bold"
                        >
                          Inspect DAG
                        </button>
                        <button
                          onClick={() => handleSimulate(rb)}
                          className="win-btn text-[11px] px-2 py-0.5"
                          title="Simulate pre-flight checks in isolated test mode"
                        >
                          Simulate
                        </button>
                        <button
                          onClick={() => {
                            setFailoverTarget(rb);
                            setFailoverMode('SIMULATION');
                            setFailoverAcknowledged(false);
                          }}
                          className={`win-btn text-[11px] px-2 py-0.5 font-bold ${
                            isCycleError ? 'opacity-50 cursor-not-allowed' : 'text-[#000080]'
                          }`}
                          disabled={isCycleError}
                        >
                          Launch...
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Launch Execution Modal with Explicit Simulation vs Failover Differentiation */}
      <WinDialog
        isOpen={Boolean(failoverTarget)}
        title="Execute Disaster Recovery Runbook — [Mode Selection]"
        icon={<RunbookIcon size={16} />}
        onClose={() => setFailoverTarget(null)}
        width="480px"
      >
        <div className="flex flex-col gap-3 p-1 font-sans text-xs">
          <div className="font-bold text-xs text-gray-800">
            Target Runbook: <span className="text-[#000080]">{failoverTarget?.name}</span>
          </div>

          {/* Mode Selector */}
          <div className="win-inset p-2.5 bg-gray-50 flex flex-col gap-2">
            <span className="font-bold text-[11px]">Select Execution Paradigm:</span>
            <label className="flex items-start gap-2 p-2 border border-gray-300 rounded cursor-pointer bg-blue-50 hover:bg-blue-100">
              <input
                type="radio"
                name="execMode"
                value="SIMULATION"
                checked={failoverMode === 'SIMULATION'}
                onChange={() => setFailoverMode('SIMULATION')}
                className="mt-0.5"
              />
              <div>
                <strong className="text-[#000080] block">SIMULATION (Dry Run Sandbox)</strong>
                <span className="text-[10px] text-gray-600 block">
                  Simulates full DAG dependency boot order, IP quotas, and VSS recovery integrity without modifying target infrastructure.
                </span>
              </div>
            </label>

            <label className="flex items-start gap-2 p-2 border border-red-300 rounded cursor-pointer bg-red-50 hover:bg-red-100">
              <input
                type="radio"
                name="execMode"
                value="ACTUAL_FAILOVER"
                checked={failoverMode === 'ACTUAL_FAILOVER'}
                onChange={() => setFailoverMode('ACTUAL_FAILOVER')}
                className="mt-0.5"
              />
              <div>
                <strong className="text-[#cc0000] block">ACTUAL FAILOVER (Live DR Provisioning)</strong>
                <span className="text-[10px] text-gray-700 block">
                  PROVISIONS REAL PRODUCTION WORKLOADS in {failoverTarget?.target_environment}. Network traffic will be rerouted.
                </span>
              </div>
            </label>
          </div>

          {/* Strong Warning and Checkbox for Actual Failover */}
          {failoverMode === 'ACTUAL_FAILOVER' && (
            <div className="win-inset p-2 bg-[#ffebee] border-l-4 border-[#cc0000] flex flex-col gap-2">
              <div className="font-bold text-[#cc0000] flex items-center gap-1">
                <WarningIcon size={14} /> Critical Infrastructure Impact Warning
              </div>
              <p className="text-[11px] text-gray-800">
                This operation initiates failover for {failoverTarget?.step_count} production workloads. This operation may affect recovery infrastructure.
              </p>
              <label className="flex items-center gap-2 font-bold cursor-pointer text-[11px] text-[#cc0000]">
                <input
                  type="checkbox"
                  checked={failoverAcknowledged}
                  onChange={(e) => setFailoverAcknowledged(e.target.checked)}
                />
                <span>I confirm live failover execution for this infrastructure.</span>
              </label>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-[#808080]">
            <button
              onClick={() => setFailoverTarget(null)}
              className="win-btn px-3 py-1"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              onClick={handleExecuteSubmit}
              className={`win-btn px-4 py-1 font-bold ${
                failoverMode === 'ACTUAL_FAILOVER' ? 'bg-[#ffebee] text-[#cc0000]' : 'bg-[#e6f2ff] text-[#000080]'
              }`}
              disabled={submitting || (failoverMode === 'ACTUAL_FAILOVER' && !failoverAcknowledged)}
            >
              {submitting
                ? 'Initiating...'
                : failoverMode === 'ACTUAL_FAILOVER'
                ? 'Execute Live Failover'
                : 'Start Dry Run Simulation'}
            </button>
          </div>
        </div>
      </WinDialog>
    </div>
  );
};

export default DRRunbooksPage;
