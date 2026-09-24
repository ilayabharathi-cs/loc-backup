import React, { useState, useEffect } from 'react';
import {
  getObservabilityOverview
} from '../api/v10';
import type { ObservabilityOverview } from '../api/v10';
import axios from 'axios';

export const ObservabilityPage: React.FC = () => {
  const [data, setData] = useState<ObservabilityOverview | null>(null);
  const [window, setWindow] = useState<string>('24h');
  const [loading, setLoading] = useState<boolean>(true);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getObservabilityOverview(window);
      setData(res);
    } catch (e: any) {
      console.error('Error loading observability:', e);
      setStatusMsg(`Observability error: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [window]);

  const handlePrune = async () => {
    try {
      const res = await axios.post('/api/v1/observability/prune');
      setStatusMsg(`Telemetry pruned successfully: ${JSON.stringify(res.data)}`);
      await loadData();
    } catch (e: any) {
      setStatusMsg(`Prune error: ${e.message}`);
    }
  };

  const handleDownsample = async () => {
    try {
      const res = await axios.post('/api/v1/observability/downsample');
      setStatusMsg(`Downsampling rollups generated: ${JSON.stringify(res.data)}`);
      await loadData();
    } catch (e: any) {
      setStatusMsg(`Downsample error: ${e.message}`);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#c0c0c0] p-2 overflow-auto text-[11px]">
      {/* Title Bar Area */}
      <div className="win-outset p-2 mb-2 bg-[#dfdfdf] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-[#000080]" />
          <span className="font-bold text-[12px] text-[#000080]">
            RetroVault Telemetry & Observability Center
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[#666666]">Time Window:</span>
          <select
            value={window}
            onChange={(e) => setWindow(e.target.value)}
            className="win-inset px-1 py-0.5 text-[11px] bg-white font-mono"
          >
            <option value="1h">1 Hour</option>
            <option value="6h">6 Hours</option>
            <option value="24h">24 Hours</option>
            <option value="7d">7 Days</option>
            <option value="30d">30 Days</option>
            <option value="90d">90 Days</option>
          </select>
          <button onClick={loadData} className="win-btn px-2 py-0.5 text-[11px] font-bold">
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="win-inset p-1.5 mb-2 bg-[#ffffe0] text-[#000000] flex justify-between items-center text-[11px]">
          <span>{statusMsg}</span>
          <button onClick={() => setStatusMsg(null)} className="font-bold text-[#b91c1c]">×</button>
        </div>
      )}

      {/* Real-Time Host & Cluster Resources */}
      {data && (
        <div className="win-outset p-2 mb-2 bg-white">
          <div className="font-bold text-[11px] text-[#000080] mb-1">Live Subsystem Resources</div>
          <div className="grid grid-cols-6 gap-2">
            <div className="win-inset p-1.5 bg-[#f9fafb]">
              <div className="text-[#666666] text-[10px]">CPU USAGE</div>
              <div className="font-mono text-[14px] font-bold text-[#000080]">
                {data.system_resources.cpu_utilization_pct}%
              </div>
            </div>
            <div className="win-inset p-1.5 bg-[#f9fafb]">
              <div className="text-[#666666] text-[10px]">RAM USAGE</div>
              <div className="font-mono text-[14px] font-bold text-[#000080]">
                {data.system_resources.memory_utilization_pct}%
              </div>
            </div>
            <div className="win-inset p-1.5 bg-[#f9fafb]">
              <div className="text-[#666666] text-[10px]">DISK READ</div>
              <div className="font-mono text-[14px] font-bold text-[#008000]">
                {data.system_resources.disk_io_read_mbs} MB/s
              </div>
            </div>
            <div className="win-inset p-1.5 bg-[#f9fafb]">
              <div className="text-[#666666] text-[10px]">DISK WRITE</div>
              <div className="font-mono text-[14px] font-bold text-[#b91c1c]">
                {data.system_resources.disk_io_write_mbs} MB/s
              </div>
            </div>
            <div className="win-inset p-1.5 bg-[#f9fafb]">
              <div className="text-[#666666] text-[10px]">NETWORK</div>
              <div className="font-mono text-[14px] font-bold text-[#333333]">
                {data.system_resources.network_throughput_mbs} MB/s
              </div>
            </div>
            <div className="win-inset p-1.5 bg-[#f9fafb]">
              <div className="text-[#666666] text-[10px]">WORKER UTIL</div>
              <div className="font-mono text-[14px] font-bold text-[#008080]">
                {data.system_resources.worker_utilization_pct}%
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CAS Efficiency Section */}
      {data && (
        <div className="win-outset p-2 mb-2 bg-[#f0f4f8]">
          <div className="font-bold text-[11px] text-[#000080] mb-1">
            Content Addressable Storage (CAS) Deduplication & Compression Telemetry
          </div>
          <div className="grid grid-cols-5 gap-2">
            <div className="win-outset p-2 bg-white">
              <div className="text-[#666666] text-[10px]">LOGICAL BACKUP BYTES</div>
              <div className="font-mono text-[13px] font-bold text-[#000080]">
                {formatBytes(data.cas_storage_efficiency.logical_bytes)}
              </div>
              <div className="text-[9px] text-[#888888] font-mono">
                {data.cas_storage_efficiency.logical_files} files scanned
              </div>
            </div>
            <div className="win-outset p-2 bg-white">
              <div className="text-[#666666] text-[10px]">UNIQUE CAS BLOCKS</div>
              <div className="font-mono text-[13px] font-bold text-[#333333]">
                {formatBytes(data.cas_storage_efficiency.unique_bytes)}
              </div>
              <div className="text-[9px] text-[#888888] font-mono">
                {data.cas_storage_efficiency.unique_objects} stored objects
              </div>
            </div>
            <div className="win-outset p-2 bg-white">
              <div className="text-[#666666] text-[10px]">DEDUP RATIO</div>
              <div className="font-mono text-[15px] font-bold text-[#008000]">
                {data.cas_storage_efficiency.dedup_ratio}x
              </div>
              <div className="text-[9px] text-[#008000] font-mono">
                Savings: {formatBytes(data.cas_storage_efficiency.dedup_savings_bytes)}
              </div>
            </div>
            <div className="win-outset p-2 bg-white">
              <div className="text-[#666666] text-[10px]">COMPRESSION RATIO</div>
              <div className="font-mono text-[15px] font-bold text-[#008080]">
                {data.cas_storage_efficiency.compression_ratio}x
              </div>
            </div>
            <div className="win-outset p-2 bg-white">
              <div className="text-[#666666] text-[10px]">TOTAL EFFICIENCY</div>
              <div className="font-mono text-[15px] font-bold text-[#000080]">
                {data.cas_storage_efficiency.overall_efficiency}x
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Backup and Restore Performance Analytics */}
      {data && (
        <div className="grid grid-cols-2 gap-2 mb-2 flex-1">
          {/* Backup Performance */}
          <div className="win-outset p-2 bg-white flex flex-col">
            <div className="font-bold text-[11px] text-[#000080] mb-1">
              Backup Performance ({window} window, {data.backup_performance.total_runs} runs)
            </div>
            <table className="w-full border-collapse text-left text-[10px]">
              <thead>
                <tr className="bg-[#808080] text-white">
                  <th className="p-1">Metric</th>
                  <th className="p-1">Average</th>
                  <th className="p-1">Median</th>
                  <th className="p-1">p95</th>
                  <th className="p-1">Max</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[#dfdfdf]">
                  <td className="p-1 font-bold">Duration (s)</td>
                  <td className="p-1 font-mono">{data.backup_performance.duration_seconds.average}</td>
                  <td className="p-1 font-mono">{data.backup_performance.duration_seconds.median}</td>
                  <td className="p-1 font-mono font-bold text-[#b91c1c]">{data.backup_performance.duration_seconds.p95}</td>
                  <td className="p-1 font-mono">{data.backup_performance.duration_seconds.max}</td>
                </tr>
                <tr className="border-b border-[#dfdfdf]">
                  <td className="p-1 font-bold">Files Scanned</td>
                  <td className="p-1 font-mono">{data.backup_performance.files_scanned.average}</td>
                  <td className="p-1 font-mono">{data.backup_performance.files_scanned.median}</td>
                  <td className="p-1 font-mono">{data.backup_performance.files_scanned.p95}</td>
                  <td className="p-1 font-mono">{data.backup_performance.files_scanned.max}</td>
                </tr>
                <tr>
                  <td className="p-1 font-bold">Files Changed</td>
                  <td className="p-1 font-mono">{data.backup_performance.files_changed.average}</td>
                  <td className="p-1 font-mono">{data.backup_performance.files_changed.median}</td>
                  <td className="p-1 font-mono">{data.backup_performance.files_changed.p95}</td>
                  <td className="p-1 font-mono">{data.backup_performance.files_changed.max}</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Restore Performance */}
          <div className="win-outset p-2 bg-white flex flex-col">
            <div className="font-bold text-[11px] text-[#000080] mb-1">
              Restore Performance ({window} window, {data.restore_performance.total_restores} jobs)
            </div>
            <table className="w-full border-collapse text-left text-[10px]">
              <thead>
                <tr className="bg-[#808080] text-white">
                  <th className="p-1">Metric</th>
                  <th className="p-1">Average</th>
                  <th className="p-1">Median</th>
                  <th className="p-1">p95</th>
                  <th className="p-1">Max</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[#dfdfdf]">
                  <td className="p-1 font-bold">Duration (s)</td>
                  <td className="p-1 font-mono">{data.restore_performance.duration_seconds.average}</td>
                  <td className="p-1 font-mono">{data.restore_performance.duration_seconds.median}</td>
                  <td className="p-1 font-mono font-bold text-[#b91c1c]">{data.restore_performance.duration_seconds.p95}</td>
                  <td className="p-1 font-mono">{data.restore_performance.duration_seconds.max}</td>
                </tr>
                <tr className="border-b border-[#dfdfdf]">
                  <td className="p-1 font-bold">Throughput (MB/s)</td>
                  <td className="p-1 font-mono text-[#008000]">{data.restore_performance.throughput_mb_s.average}</td>
                  <td className="p-1 font-mono text-[#008000]">{data.restore_performance.throughput_mb_s.median}</td>
                  <td className="p-1 font-mono text-[#008000]">{data.restore_performance.throughput_mb_s.p95}</td>
                  <td className="p-1 font-mono text-[#008000]">{data.restore_performance.throughput_mb_s.max}</td>
                </tr>
                <tr>
                  <td className="p-1 font-bold">Files Restored</td>
                  <td className="p-1 font-mono">{data.restore_performance.files_restored.average}</td>
                  <td className="p-1 font-mono">{data.restore_performance.files_restored.median}</td>
                  <td className="p-1 font-mono">{data.restore_performance.files_restored.p95}</td>
                  <td className="p-1 font-mono">{data.restore_performance.files_restored.max}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Telemetry Maintenance Bar */}
      <div className="win-outset p-2 bg-[#dfdfdf] flex justify-between items-center">
        <div className="text-[10px] text-[#555555]">
          Telemetry Lifecycle: Raw metrics downsampled to hourly summaries. Safety invariant protects recovery points and audit logs.
        </div>
        <div className="flex gap-2">
          <button onClick={handleDownsample} className="win-btn px-2 py-0.5 text-[10px]">
            Run Downsampling Rollup
          </button>
          <button onClick={handlePrune} className="win-btn px-2 py-0.5 text-[10px] font-bold text-[#b91c1c]">
            Prune Expired Telemetry
          </button>
        </div>
      </div>
    </div>
  );
};
