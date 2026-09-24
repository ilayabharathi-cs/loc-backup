import React, { useState, useEffect } from 'react';
import { v9Api } from '../api/v9';
import type { DistributedJob, BulkOperation } from '../api/v9';

export const SchedulerPage: React.FC = () => {
  const [jobs, setJobs] = useState<DistributedJob[]>([]);
  const [bulkOps, setBulkOps] = useState<BulkOperation[]>([]);
  const [pools, setPools] = useState<any>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState<boolean>(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  // Enqueue Job Modal State
  const [showEnqueueModal, setShowEnqueueModal] = useState<boolean>(false);
  const [jobType, setJobType] = useState<string>('BACKUP');
  const [priority, setPriority] = useState<string>('NORMAL');
  const [clientId, setClientId] = useState<string>('');

  // Bulk Trigger Modal State
  const [showBulkModal, setShowBulkModal] = useState<boolean>(false);
  const [bulkPriority, setBulkPriority] = useState<string>('NORMAL');

  const loadSchedulerData = async () => {
    setLoading(true);
    try {
      const [jobsRes, poolsRes, bulkRes] = await Promise.all([
        v9Api.listJobs({
          status: statusFilter === 'ALL' ? undefined : statusFilter,
          limit: 50,
        }),
        v9Api.getWorkerPools(),
        v9Api.listBulkOperations(20),
      ]);
      setJobs(jobsRes);
      setPools(poolsRes);
      setBulkOps(bulkRes);
    } catch (e: any) {
      console.error('Failed to load scheduler data:', e);
      setActionMsg(`Failed to load scheduler data: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSchedulerData();
    const interval = setInterval(loadSchedulerData, 10000);
    return () => clearInterval(interval);
  }, [statusFilter]);

  const handleEnqueue = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const newJob = await v9Api.enqueueJob({
        job_type: jobType,
        priority: priority,
        client_id: clientId.trim() || undefined,
      });
      setShowEnqueueModal(false);
      setActionMsg(`Job #${newJob.id} (${newJob.job_type}) enqueued successfully with priority ${newJob.priority}.`);
      await loadSchedulerData();
    } catch (e: any) {
      setActionMsg(`Enqueue failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleBulkTrigger = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await v9Api.triggerBulkBackup({
        job_type: 'BACKUP',
        priority: bulkPriority,
      });
      setShowBulkModal(false);
      setActionMsg(`Bulk operation ${res.operation_id} triggered for ${res.target_count} clients (${res.success_count} queued).`);
      await loadSchedulerData();
    } catch (e: any) {
      setActionMsg(`Bulk trigger failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const categories = pools?.categories || {};
  const backpressure = pools?.backpressure || {};

  return (
    <div className="flex-1 flex flex-col p-3 gap-3 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Header Panel */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span>⚡ Distributed Scheduler & Worker Pools Console (V9)</span>
          </h2>
          <p className="text-[11px] text-gray-700">
            Atomic CAS job claims, category concurrency limits, fair scheduling, and fleet bulk dispatch
          </p>
        </div>
        <div className="flex items-center gap-2">
          {loading && <span className="text-[11px] text-gray-500 font-mono">Syncing...</span>}
          <button onClick={loadSchedulerData} className="win-btn px-3 py-1 font-bold">
            Refresh
          </button>
          <button onClick={() => setShowEnqueueModal(true)} className="win-btn px-3 py-1 font-bold">
            + Enqueue Job
          </button>
          <button
            onClick={() => setShowBulkModal(true)}
            className="win-btn px-3 py-1 font-bold text-[#000080]"
          >
            🚀 Fleet Bulk Backup
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="win-outset p-2 bg-[#ffffcc] text-black font-mono flex justify-between items-center">
          <span>ℹ {actionMsg}</span>
          <button onClick={() => setActionMsg(null)} className="win-btn px-2 text-[10px]">
            Dismiss
          </button>
        </div>
      )}

      {/* Backpressure Status Banner */}
      <div className="win-outset p-2 bg-white flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className="font-bold">Queue Backpressure Engine:</span>
          <span
            className={`px-2 py-0.5 font-bold font-mono text-[10px] text-white ${
              backpressure.backpressure_level === 'NORMAL'
                ? 'bg-[#008000]'
                : backpressure.backpressure_level === 'MODERATE'
                ? 'bg-[#e09000]'
                : 'bg-[#c00000]'
            }`}
          >
            ● {backpressure.backpressure_level || 'NORMAL'}
          </span>
          <span className="text-gray-600 font-mono text-[11px]">
            ({backpressure.queued_jobs ?? 0} jobs waiting across {backpressure.active_nodes ?? 0} active worker nodes)
          </span>
        </div>
        {backpressure.should_throttle_new_jobs && (
          <span className="text-[#800000] font-bold font-mono text-[11px]">
            ⚠️ Workload Throttling Recommended ({backpressure.recommended_retry_delay_seconds}s backoff)
          </span>
        )}
      </div>

      {/* Category Concurrency Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {Object.entries(categories).map(([cat, info]: [string, any]) => (
          <div key={cat} className="win-outset p-2 bg-white flex flex-col gap-1">
            <div className="flex justify-between items-center">
              <span className="font-bold text-[11px] text-[#000080]">{cat}</span>
              <span className="font-mono text-[10px] text-gray-500">
                {info.running}/{info.max_concurrency} Active
              </span>
            </div>
            {/* Simple Win95 Progress Bar */}
            <div className="win-inset bg-gray-200 h-3 w-full overflow-hidden">
              <div
                className={`h-full ${info.is_saturated ? 'bg-[#c00000]' : 'bg-[#000080]'}`}
                style={{ width: `${Math.min(100, info.utilization_pct)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] font-mono text-gray-600">
              <span>{info.utilization_pct}% Utilized</span>
              <span>{info.queued} Queued</span>
            </div>
          </div>
        ))}
      </div>

      {/* Distributed Jobs Queue Table */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex flex-col gap-2">
        <div className="flex justify-between items-center border-b pb-1">
          <div className="flex items-center gap-2">
            <span className="font-bold text-xs">Distributed Job Queue ({jobs.length})</span>
            {/* Filter buttons */}
            <div className="flex gap-1 ml-4">
              {['ALL', 'QUEUED', 'CLAIMED', 'RUNNING', 'COMPLETED', 'FAILED', 'ORPHANED'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-2 py-0.5 text-[10px] font-mono ${
                    statusFilter === st ? 'win-inset bg-white font-bold text-[#000080]' : 'win-btn'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="win-inset bg-white overflow-auto max-h-[320px]">
          <table className="w-full text-left border-collapse text-[11px]">
            <thead className="bg-[#000080] text-white font-mono sticky top-0">
              <tr>
                <th className="p-1 border-r border-[#808080]">ID</th>
                <th className="p-1 border-r border-[#808080]">Job Type</th>
                <th className="p-1 border-r border-[#808080]">Priority</th>
                <th className="p-1 border-r border-[#808080]">Client ID</th>
                <th className="p-1 border-r border-[#808080]">Status</th>
                <th className="p-1 border-r border-[#808080]">Worker Node</th>
                <th className="p-1 border-r border-[#808080]">Attempts</th>
                <th className="p-1 border-r border-[#808080]">Created At</th>
                <th className="p-1">Error / Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 font-mono">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-3 text-center text-gray-500 italic">
                    No distributed jobs found matching current filter.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id}>
                    <td className="p-1 border-r border-gray-200 font-bold">#{job.id}</td>
                    <td className="p-1 border-r border-gray-200">{job.job_type}</td>
                    <td className="p-1 border-r border-gray-200">
                      <span
                        className={`px-1 py-0.2 text-[10px] font-bold ${
                          job.priority === 'CRITICAL'
                            ? 'bg-[#ffc0c0] text-[#800000]'
                            : job.priority === 'HIGH'
                            ? 'bg-[#ffe080] text-[#804000]'
                            : 'bg-[#e0e0e0] text-gray-800'
                        }`}
                      >
                        {job.priority}
                      </span>
                    </td>
                    <td className="p-1 border-r border-gray-200 truncate max-w-[100px]">
                      {job.client_id || 'N/A'}
                    </td>
                    <td className="p-1 border-r border-gray-200">
                      <span
                        className={`px-1 py-0.2 text-[10px] font-bold ${
                          job.status === 'COMPLETED'
                            ? 'bg-[#c0ffc0] text-[#006000]'
                            : job.status === 'RUNNING' || job.status === 'CLAIMED'
                            ? 'bg-[#c0e0ff] text-[#000080]'
                            : job.status === 'QUEUED'
                            ? 'bg-[#ffffc0] text-[#808000]'
                            : 'bg-[#ffc0c0] text-[#800000]'
                        }`}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="p-1 border-r border-gray-200">{job.owner_node_id || '—'}</td>
                    <td className="p-1 border-r border-gray-200">
                      {job.attempt_count} / {job.max_attempts}
                    </td>
                    <td className="p-1 border-r border-gray-200 text-[10px]">
                      {new Date(job.created_at).toLocaleTimeString()}
                    </td>
                    <td className="p-1 text-[10px] text-gray-600 truncate max-w-[200px]">
                      {job.error_message || '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Fleet Bulk Operations Log */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex flex-col gap-1">
        <div className="flex justify-between items-center">
          <span className="font-bold text-xs">Fleet Bulk Operations History ({bulkOps.length})</span>
          <span className="text-[10px] text-gray-600 font-mono">Mass Policy & Backup Dispatch</span>
        </div>
        <div className="win-inset bg-white overflow-auto max-h-[160px]">
          <table className="w-full text-left border-collapse text-[11px] font-mono">
            <thead className="bg-[#808080] text-white sticky top-0">
              <tr>
                <th className="p-1">Operation ID</th>
                <th className="p-1">Type</th>
                <th className="p-1">Status</th>
                <th className="p-1">Target</th>
                <th className="p-1">Success</th>
                <th className="p-1">Failures</th>
                <th className="p-1">Started</th>
                <th className="p-1">Completed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {bulkOps.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-2 text-center text-gray-500 italic">
                    No bulk operations triggered yet.
                  </td>
                </tr>
              ) : (
                bulkOps.map((op) => (
                  <tr key={op.operation_id}>
                    <td className="p-1 font-bold">{op.operation_id}</td>
                    <td className="p-1">{op.operation_type}</td>
                    <td className="p-1">
                      <span
                        className={`px-1 text-[10px] font-bold ${
                          op.status === 'COMPLETED' ? 'text-[#008000]' : 'text-[#800000]'
                        }`}
                      >
                        {op.status}
                      </span>
                    </td>
                    <td className="p-1">{op.target_count}</td>
                    <td className="p-1 text-[#008000]">{op.success_count}</td>
                    <td className="p-1 text-[#800000]">{op.failure_count}</td>
                    <td className="p-1 text-[10px]">
                      {op.started_at ? new Date(op.started_at).toLocaleTimeString() : '—'}
                    </td>
                    <td className="p-1 text-[10px]">
                      {op.completed_at ? new Date(op.completed_at).toLocaleTimeString() : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Enqueue Modal */}
      {showEnqueueModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="win-outset bg-[#dcdcdc] p-3 w-full max-w-sm flex flex-col gap-3 font-sans">
            <div className="bg-[#000080] text-white p-1 font-bold flex justify-between items-center text-xs">
              <span>Enqueue Distributed Job</span>
              <button
                onClick={() => setShowEnqueueModal(false)}
                className="win-btn text-black px-1.5 py-0 text-xs font-mono"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleEnqueue} className="flex flex-col gap-2 font-mono text-xs">
              <div>
                <label className="block text-[11px] font-bold text-gray-700">Job Type</label>
                <select
                  value={jobType}
                  onChange={(e) => setJobType(e.target.value)}
                  className="win-inset w-full p-1 bg-white"
                >
                  <option value="BACKUP">BACKUP</option>
                  <option value="RESTORE">RESTORE</option>
                  <option value="REPLICATION">REPLICATION</option>
                  <option value="PRUNE">PRUNE</option>
                  <option value="VERIFICATION">VERIFICATION</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-bold text-gray-700">Priority</label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="win-inset w-full p-1 bg-white"
                >
                  <option value="CRITICAL">CRITICAL (Top of Queue)</option>
                  <option value="HIGH">HIGH</option>
                  <option value="NORMAL">NORMAL</option>
                  <option value="LOW">LOW</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-bold text-gray-700">Client ID (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. client-uuid"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  className="win-inset w-full p-1 bg-white"
                />
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowEnqueueModal(false)}
                  className="win-btn px-3 py-1 font-bold"
                >
                  Cancel
                </button>
                <button type="submit" className="win-btn px-4 py-1 font-bold text-[#000080]">
                  Enqueue
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Bulk Trigger Modal */}
      {showBulkModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="win-outset bg-[#dcdcdc] p-3 w-full max-w-sm flex flex-col gap-3 font-sans">
            <div className="bg-[#000080] text-white p-1 font-bold flex justify-between items-center text-xs">
              <span>🚀 Fleet-wide Bulk Backup Trigger</span>
              <button
                onClick={() => setShowBulkModal(false)}
                className="win-btn text-black px-1.5 py-0 text-xs font-mono"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleBulkTrigger} className="flex flex-col gap-2 font-mono text-xs">
              <p className="text-[11px] text-gray-700 leading-tight">
                This will simultaneously generate queued distributed backup jobs for all registered clients in the fleet.
              </p>
              <div>
                <label className="block text-[11px] font-bold text-gray-700">Dispatch Priority</label>
                <select
                  value={bulkPriority}
                  onChange={(e) => setBulkPriority(e.target.value)}
                  className="win-inset w-full p-1 bg-white"
                >
                  <option value="NORMAL">NORMAL</option>
                  <option value="HIGH">HIGH</option>
                  <option value="LOW">LOW</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowBulkModal(false)}
                  className="win-btn px-3 py-1 font-bold"
                >
                  Cancel
                </button>
                <button type="submit" className="win-btn px-4 py-1 font-bold text-[#000080]">
                  Trigger Fleet Backup
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
