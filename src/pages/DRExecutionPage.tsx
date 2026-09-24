import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { v12Api, parseApiError } from '../api/v12';
import type { DRRunbookExecution } from '../api/v12';
import { DRExecutionTimeline } from '../components/v12/DRExecutionTimeline';
import { RunbookIcon, RefreshIcon, CheckIcon, ErrorIcon, ShieldCheckIcon } from '../components/win95/WinIcons';

export const DRExecutionPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [execution, setExecution] = useState<DRRunbookExecution | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchStatus = useCallback(async (isInitial = false) => {
    if (!id) return;
    if (isInitial) setLoading(true);
    else setIsRefreshing(true);

    try {
      const data = await v12Api.getDRExecution(id);
      setExecution(data);
      setError(null);
    } catch (err: unknown) {
      setError(parseApiError(err, 'Failed to retrieve DR execution record'));
    } finally {
      if (isInitial) setLoading(false);
      setIsRefreshing(false);
    }
  }, [id]);

  useEffect(() => {
    let isMounted = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const runPoll = async () => {
      if (!id) return;
      try {
        const data = await v12Api.getDRExecution(id);
        if (!isMounted) return;
        setExecution(data);
        setError(null);

        // Check terminal state
        const isTerminal = data.status === 'SUCCEEDED' || data.status === 'FAILED' || data.status === 'CANCELLED';
        if (!isTerminal) {
          timer = setTimeout(runPoll, 2500);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        setError(parseApiError(err, 'Failed to poll DR execution status'));
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    setLoading(true);
    runPoll();

    return () => {
      isMounted = false;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  if (loading) {
    return (
      <div className="flex-1 win-inset bg-white m-3 p-8 flex flex-col items-center justify-center gap-3">
        <div className="text-xs font-bold text-gray-700">Connecting to DR execution orchestrator...</div>
        <div className="w-64 h-4 win-inset-gray bg-[#dfdfdf] relative overflow-hidden">
          <div className="h-full bg-[#000080] animate-pulse w-3/4" />
        </div>
      </div>
    );
  }

  if (error || !execution) {
    return (
      <div className="flex-1 win-inset bg-white m-3 p-8 flex flex-col items-center justify-center gap-3 text-center">
        <div className="text-[#cc0000] font-bold text-sm">Failed to Load Execution</div>
        <div className="text-xs text-gray-700">{error || 'Execution not found'}</div>
        <button onClick={() => navigate('/dr/runbooks')} className="win-btn px-4 py-1.5 font-bold">
          &larr; Return to Runbook Catalog
        </button>
      </div>
    );
  }

  const isTerminal = execution.status === 'SUCCEEDED' || execution.status === 'FAILED' || execution.status === 'CANCELLED';
  const completedSteps = execution.steps.filter((s) => s.status === 'SUCCEEDED').length;
  const failedSteps = execution.steps.filter((s) => s.status === 'FAILED');
  const healthCheckSteps = execution.steps.filter((s) => s.action_type === 'HEALTH_CHECK' || s.action_type === 'VALIDATION');
  const passedHealthChecks = healthCheckSteps.filter((s) => s.status === 'SUCCEEDED').length;

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Header Bar */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate('/dr/runbooks')} className="win-btn px-2 py-0.5 font-bold">
            &larr; Runbooks
          </button>
          <div>
            <h2 className="text-sm font-bold flex items-center gap-2">
              <RunbookIcon size={16} />
              <span>{execution.runbook_name}</span>
              <span className="font-mono text-[10px] text-gray-600 bg-white px-1 border border-gray-400">
                {execution.execution_id}
              </span>
            </h2>
            <p className="text-[11px] text-gray-700">
              Initiated by: <strong>{execution.initiated_by}</strong> &bull; Started:{' '}
              {new Date(execution.started_at).toLocaleTimeString()}
            </p>
          </div>
        </div>

        <div className="flex gap-2 items-center">
          <div className="flex items-center gap-1.5 px-2 py-0.5 win-inset bg-white text-[10px] font-mono">
            {isTerminal ? (
              <span className="text-gray-600 font-bold">● TERMINATED</span>
            ) : (
              <span className="text-green-700 font-bold animate-pulse">● POLLING (2.5s)</span>
            )}
          </div>
          <button
            onClick={() => fetchStatus(false)}
            disabled={isRefreshing}
            className="win-btn px-3 py-1 flex items-center gap-1"
          >
            <RefreshIcon size={12} /> {isRefreshing ? 'Checking...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Execution Status Card */}
      <div className="win-outset p-3 bg-[#dcdcdc] flex flex-wrap justify-between items-center gap-2">
        <div className="flex items-center gap-3">
          <div className="flex flex-col">
            <span className="text-[10px] text-gray-600 uppercase font-bold">Execution Status</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              {execution.status === 'SUCCEEDED' ? (
                <span className="px-2 py-0.5 bg-green-700 text-white font-bold rounded flex items-center gap-1">
                  <CheckIcon size={12} /> SUCCEEDED
                </span>
              ) : execution.status === 'FAILED' ? (
                <span className="px-2 py-0.5 bg-red-700 text-white font-bold rounded flex items-center gap-1">
                  <ErrorIcon size={12} /> FAILED
                </span>
              ) : (
                <span className="px-2 py-0.5 bg-blue-700 text-white font-bold rounded animate-pulse">
                  IN PROGRESS (Stage {execution.current_step_order}/{execution.total_steps})
                </span>
              )}
            </div>
          </div>

          <div className="h-8 w-px bg-gray-400 mx-2" />

          <div className="flex flex-col">
            <span className="text-[10px] text-gray-600 uppercase font-bold">Execution Mode</span>
            <span className={`font-mono text-xs font-bold mt-0.5 ${
              execution.execution_mode === 'TEST_DRILL' ? 'text-[#000080]' : 'text-[#b22222]'
            }`}>
              {execution.execution_mode === 'TEST_DRILL' ? 'SIMULATION / DRY RUN' : 'CRITICAL FAILOVER'}
            </span>
          </div>

          <div className="h-8 w-px bg-gray-400 mx-2" />

          <div className="flex flex-col">
            <span className="text-[10px] text-gray-600 uppercase font-bold">Phases Completed</span>
            <span className="font-mono text-xs font-bold mt-0.5 text-gray-800">
              {completedSteps} / {execution.total_steps} Workloads
            </span>
          </div>

          <div className="h-8 w-px bg-gray-400 mx-2" />

          <div className="flex flex-col">
            <span className="text-[10px] text-gray-600 uppercase font-bold">Health Checks</span>
            <span className="font-mono text-xs font-bold mt-0.5 text-gray-800 flex items-center gap-1">
              <ShieldCheckIcon size={12} /> {passedHealthChecks} / {healthCheckSteps.length} Verified
            </span>
          </div>
        </div>

        {isTerminal && execution.completed_at && (
          <div className="text-right text-[11px] text-gray-600">
            <div>Completed At: {new Date(execution.completed_at).toLocaleTimeString()}</div>
            <div className="text-[10px]">
              Total Duration:{' '}
              {Math.round(
                (new Date(execution.completed_at).getTime() - new Date(execution.started_at).getTime()) / 1000
              )}
              s
            </div>
          </div>
        )}
      </div>

      {/* Failure Banner if any step failed */}
      {failedSteps.length > 0 && (
        <div className="win-inset p-2.5 bg-[#ffebee] border-l-4 border-[#cc0000] text-xs">
          <strong className="text-[#cc0000] flex items-center gap-1">
            <ErrorIcon size={14} /> Execution Interrupted by Stage Failure:
          </strong>
          <div className="text-gray-800 mt-1">
            Workload <strong>{failedSteps[0].workload_name}</strong> reported error:{' '}
            <code className="text-[#cc0000]">{failedSteps[0].error_message || 'Verification probe timeout'}</code>
          </div>
        </div>
      )}

      {/* Execution Stepper Timeline */}
      <div className="flex-1 flex flex-col gap-2 min-h-0">
        <div className="font-bold text-xs text-gray-800 px-1">Topological Execution Stepper:</div>
        <DRExecutionTimeline steps={execution.steps} mode={execution.execution_mode} />
      </div>
    </div>
  );
};

export default DRExecutionPage;
