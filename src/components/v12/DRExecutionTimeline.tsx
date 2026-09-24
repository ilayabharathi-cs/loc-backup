import React from 'react';
import type { DRExecutionStep, DRExecutionMode } from '../../api/v12';
import { CheckIcon, ErrorIcon, WarningIcon } from '../win95/WinIcons';

interface DRExecutionTimelineProps {
  steps: DRExecutionStep[];
  mode: DRExecutionMode;
}

export const DRExecutionTimeline: React.FC<DRExecutionTimelineProps> = ({ steps, mode }) => {
  const isSimulation = mode === 'TEST_DRILL';

  return (
    <div className="flex flex-col gap-2 font-sans text-xs">
      {/* Mode Banner */}
      <div
        className={`win-outset p-2 flex justify-between items-center ${
          isSimulation ? 'bg-[#e6f2ff] border-[#000080]' : 'bg-[#fff0f0] border-[#cc0000]'
        }`}
      >
        <div className="flex items-center gap-2">
          <span
            className={`px-2 py-0.5 text-xs font-black text-white rounded ${
              isSimulation ? 'bg-[#000080]' : 'bg-[#cc0000]'
            }`}
          >
            {isSimulation ? 'SIMULATION MODE (DRY RUN)' : 'ACTUAL FAILOVER (LIVE INFRASTRUCTURE)'}
          </span>
          <span className="text-[11px] text-gray-700">
            {isSimulation
              ? 'Testing boot dependencies, networking, and integrity checks without touching production servers.'
              : 'Executing real disaster recovery workflow. Workloads will be provisioned on target DR hosts.'}
          </span>
        </div>
      </div>

      {/* Stepper List */}
      <div className="win-inset bg-white p-3 flex flex-col gap-2 overflow-auto max-h-[450px]">
        {steps.map((step) => {
          let statusBadge = (
            <span className="px-2 py-0.5 text-[10px] bg-gray-200 text-gray-700 font-bold border border-gray-400">
              PENDING
            </span>
          );

          if (step.status === 'RUNNING') {
            statusBadge = (
              <span className="px-2 py-0.5 text-[10px] bg-blue-600 text-white font-bold animate-pulse flex items-center gap-1">
                RUNNING...
              </span>
            );
          } else if (step.status === 'SUCCEEDED') {
            statusBadge = (
              <span className="px-2 py-0.5 text-[10px] bg-green-700 text-white font-bold flex items-center gap-1">
                <CheckIcon size={12} /> SUCCEEDED
              </span>
            );
          } else if (step.status === 'FAILED') {
            statusBadge = (
              <span className="px-2 py-0.5 text-[10px] bg-red-700 text-white font-bold flex items-center gap-1">
                <ErrorIcon size={12} /> FAILED
              </span>
            );
          } else if (step.status === 'SKIPPED') {
            statusBadge = (
              <span className="px-2 py-0.5 text-[10px] bg-yellow-600 text-white font-bold flex items-center gap-1">
                <WarningIcon size={12} /> SKIPPED
              </span>
            );
          }

          return (
            <div
              key={step.step_id}
              className={`p-2.5 border-l-4 flex flex-col gap-1 ${
                step.status === 'RUNNING'
                  ? 'bg-blue-50 border-blue-600'
                  : step.status === 'SUCCEEDED'
                  ? 'bg-green-50 border-green-600'
                  : step.status === 'FAILED'
                  ? 'bg-red-50 border-red-600'
                  : 'bg-gray-50 border-gray-300'
              }`}
            >
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-gray-600">Step {step.step_order}:</span>
                  <strong className="text-xs">{step.workload_name}</strong>
                  <span className="text-[10px] px-1.5 py-0.2 bg-gray-200 font-mono">
                    {step.action_type}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  {step.duration_ms > 0 && (
                    <span className="text-[10px] text-gray-500 font-mono">
                      {(step.duration_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                  {statusBadge}
                </div>
              </div>

              {step.error_message && (
                <div className="win-inset p-2 bg-[#ffebee] text-[#cc0000] text-[11px] font-mono mt-1 border border-red-300">
                  {step.error_message}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default DRExecutionTimeline;
