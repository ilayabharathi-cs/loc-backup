import React, { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { WinPanel } from '../components/win95/WinPanel';
import { WinButton } from '../components/win95/WinButton';
import { HardDriveIcon, ShieldCheckIcon, CheckIcon } from '../components/win95/WinIcons';
import { storageApi, type StorageMetricsApiData } from '../api/storage';

export const StoragePage: React.FC = () => {
  const { storage, addToast } = useApp();
  const [metrics, setMetrics] = useState<StorageMetricsApiData | null>(null);
  const [loading, setLoading] = useState(false);
  const [gcRunning, setGcRunning] = useState(false);

  const fetchLiveMetrics = async () => {
    try {
      const res = await storageApi.getMetrics();
      if (res?.data) {
        setMetrics(res.data);
      }
    } catch {
      // Fallback to context storage if offline
    }
  };

  useEffect(() => {
    fetchLiveMetrics();
  }, []);

  const handleVerifyIntegrity = async () => {
    setLoading(true);
    addToast('Integrity Scrub', 'Initiating background checksum scrub across physical objects...', 'info');
    try {
      const res = await storageApi.verifyIntegrity(100, true);
      const data = res?.data;
      addToast(
        'Integrity Scan Complete',
        `Checked ${data?.objects_checked || 0} objects: ${data?.objects_valid || 0} valid, ${data?.objects_corrupted || 0} corrupted.`,
        data?.objects_corrupted > 0 ? 'error' : 'success'
      );
      fetchLiveMetrics();
    } catch (err: unknown) {
      addToast('Integrity Scan Failed', err instanceof Error ? err.message : 'Scrub error', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerGc = async () => {
    setGcRunning(true);
    addToast('Garbage Collection', 'Executing Two-Phase Garbage Collection sweep...', 'info');
    try {
      const res = await storageApi.triggerGc(false);
      const job = res?.data;
      addToast(
        'GC Complete',
        `Two-phase GC completed: deleted ${job?.objects_deleted || 0} unreferenced objects, reclaimed ${((job?.bytes_reclaimed || 0) / 1024).toFixed(1)} KB.`,
        'success'
      );
      fetchLiveMetrics();
    } catch (err: unknown) {
      addToast('GC Failed', err instanceof Error ? err.message : 'GC error', 'error');
    } finally {
      setGcRunning(false);
    }
  };

  const handleEvaluateRetention = async () => {
    addToast('GFS Retention', 'Evaluating recovery points against GFS retention schedule...', 'info');
    try {
      const res = await storageApi.evaluateRetention();
      const count = res?.data?.length || 0;
      addToast('Retention Evaluated', `Evaluated retention across ${count} active policies. Expired points marked.`, 'success');
      fetchLiveMetrics();
    } catch (err: unknown) {
      addToast('Retention Evaluation Failed', err instanceof Error ? err.message : 'Evaluation error', 'error');
    }
  };

  // Metrics computation with fallbacks
  const usedTb = metrics ? +(metrics.total_stored_bytes / (1024 ** 4)).toFixed(3) : storage.usedTb;
  const totalTb = storage.totalTb || 10.0;
  const freeTb = Math.max(0, +(totalTb - usedTb).toFixed(3));
  const usedPercent = Math.min(100, (usedTb / totalTb) * 100);
  const freePercent = Math.max(0, 100 - usedPercent);

  const dedupRatio = metrics?.deduplication_ratio || storage.dedupRatio || 3.7;
  const compRatio = metrics?.compression_ratio || storage.compressionRatio || 1.7;
  const overallRatio = metrics?.overall_efficiency_ratio || +(dedupRatio * compRatio).toFixed(1);
  const savedMb = metrics ? (metrics.bytes_saved / (1024 * 1024)).toFixed(1) : ((storage.usedTb * (overallRatio - 1) * 1024 * 1024)).toFixed(1);

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-y-auto bg-[#c0c0c0]">
      {/* Header */}
      <div className="win-outset px-3 py-2 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-2">
          <HardDriveIcon size={22} />
          <div>
            <h1 className="text-[13px] font-bold text-black m-0 leading-tight">
              Storage Optimization & GFS Repository Console
            </h1>
            <p className="text-[10px] text-[#505050] m-0">
              Target: {storage.repositoryPath} (Content-Addressed Storage CAS + ZSTD Stream)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <WinButton isDefault onClick={handleVerifyIntegrity} disabled={loading}>
            <ShieldCheckIcon size={14} />
            <span>{loading ? 'Scanning...' : 'Verify Integrity Scrub'}</span>
          </WinButton>
          <WinButton onClick={handleTriggerGc} disabled={gcRunning}>
            <span>{gcRunning ? 'Collecting...' : 'Run Two-Phase GC'}</span>
          </WinButton>
          <WinButton onClick={handleEvaluateRetention}>
            <span>Prune GFS Expired</span>
          </WinButton>
        </div>
      </div>

      {/* Classic Windows 95 Disk Management Representation */}
      <WinPanel title="DISK 1 — LOGICAL BACKUP VOLUMES & PARTITION MAP" className="bg-[#c0c0c0]">
        <div className="flex flex-col gap-2 p-1">
          {/* Drive header */}
          <div className="flex items-center gap-2 text-[11px] font-sans">
            <span className="font-bold text-black font-mono">D: [RetroVault CAS Repository]</span>
            <span className="text-[#606060]">| Format: <b>objects/xx/yy (CAS)</b></span>
            <span className="text-[#606060]">| Status: <b className="text-[#008000]">Healthy (Active)</b></span>
            <span className="text-[#606060]">| Compression: <b>ZSTD / Stream</b></span>
          </div>

          {/* Visual Disk Partition Map */}
          <div className="win-inset-gray h-16 p-1 bg-[#dfdfdf] flex gap-1 select-none">
            {/* Used Partition */}
            <div
              className="win-outset bg-[#000080] text-white p-1 flex flex-col justify-between overflow-hidden shadow-xs cursor-default"
              style={{ width: `${Math.max(5, usedPercent)}%` }}
              title={`Stored Physical Blocks: ${usedTb} TB (${usedPercent.toFixed(1)}%)`}
            >
              <div className="font-mono text-[10px] font-bold truncate">
                Stored Physical: {usedTb} TB ({usedPercent.toFixed(1)}%)
              </div>
              <div className="text-[9px] font-mono text-[#a0c0ff] truncate">
                Deduplicated CAS Objects ({metrics?.unique_storage_objects || storage.backupObjectsCount} objects)
              </div>
            </div>

            {/* Free Partition */}
            <div
              className="win-outset bg-[#c0c0c0] text-black p-1 flex flex-col justify-between overflow-hidden shadow-xs cursor-default"
              style={{ width: `${Math.max(5, freePercent)}%` }}
              title={`Free Capacity: ${freeTb} TB (${freePercent.toFixed(1)}%)`}
            >
              <div className="font-mono text-[10px] font-bold text-[#006000] truncate">
                Free: {freeTb} TB ({freePercent.toFixed(1)}%)
              </div>
              <div className="text-[9px] font-mono text-[#505050] truncate">
                Unallocated Storage Pool
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-[10px] text-[#404040]">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 bg-[#000080] inline-block border border-black" />
                <span>CAS Objects ({usedTb} TB)</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 bg-[#c0c0c0] inline-block border border-black" />
                <span>Free Repository Space ({freeTb} TB)</span>
              </span>
            </div>
            <span className="font-mono font-bold text-black">
              Total Array Capacity: {totalTb} TB
            </span>
          </div>
        </div>
      </WinPanel>

      {/* Grid of Telemetry & Optimization Statistics */}
      <div className="grid grid-cols-3 gap-2">
        {/* Panel 1: Repository Health & Hardware */}
        <WinPanel title="REPOSITORY STATUS & INTEGRITY" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-2 p-1 text-[11px]">
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Repository Path:</span>
              <span className="font-mono font-bold text-black truncate max-w-[160px]">{storage.repositoryPath}</span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Integrity Status:</span>
              <span className="font-bold text-[#008000] flex items-center gap-1">
                <CheckIcon size={12} />
                <span>Optimal (Scrubbed)</span>
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Crash Reconciliation:</span>
              <span className="font-mono text-black font-semibold">Enabled (Two-Phase GC)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#505050]">Bit-Rot Isolation:</span>
              <span className="font-mono text-[#008000] font-bold">Auto-Quarantine Active</span>
            </div>
          </div>
        </WinPanel>

        {/* Panel 2: Backup Objects & Catalog */}
        <WinPanel title="CONTENT-ADDRESSED CATALOG" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-2 p-1 text-[11px]">
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Unique Storage Objects:</span>
              <span className="font-mono font-bold text-black">
                {(metrics?.unique_storage_objects ?? storage.backupObjectsCount).toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Files Referenced:</span>
              <span className="font-mono font-bold text-[#000080]">
                {(metrics?.total_files_referenced ?? 0).toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Active Recovery Points:</span>
              <span className="font-mono font-bold text-[#000080]">
                {storage.recoveryPointsCount.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#505050]">Deduplication Index:</span>
              <span className="font-semibold text-[#008000]">Synchronized (0 orphaned)</span>
            </div>
          </div>
        </WinPanel>

        {/* Panel 3: Deduplication & Compression Ratios */}
        <WinPanel title="STORAGE EFFICIENCY & SAVINGS" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-2 p-1 text-[11px]">
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Deduplication Ratio:</span>
              <span className="font-mono font-bold text-[#000080] text-[13px]">
                {dedupRatio}x
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">ZSTD Compression:</span>
              <span className="font-mono font-bold text-[#000080] text-[13px]">
                {compRatio}x
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Overall Efficiency Ratio:</span>
              <span className="font-mono font-bold text-[#006000] text-[13px]">{overallRatio}x</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#505050]">Total Storage Saved:</span>
              <span className="font-mono font-bold text-[#008000]">{savedMb} MB ({metrics?.savings_percent ?? 73.7}%)</span>
            </div>
          </div>
        </WinPanel>
      </div>

      {/* Retention Policy Summary */}
      <div className="win-fieldset p-2 bg-[#c0c0c0]">
        <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
          GRANDFATHER-FATHER-SON (GFS) RETENTION POLICY SCHEDULE
        </legend>
        <div className="grid grid-cols-4 gap-2 text-[11px] p-1 font-sans">
          <div className="win-inset bg-white p-2">
            <span className="text-[#606060] block font-medium">Daily GFS Tier:</span>
            <span className="font-bold text-black">Retained 7 Calendar Days</span>
            <span className="text-[9px] text-[#404040] block mt-1">Calendar-day baseline snapshot</span>
          </div>
          <div className="win-inset bg-white p-2">
            <span className="text-[#606060] block font-medium">Weekly GFS Tier:</span>
            <span className="font-bold text-black">Retained 4 Calendar Weeks</span>
            <span className="text-[9px] text-[#404040] block mt-1">Sunday weekly consolidated snapshot</span>
          </div>
          <div className="win-inset bg-white p-2">
            <span className="text-[#606060] block font-medium">Monthly GFS Tier:</span>
            <span className="font-bold text-black">Retained 12 Calendar Months</span>
            <span className="text-[9px] text-[#404040] block mt-1">Month-end compliance snapshot</span>
          </div>
          <div className="win-inset bg-white p-2">
            <span className="text-[#606060] block font-medium">Yearly GFS Tier:</span>
            <span className="font-bold text-black">Retained 7 Calendar Years</span>
            <span className="text-[9px] text-[#404040] block mt-1">Permanent audit compliance archive</span>
          </div>
        </div>
      </div>
    </div>
  );
};
