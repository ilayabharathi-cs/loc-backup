import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import type { BackupPolicy } from '../types';
import { WinButton } from '../components/win95/WinButton';
import { WinCheckbox } from '../components/win95/WinFormControls';
import { WinDialog } from '../components/win95/WinDialog';
import { ShieldCheckIcon, ComputerIcon } from '../components/win95/WinIcons';

export const PoliciesPage: React.FC = () => {
  const { policies, clients, updatePolicy, applyPolicyToClients } = useApp();

  const [selectedPolicyId, setSelectedPolicyId] = useState<string>(policies[0]?.id || 'POL-001');
  const currentPolicy = policies.find(p => p.id === selectedPolicyId) || policies[0];

  // Editable draft state
  const [name, setName] = useState<string>(currentPolicy.name);
  const [description, setDescription] = useState<string>(currentPolicy.description);
  const [folders, setFolders] = useState(currentPolicy.protectedFolders);
  const [customFolders, setCustomFolders] = useState<string[]>(currentPolicy.customFolders);
  const [excludedPaths, setExcludedPaths] = useState<string[]>(currentPolicy.excludedPaths);
  const [backupType, setBackupType] = useState(currentPolicy.backupType);
  const [changeDetection, setChangeDetection] = useState(currentPolicy.changeDetection);
  const [rpoTarget, setRpoTarget] = useState<number>(currentPolicy.rpoTargetSeconds);
  const [compression, setCompression] = useState<boolean>(currentPolicy.compressionEnabled);
  const [encryption, setEncryption] = useState<boolean>(currentPolicy.encryptionEnabled);
  const [cpuLimit, setCpuLimit] = useState<number>(currentPolicy.cpuLimitPercent);
  const [networkLimit, setNetworkLimit] = useState<number>(currentPolicy.networkLimitMbps);
  const [retentionDays, setRetentionDays] = useState<number>(currentPolicy.retentionDays);

  const [newCustomPath, setNewCustomPath] = useState<string>('');
  const [newExcludedPath, setNewExcludedPath] = useState<string>('');

  // Apply to clients modal
  const [showApplyModal, setShowApplyModal] = useState<boolean>(false);
  const [targetClientIds, setTargetClientIds] = useState<string[]>(
    clients.filter(c => c.policyId === currentPolicy.id).map(c => c.id)
  );

  // When policy selection changes, reload draft state
  const handleSelectPolicy = (p: BackupPolicy) => {
    setSelectedPolicyId(p.id);
    setName(p.name);
    setDescription(p.description);
    setFolders(p.protectedFolders);
    setCustomFolders(p.customFolders);
    setExcludedPaths(p.excludedPaths);
    setBackupType(p.backupType);
    setChangeDetection(p.changeDetection);
    setRpoTarget(p.rpoTargetSeconds);
    setCompression(p.compressionEnabled);
    setEncryption(p.encryptionEnabled);
    setCpuLimit(p.cpuLimitPercent);
    setNetworkLimit(p.networkLimitMbps);
    setRetentionDays(p.retentionDays);
    setTargetClientIds(clients.filter(c => c.policyId === p.id).map(c => c.id));
  };

  const handleToggleFolder = (index: number) => {
    setFolders(prev => prev.map((f, i) => i === index ? { ...f, enabled: !f.enabled } : f));
  };

  const handleAddCustomFolder = () => {
    if (!newCustomPath.trim()) return;
    setCustomFolders(prev => [...prev, newCustomPath.trim()]);
    setNewCustomPath('');
  };

  const handleRemoveCustomFolder = (path: string) => {
    setCustomFolders(prev => prev.filter(p => p !== path));
  };

  const handleAddExcludedPath = () => {
    if (!newExcludedPath.trim()) return;
    setExcludedPaths(prev => [...prev, newExcludedPath.trim()]);
    setNewExcludedPath('');
  };

  const handleRemoveExcludedPath = (path: string) => {
    setExcludedPaths(prev => prev.filter(p => p !== path));
  };

  const handleSavePolicy = () => {
    const updated: BackupPolicy = {
      ...currentPolicy,
      name,
      description,
      protectedFolders: folders,
      customFolders,
      excludedPaths,
      backupType,
      changeDetection,
      rpoTargetSeconds: rpoTarget,
      compressionEnabled: compression,
      encryptionEnabled: encryption,
      cpuLimitPercent: cpuLimit,
      networkLimitMbps: networkLimit,
      retentionDays,
    };
    updatePolicy(updated);
  };

  const handleConfirmApply = () => {
    applyPolicyToClients(currentPolicy.id, targetClientIds);
    setShowApplyModal(false);
  };

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-hidden bg-[#c0c0c0]">
      {/* Top Banner */}
      <div className="win-outset px-3 py-1.5 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-2">
          <ShieldCheckIcon size={20} />
          <div>
            <h1 className="text-[13px] font-bold text-black m-0 leading-tight">
              Enterprise Workstation Backup Policy Manager
            </h1>
            <p className="text-[10px] text-[#505050] m-0">
              Configure universal logical path definitions, NTFS USN triggers, throttling, and retention
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <WinButton isDefault onClick={handleSavePolicy}>
            Save Policy
          </WinButton>
          <WinButton onClick={() => setShowApplyModal(true)}>
            Apply to Clients...
          </WinButton>
          <WinButton onClick={() => handleSelectPolicy(currentPolicy)}>
            Cancel / Revert
          </WinButton>
        </div>
      </div>

      {/* Main Dual Pane Layout */}
      <div className="flex-1 grid grid-cols-12 gap-2 min-h-0">
        {/* Left: Policy List */}
        <div className="col-span-3 win-outset p-2 flex flex-col gap-1 bg-[#c0c0c0]">
          <div className="px-2 py-1 bg-[#808080] text-white font-bold text-[10px] uppercase shadow-inner">
            Defined Backup Policies
          </div>

          <div className="win-inset bg-white flex-1 overflow-y-auto p-1 flex flex-col gap-0.5">
            {policies.map((p) => {
              const isSelected = p.id === selectedPolicyId;
              const assignedCount = clients.filter(c => c.policyId === p.id).length;

              return (
                <div
                  key={p.id}
                  className={`p-1.5 cursor-pointer select-none text-[11px] ${
                    isSelected ? 'bg-[#000080] text-white' : 'hover:bg-[#f0f0f0] text-black'
                  }`}
                  onClick={() => handleSelectPolicy(p)}
                >
                  <div className="font-bold flex items-center justify-between">
                    <span className="truncate">{p.name}</span>
                    <span className={`text-[9px] font-mono px-1 ${isSelected ? 'bg-white/20' : 'bg-[#dfdfdf] text-[#404040]'}`}>
                      {assignedCount} PCs
                    </span>
                  </div>
                  <div className={`text-[10px] truncate ${isSelected ? 'text-[#c0d8ff]' : 'text-[#606060]'}`}>
                    RPO: {p.rpoTargetSeconds}s | {p.backupType}
                  </div>
                </div>
              );
            })}
          </div>

          <WinButton
            size="sm"
            onClick={() => {
              const newId = `POL-00${policies.length + 1}`;
              const created: BackupPolicy = {
                id: newId,
                name: 'New Custom Enterprise Policy',
                description: 'Custom protection profile',
                protectedFolders: [
                  { path: '%USERPROFILE%\\Documents', isUniversal: true, enabled: true },
                  { path: '%USERPROFILE%\\Desktop', isUniversal: true, enabled: true }
                ],
                customFolders: [],
                excludedPaths: ['%TEMP%', '*.tmp'],
                backupType: 'Incremental',
                changeDetection: 'USN Journal',
                rpoTargetSeconds: 120,
                compressionEnabled: true,
                encryptionEnabled: true,
                cpuLimitPercent: 10,
                networkLimitMbps: 100,
                retentionDays: 7,
              };
              updatePolicy(created);
              handleSelectPolicy(created);
            }}
          >
            + Create New Policy
          </WinButton>
        </div>

        {/* Right: Policy Editor Details */}
        <div className="col-span-9 win-outset p-3 bg-[#c0c0c0] flex flex-col gap-2 overflow-y-auto">
          {/* Policy Title & Description */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="text-[11px] font-bold text-black block mb-0.5">Policy Name:</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="win-inset bg-white px-2 py-1 text-[11px] font-bold text-black w-full"
              />
            </div>
            <div>
              <span className="text-[11px] font-bold text-black block mb-0.5">Description:</span>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="win-inset bg-white px-2 py-1 text-[11px] text-black w-full"
              />
            </div>
          </div>

          {/* Section 1: Universal Protected Folders */}
          <div className="win-fieldset">
            <legend className="text-[10px] font-bold text-[#000080] bg-[#c0c0c0] px-1">
              UNIVERSAL PROTECTED FOLDERS (AUTOMATICALLY EXPANDED FOR EACH USER PROFILE)
            </legend>
            <div className="grid grid-cols-2 gap-2 mt-1">
              {folders.map((f, idx) => (
                <div key={idx} className="flex items-center justify-between win-inset bg-white px-2 py-1">
                  <WinCheckbox
                    label={<span className="font-mono text-[10px] font-semibold">{f.path}</span>}
                    checked={f.enabled}
                    onChange={() => handleToggleFolder(idx)}
                  />
                  <span className="text-[9px] font-mono text-[#008000] font-bold">UNIVERSAL</span>
                </div>
              ))}
            </div>
          </div>

          {/* Section 2: Custom Folders & Excluded Paths */}
          <div className="grid grid-cols-2 gap-2">
            {/* Custom Folders */}
            <div className="win-fieldset">
              <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
                ADDITIONAL CUSTOM DIRECTORIES
              </legend>
              <div className="flex flex-col gap-1 mt-1 max-h-24 overflow-y-auto">
                {customFolders.length === 0 ? (
                  <div className="text-[10px] text-[#606060] italic py-1">
                    No custom directories assigned.
                  </div>
                ) : (
                  customFolders.map((p, idx) => (
                    <div key={idx} className="win-inset bg-white px-2 py-0.5 font-mono text-[10px] text-black flex justify-between items-center">
                      <span className="truncate">{p}</span>
                      <button
                        type="button"
                        className="text-[#aa0000] hover:font-bold cursor-pointer"
                        onClick={() => handleRemoveCustomFolder(p)}
                      >
                        ×
                      </button>
                    </div>
                  ))
                )}
              </div>
              <div className="flex gap-1 mt-2">
                <input
                  type="text"
                  placeholder="e.g. D:\Projects, D:\CompanyData"
                  value={newCustomPath}
                  onChange={(e) => setNewCustomPath(e.target.value)}
                  className="win-inset bg-white px-1.5 py-0.5 text-[10px] font-mono flex-1 text-black"
                />
                <WinButton size="sm" onClick={handleAddCustomFolder}>
                  + Add
                </WinButton>
              </div>
            </div>

            {/* Excluded Paths */}
            <div className="win-fieldset">
              <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
                EXCLUDED DIRECTORIES & PATTERNS
              </legend>
              <div className="flex flex-wrap gap-1 mt-1 max-h-24 overflow-y-auto">
                {excludedPaths.map((p, idx) => (
                  <span key={idx} className="win-inset-gray px-1.5 py-0.5 font-mono text-[9px] text-black flex items-center gap-1 bg-[#dfdfdf]">
                    <span>{p}</span>
                    <button
                      type="button"
                      className="text-[#aa0000] hover:font-bold cursor-pointer"
                      onClick={() => handleRemoveExcludedPath(p)}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-1 mt-2">
                <input
                  type="text"
                  placeholder="e.g. %TEMP%, *.tmp, *.cache"
                  value={newExcludedPath}
                  onChange={(e) => setNewExcludedPath(e.target.value)}
                  className="win-inset bg-white px-1.5 py-0.5 text-[10px] font-mono flex-1 text-black"
                />
                <WinButton size="sm" onClick={handleAddExcludedPath}>
                  + Exclude
                </WinButton>
              </div>
            </div>
          </div>

          {/* Section 3: Backup Engine & USN Detection */}
          <div className="win-fieldset">
            <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
              BACKUP ENGINE & CHANGE DETECTION
            </legend>
            <div className="grid grid-cols-4 gap-3 mt-1 text-[11px]">
              <div>
                <span className="text-[#606060] block font-medium">Backup Mode:</span>
                <select
                  value={backupType}
                  onChange={(e) => setBackupType(e.target.value as 'Incremental' | 'Full')}
                  className="win-inset bg-white px-2 py-0.5 text-[11px] text-black w-full"
                >
                  <option value="Incremental">Incremental</option>
                  <option value="Full">Synthetic Full</option>
                </select>
              </div>

              <div>
                <span className="text-[#606060] block font-medium">Change Detection:</span>
                <select
                  value={changeDetection}
                  onChange={(e) => setChangeDetection(e.target.value as 'USN Journal' | 'File Watcher' | 'Timestamp')}
                  className="win-inset bg-white px-2 py-0.5 text-[11px] text-black w-full"
                >
                  <option value="USN Journal">USN Journal (NTFS)</option>
                  <option value="File Watcher">Win32 ReadDirectoryChanges</option>
                  <option value="Timestamp">MFT Timestamp Polling</option>
                </select>
              </div>

              <div>
                <span className="text-[#606060] block font-medium">Target RPO (Latency):</span>
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    min="30"
                    max="3600"
                    value={rpoTarget}
                    onChange={(e) => setRpoTarget(Number(e.target.value))}
                    className="win-inset bg-white px-2 py-0.5 text-[11px] font-mono font-bold text-black w-20"
                  />
                  <span className="text-[10px] text-[#404040]">sec ({Math.round(rpoTarget / 60)} min)</span>
                </div>
              </div>

              <div className="flex flex-col gap-1 pt-3">
                <WinCheckbox
                  label="Compression: Enabled (LZ4)"
                  checked={compression}
                  onChange={setCompression}
                />
                <WinCheckbox
                  label="Encryption: AES-256"
                  checked={encryption}
                  onChange={setEncryption}
                />
              </div>
            </div>
          </div>

          {/* Section 4: Performance & Retention */}
          <div className="grid grid-cols-2 gap-3">
            <div className="win-fieldset">
              <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
                RESOURCE THROTTLING
              </legend>
              <div className="grid grid-cols-2 gap-2 mt-1 text-[11px]">
                <div>
                  <span className="text-[#606060] block">CPU Throttling Limit:</span>
                  <input
                    type="number"
                    min="5"
                    max="100"
                    value={cpuLimit}
                    onChange={(e) => setCpuLimit(Number(e.target.value))}
                    className="win-inset bg-white px-2 py-0.5 font-mono text-[11px] text-black w-20"
                  />
                  <span className="text-[10px] text-[#505050] ml-1">% Max</span>
                </div>
                <div>
                  <span className="text-[#606060] block">Network Bandwidth Cap:</span>
                  <input
                    type="number"
                    min="10"
                    max="1000"
                    value={networkLimit}
                    onChange={(e) => setNetworkLimit(Number(e.target.value))}
                    className="win-inset bg-white px-2 py-0.5 font-mono text-[11px] text-black w-20"
                  />
                  <span className="text-[10px] text-[#505050] ml-1">Mbps</span>
                </div>
              </div>
            </div>

            <div className="win-fieldset">
              <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
                RETENTION RULES
              </legend>
              <div className="flex items-center gap-2 mt-1 text-[11px]">
                <span className="text-[#606060]">Retain Daily Snapshots For:</span>
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={retentionDays}
                  onChange={(e) => setRetentionDays(Number(e.target.value))}
                  className="win-inset bg-white px-2 py-0.5 font-mono font-bold text-black w-16"
                />
                <span className="text-[#404040]">days</span>
                <span className="text-[10px] text-[#000080] font-semibold ml-2">
                  (~{retentionDays * 24} hourly checkpoints)
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Apply to Clients Modal */}
      <WinDialog
        isOpen={showApplyModal}
        onClose={() => setShowApplyModal(false)}
        title={`Apply Policy "${currentPolicy.name}" to Enterprise Clients`}
        icon={<ComputerIcon size={16} />}
        width={520}
        okText="Apply Policy"
        onOk={handleConfirmApply}
      >
        <div className="flex flex-col gap-2">
          <p className="text-[11px] text-black m-0">
            Check the workstations that should adopt this backup policy. Universal paths will be logically expanded according to each client's user profile:
          </p>

          <div className="win-inset bg-white p-1 max-h-60 overflow-y-auto flex flex-col gap-0.5">
            {clients.map((c) => {
              const isChecked = targetClientIds.includes(c.id);

              return (
                <div
                  key={c.id}
                  className="flex items-center justify-between px-2 py-1 hover:bg-[#f0f0f0] text-[11px]"
                >
                  <WinCheckbox
                    label={
                      <span className="font-mono text-[10px]">
                        <b>{c.hostname}</b> ({c.id}) — {c.user}
                      </span>
                    }
                    checked={isChecked}
                    onChange={() => {
                      setTargetClientIds(prev => 
                        isChecked ? prev.filter(id => id !== c.id) : [...prev, c.id]
                      );
                    }}
                  />
                  <span className="text-[9px] font-mono text-[#606060]">
                    Current: {c.policyName}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="flex justify-between items-center text-[10px] text-[#404040] pt-1">
            <div className="flex gap-2">
              <button
                type="button"
                className="underline hover:text-black cursor-pointer"
                onClick={() => setTargetClientIds(clients.map(c => c.id))}
              >
                Select All 20 Clients
              </button>
              <button
                type="button"
                className="underline hover:text-black cursor-pointer"
                onClick={() => setTargetClientIds([])}
              >
                Clear Selection
              </button>
            </div>
            <span><b>{targetClientIds.length}</b> workstations selected</span>
          </div>
        </div>
      </WinDialog>
    </div>
  );
};
