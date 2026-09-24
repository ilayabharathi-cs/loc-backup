import React, { useState, useEffect } from 'react';
import { 
  getReplicationJobs, 
  createReplicationJob, 
  pauseReplicationJob, 
  resumeReplicationJob, 
  cancelReplicationJob, 
  retryReplicationJob, 
  getRepositories, 
  getTopology
} from '../api/v7';
import type { 
  ReplicationJob, 
  StorageRepository, 
  TopologyStatus 
} from '../api/v7';

export const ReplicationPage: React.FC = () => {
  const [jobs, setJobs] = useState<ReplicationJob[]>([]);
  const [repos, setRepos] = useState<StorageRepository[]>([]);
  const [topology, setTopology] = useState<TopologyStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [showNewModal, setShowNewModal] = useState<boolean>(false);
  const [sourceRepoId, setSourceRepoId] = useState<number>(0);
  const [destRepoId, setDestRepoId] = useState<number>(0);
  const [bwLimit, setBwLimit] = useState<string>('50');
  const [errorMsg, setErrorMsg] = useState<string>('');

  const loadData = async () => {
    setLoading(true);
    try {
      const [jobsRes, reposRes, topoRes] = await Promise.all([
        getReplicationJobs(),
        getRepositories(),
        getTopology()
      ]);
      if (jobsRes.success) setJobs(jobsRes.data);
      if (reposRes.success) {
        setRepos(reposRes.data);
        if (reposRes.data.length >= 2) {
          setSourceRepoId(reposRes.data[0].id);
          setDestRepoId(reposRes.data[1].id);
        }
      }
      if (topoRes.success) setTopology(topoRes.data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load replication data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleCreate = async () => {
    if (!sourceRepoId || !destRepoId) {
      alert('Please select both source and destination repositories');
      return;
    }
    if (sourceRepoId === destRepoId) {
      alert('Source and destination repositories must be different');
      return;
    }
    try {
      await createReplicationJob({
        source_repository_id: sourceRepoId,
        destination_repository_id: destRepoId,
        bandwidth_limit_mbps: bwLimit ? parseFloat(bwLimit) : undefined
      });
      setShowNewModal(false);
      loadData();
    } catch (err: any) {
      alert('Failed to start replication: ' + (err.response?.data?.error?.message || err.message));
    }
  };

  const handlePause = async (id: string) => {
    try {
      await pauseReplicationJob(id);
      loadData();
    } catch (err: any) {
      alert('Pause failed: ' + err.message);
    }
  };

  const handleResume = async (id: string) => {
    try {
      await resumeReplicationJob(id);
      loadData();
    } catch (err: any) {
      alert('Resume failed: ' + err.message);
    }
  };

  const handleCancel = async (id: string) => {
    try {
      await cancelReplicationJob(id);
      loadData();
    } catch (err: any) {
      alert('Cancel failed: ' + err.message);
    }
  };

  const handleRetry = async (id: string) => {
    try {
      await retryReplicationJob(id);
      loadData();
    } catch (err: any) {
      alert('Retry failed: ' + err.message);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {errorMsg && (
        <div className="p-1 bg-[#ffcccc] text-[#800000] border border-[#800000] font-bold">
          {errorMsg}
        </div>
      )}
      {/* 3-2-1 Topology Compliance Header */}
      <div className="win-outset p-2 flex flex-col gap-1.5 bg-[#dcdcdc]">
        <div className="flex items-center justify-between border-b border-[#808080] pb-1">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm">3-2-1 Enterprise Backup Protection Status:</span>
            {topology?.is_compliant ? (
              <span className="px-2 py-0.5 bg-[#008000] text-white font-bold font-mono text-[10px]">
                ● COMPLIANT
              </span>
            ) : (
              <span className="px-2 py-0.5 bg-[#800000] text-white font-bold font-mono text-[10px]">
                ▲ NOT COMPLIANT
              </span>
            )}
          </div>
          <button
            onClick={loadData}
            className="win-btn px-2 py-0.5 font-bold"
          >
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-4 gap-2 text-[11px]">
          <div className="win-inset p-1.5 bg-white">
            <div className="text-gray-600 font-semibold">Total Target Repositories:</div>
            <div className="font-mono text-sm font-bold">{topology?.total_repositories || 0} / 3</div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="text-gray-600 font-semibold">Media Types (Disk / NAS / S3):</div>
            <div className="font-mono text-sm font-bold">{topology?.media_types_count || 0} / 2 Types</div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="text-gray-600 font-semibold">Offsite / Cloud Copy:</div>
            <div className={`font-mono text-sm font-bold ${topology?.has_offsite ? 'text-[#008000]' : 'text-[#800000]'}`}>
              {topology?.has_offsite ? 'YES (Verified)' : 'MISSING'}
            </div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="text-gray-600 font-semibold">Completed Replications:</div>
            <div className="font-mono text-sm font-bold">{topology?.completed_replications || 0}</div>
          </div>
        </div>

        {topology && !topology.is_compliant && topology.missing_requirements.length > 0 && (
          <div className="p-1 bg-[#ffffe0] border border-[#d4a017] text-[#664d03] text-[10px]">
            <strong>Missing Requirements:</strong> {topology.missing_requirements.join(' • ')}
          </div>
        )}
      </div>

      {/* Toolbar & Action Bar */}
      <div className="win-outset p-1 flex items-center justify-between">
        <div className="flex gap-2">
          <button
            onClick={() => setShowNewModal(true)}
            className="win-btn px-3 py-1 font-bold flex items-center gap-1.5"
          >
            <span>+</span> Start New Replication Job
          </button>
        </div>
        <div className="font-mono text-[11px] text-gray-700">
          Replication Engine: <span className="font-bold text-black">CAS Deduplicated & Resumable</span>
        </div>
      </div>

      {/* Replication Jobs Grid */}
      <div className="flex-1 win-inset bg-white p-1 overflow-auto">
        <table className="w-full border-collapse text-[11px] text-left">
          <thead>
            <tr className="bg-[#000080] text-white">
              <th className="p-1.5 border border-[#808080]">Job ID</th>
              <th className="p-1.5 border border-[#808080]">Source Repo</th>
              <th className="p-1.5 border border-[#808080]">Destination Repo</th>
              <th className="p-1.5 border border-[#808080]">Status</th>
              <th className="p-1.5 border border-[#808080]">Objects (Copied / Skip)</th>
              <th className="p-1.5 border border-[#808080]">Transferred / Total</th>
              <th className="p-1.5 border border-[#808080]">Progress</th>
              <th className="p-1.5 border border-[#808080]">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && jobs.length === 0 ? (
              <tr>
                <td colSpan={8} className="p-4 text-center text-gray-500">
                  Loading replication jobs...
                </td>
              </tr>
            ) : jobs.length === 0 ? (
              <tr>
                <td colSpan={8} className="p-4 text-center text-gray-500">
                  No replication jobs found. Click "Start New Replication Job" to replicate Recovery Points.
                </td>
              </tr>
            ) : (
              jobs.map((j) => (
                <tr key={j.id} className="hover:bg-[#e8e8e8] border-b border-[#dfdfdf]">
                  <td className="p-1 font-mono font-bold">{j.job_id}</td>
                  <td className="p-1 font-mono">Repo #{j.source_repository_id}</td>
                  <td className="p-1 font-mono">Repo #{j.destination_repository_id}</td>
                  <td className="p-1">
                    <span className={`px-1.5 py-0.5 text-[9px] font-bold font-mono text-white ${
                      j.status === 'COMPLETED' ? 'bg-[#008000]' :
                      j.status === 'RUNNING' ? 'bg-[#000080]' :
                      j.status === 'PAUSED' ? 'bg-[#d4a017]' :
                      j.status === 'QUEUED' ? 'bg-[#404040]' :
                      'bg-[#800000]'
                    }`}>
                      {j.status}
                    </span>
                  </td>
                  <td className="p-1 font-mono">
                    {j.completed_objects} / {j.total_objects} ({j.skipped_objects} skipped)
                  </td>
                  <td className="p-1 font-mono">
                    {formatBytes(j.transferred_bytes)} / {formatBytes(j.total_bytes)}
                  </td>
                  <td className="p-1 w-32">
                    <div className="w-full bg-[#dfdfdf] win-inset h-3 relative">
                      <div 
                        className="bg-[#000080] h-full"
                        style={{ width: `${Math.min(100, Math.max(0, j.progress_percent))}%` }}
                      />
                      <span className="absolute inset-0 flex items-center justify-center text-[8px] font-mono font-bold text-black mix-blend-difference">
                        {j.progress_percent.toFixed(1)}%
                      </span>
                    </div>
                  </td>
                  <td className="p-1">
                    <div className="flex gap-1">
                      {j.status === 'RUNNING' && (
                        <button
                          onClick={() => handlePause(j.job_id)}
                          className="win-btn px-1.5 py-0.5 text-[10px]"
                        >
                          Pause
                        </button>
                      )}
                      {(j.status === 'PAUSED' || j.status === 'QUEUED') && (
                        <button
                          onClick={() => handleResume(j.job_id)}
                          className="win-btn px-1.5 py-0.5 text-[10px]"
                        >
                          Resume
                        </button>
                      )}
                      {(j.status === 'FAILED' || j.status === 'PARTIAL') && (
                        <button
                          onClick={() => handleRetry(j.job_id)}
                          className="win-btn px-1.5 py-0.5 text-[10px] font-bold"
                        >
                          Retry
                        </button>
                      )}
                      {j.status !== 'COMPLETED' && j.status !== 'CANCELLED' && (
                        <button
                          onClick={() => handleCancel(j.job_id)}
                          className="win-btn px-1.5 py-0.5 text-[10px] text-[#aa0000]"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* New Replication Job Modal */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="win-outset bg-[#c0c0c0] w-[460px] p-2 flex flex-col gap-3 shadow-2xl">
            <div className="bg-[#000080] text-white font-bold p-1 flex justify-between items-center text-xs">
              <span>Start New Replication Job</span>
              <button onClick={() => setShowNewModal(false)} className="text-white hover:bg-red-600 px-1 font-bold">×</button>
            </div>

            <div className="flex flex-col gap-2 p-1 text-[11px]">
              <div>
                <label className="font-semibold block mb-0.5">Source Repository (Primary):</label>
                <select
                  value={sourceRepoId}
                  onChange={(e) => setSourceRepoId(parseInt(e.target.value))}
                  className="w-full win-inset bg-white p-1"
                >
                  {repos.map(r => (
                    <option key={r.id} value={r.id}>
                      {r.name} ({r.repository_type}) - {r.status}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-semibold block mb-0.5">Destination Repository (Secondary / Offsite):</label>
                <select
                  value={destRepoId}
                  onChange={(e) => setDestRepoId(parseInt(e.target.value))}
                  className="w-full win-inset bg-white p-1"
                >
                  {repos.map(r => (
                    <option key={r.id} value={r.id}>
                      {r.name} ({r.repository_type}) - {r.status}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="font-semibold block mb-0.5">Bandwidth Limit (MB/s):</label>
                <input
                  type="number"
                  value={bwLimit}
                  onChange={(e) => setBwLimit(e.target.value)}
                  className="w-full win-inset bg-white p-1 font-mono"
                  placeholder="e.g. 50 (leave empty for unlimited)"
                />
              </div>

              <div className="p-2 win-inset bg-[#f0f0f0] text-[10px] text-gray-700">
                <strong>CAS Deduplication Rule:</strong> Objects already existing with verified SHA-256 hashes on the destination repository will be skipped automatically without retransfer.
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-[#808080] pt-2">
              <button
                onClick={() => setShowNewModal(false)}
                className="win-btn px-3 py-1"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                className="win-btn px-4 py-1 font-bold bg-[#dfdfdf]"
              >
                Start Replication
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
