import React from 'react';
import { useApp } from '../context/AppContext';
import { WinPanel } from '../components/win95/WinPanel';
import { WinButton } from '../components/win95/WinButton';
import { HardDriveIcon, ShieldCheckIcon, CheckIcon } from '../components/win95/WinIcons';

export const StoragePage: React.FC = () => {
  const { storage, verifyStorage, addToast } = useApp();

  const usedPercent = (storage.usedTb / storage.totalTb) * 100;
  const freePercent = (storage.freeTb / storage.totalTb) * 100;

  // Uncompressed size estimate
  const uncompressedTb = +(storage.usedTb * storage.dedupRatio * storage.compressionRatio).toFixed(1);
  const totalSavedTb = +(uncompressedTb - storage.usedTb).toFixed(1);

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-y-auto bg-[#c0c0c0]">
      {/* Header */}
      <div className="win-outset px-3 py-2 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-2">
          <HardDriveIcon size={22} />
          <div>
            <h1 className="text-[13px] font-bold text-black m-0 leading-tight">
              Storage Repository & Disk Management Console
            </h1>
            <p className="text-[10px] text-[#505050] m-0">
              Primary Backup Target Volume: {storage.repositoryPath} (NTFS / ReFS Cluster)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <WinButton isDefault onClick={verifyStorage}>
            <ShieldCheckIcon size={14} />
            <span>Verify Integrity Scrub</span>
          </WinButton>
          <WinButton
            onClick={() => {
              addToast('Compaction', 'Defragmentation and block compaction initiated for D:\\BackupRepository.', 'info');
            }}
          >
            Compact Deduplication Table
          </WinButton>
          <WinButton
            onClick={() => {
              addToast('Pruning', 'Pruned 18 snapshots past 7-day policy retention window.', 'success');
            }}
          >
            Prune Expired
          </WinButton>
        </div>
      </div>

      {/* Classic Windows 95 Disk Management Representation */}
      <WinPanel title="DISK 1 — LOGICAL BACKUP VOLUMES" className="bg-[#c0c0c0]">
        <div className="flex flex-col gap-2 p-1">
          {/* Drive header */}
          <div className="flex items-center gap-2 text-[11px] font-sans">
            <span className="font-bold text-black font-mono">D: [BackupRepository]</span>
            <span className="text-[#606060]">| File System: <b>NTFS / ReFS</b></span>
            <span className="text-[#606060]">| Status: <b className="text-[#008000]">Healthy (Active)</b></span>
            <span className="text-[#606060]">| Cluster Size: <b>64 KB</b></span>
          </div>

          {/* Visual Disk Partition Map */}
          <div className="win-inset-gray h-16 p-1 bg-[#dfdfdf] flex gap-1 select-none">
            {/* Used Partition */}
            <div
              className="win-outset bg-[#000080] text-white p-1 flex flex-col justify-between overflow-hidden shadow-xs cursor-default"
              style={{ width: `${usedPercent}%` }}
              title={`Used Space: ${storage.usedTb} TB (${usedPercent.toFixed(1)}%)`}
            >
              <div className="font-mono text-[10px] font-bold truncate">
                Used: {storage.usedTb} TB ({usedPercent.toFixed(1)}%)
              </div>
              <div className="text-[9px] font-mono text-[#a0c0ff] truncate">
                Encrypted Deduplicated Blocks
              </div>
            </div>

            {/* Free Partition */}
            <div
              className="win-outset bg-[#c0c0c0] text-black p-1 flex flex-col justify-between overflow-hidden shadow-xs cursor-default"
              style={{ width: `${freePercent}%` }}
              title={`Free Space: ${storage.freeTb} TB (${freePercent.toFixed(1)}%)`}
            >
              <div className="font-mono text-[10px] font-bold text-[#006000] truncate">
                Free: {storage.freeTb} TB ({freePercent.toFixed(1)}%)
              </div>
              <div className="text-[9px] font-mono text-[#505050] truncate">
                Unallocated Backup Capacity
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-[10px] text-[#404040]">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 bg-[#000080] inline-block border border-black" />
                <span>Primary Backup Blocks ({storage.usedTb} TB)</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 bg-[#c0c0c0] inline-block border border-black" />
                <span>Free Repository Space ({storage.freeTb} TB)</span>
              </span>
            </div>
            <span className="font-mono font-bold text-black">
              Total Array Capacity: {storage.totalTb} TB (10,240 GB)
            </span>
          </div>
        </div>
      </WinPanel>

      {/* Grid of Telemetry & Optimization Statistics */}
      <div className="grid grid-cols-3 gap-2">
        {/* Panel 1: Repository Health & Hardware */}
        <WinPanel title="REPOSITORY STATUS & HARDWARE" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-2 p-1 text-[11px]">
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Repository Path:</span>
              <span className="font-mono font-bold text-black">{storage.repositoryPath}</span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Hardware Disk Health:</span>
              <span className="font-bold text-[#008000] flex items-center gap-1">
                <CheckIcon size={12} />
                <span>{storage.diskHealth}</span>
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">I/O RAID Configuration:</span>
              <span className="font-mono text-black font-semibold">RAID-6 (Dual Parity)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#505050]">Last S.M.A.R.T. Scrub:</span>
              <span className="font-mono text-[10px] text-black">{storage.lastVerification}</span>
            </div>
          </div>
        </WinPanel>

        {/* Panel 2: Backup Objects & Catalog */}
        <WinPanel title="OBJECT CATALOG METRICS" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-2 p-1 text-[11px]">
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Total Backup Objects:</span>
              <span className="font-mono font-bold text-black">
                {storage.backupObjectsCount.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Active Recovery Points:</span>
              <span className="font-mono font-bold text-[#000080]">
                {storage.recoveryPointsCount.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Index Database Health:</span>
              <span className="font-semibold text-[#008000]">Consistent (0 orphaned)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#505050]">Average Snapshot Size:</span>
              <span className="font-mono text-black font-semibold">490.8 MB</span>
            </div>
          </div>
        </WinPanel>

        {/* Panel 3: Deduplication & Compression Ratios */}
        <WinPanel title="EFFICIENCY & DATA REDUCTION" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-2 p-1 text-[11px]">
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Deduplication Ratio:</span>
              <span className="font-mono font-bold text-[#000080] text-[13px]">
                {storage.dedupRatio}:1
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Compression Ratio:</span>
              <span className="font-mono font-bold text-[#000080] text-[13px]">
                {storage.compressionRatio}:1
              </span>
            </div>
            <div className="flex justify-between border-b border-[#808080] pb-1">
              <span className="text-[#505050]">Logical Uncompressed Data:</span>
              <span className="font-mono font-bold text-black">{uncompressedTb} TB</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#505050]">Storage Space Saved:</span>
              <span className="font-mono font-bold text-[#008000]">{totalSavedTb} TB</span>
            </div>
          </div>
        </WinPanel>
      </div>

      {/* Retention Policy Summary */}
      <div className="win-fieldset p-2 bg-[#c0c0c0]">
        <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
          REPOSITORY RETENTION & PURGE SCHEDULE
        </legend>
        <div className="grid grid-cols-4 gap-2 text-[11px] p-1 font-sans">
          <div className="win-inset bg-white p-2">
            <span className="text-[#606060] block font-medium">Hourly Snapshots:</span>
            <span className="font-bold text-black">Retained 24 Hours</span>
            <span className="text-[9px] text-[#404040] block mt-1">Granular rollbacks for work-in-progress</span>
          </div>
          <div className="win-inset bg-white p-2">
            <span className="text-[#606060] block font-medium">Daily Recovery Points:</span>
            <span className="font-bold text-black">Retained 7 Days</span>
            <span className="text-[9px] text-[#404040] block mt-1">Standard workstation policy baseline</span>
          </div>
          <div className="win-inset bg-white p-2">
            <span className="text-[#606060] block font-medium">Weekly Synthetic Fulls:</span>
            <span className="font-bold text-black">Retained 4 Weeks</span>
            <span className="text-[9px] text-[#404040] block mt-1">Consolidated deduplicated baseline</span>
          </div>
          <div className="win-inset bg-white p-2">
            <span className="text-[#606060] block font-medium">Monthly Archival:</span>
            <span className="font-bold text-black">Retained 12 Months</span>
            <span className="text-[9px] text-[#404040] block mt-1">Legal and finance vault compliance</span>
          </div>
        </div>
      </div>
    </div>
  );
};
