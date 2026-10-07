import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import type { BackupPolicy } from '../types';
import { WinButton } from '../components/win95/WinButton';
import { WinCheckbox } from '../components/win95/WinFormControls';
import { WinDialog } from '../components/win95/WinDialog';
import { ShieldCheckIcon, ComputerIcon, BackupTapeIcon } from '../components/win95/WinIcons';

const REPOSITORY_PRESETS = [
  { id: 'repository', label: 'repository (Default Global Storage)', description: 'Primary centralized vault root' },
  { id: 'production', label: 'production (Production Department)', description: 'Mission-critical production systems' },
  { id: 'marketing', label: 'marketing (Marketing & Media)', description: 'Marketing assets, creatives, campaign data' },
  { id: 'human-resources', label: 'human-resources (HR & Personnel)', description: 'HR records, employee files, onboarding' },
  { id: 'finance', label: 'finance (Finance & Accounting)', description: 'Financial spreadsheets, ledgers, audits' },
  { id: 'engineering', label: 'engineering (Engineering & DevOps)', description: 'Source code, builds, telemetry, staging' },
  { id: 'legal', label: 'legal (Legal & Compliance)', description: 'Contracts, compliance records, NDAs' },
  { id: 'operations', label: 'operations (Operations & Logistics)', description: 'Supply chain, shipping, vendor orders' },
  { id: 'custom', label: 'custom (Custom / Enter Name Below...)', description: 'Specify any custom folder name or path' },
];

export const PoliciesPage: React.FC = () => {
  const { policies, clients, updatePolicy, applyPolicyToClients, markClientWaiting, triggerBackup } = useApp();

  const [selectedPolicyId, setSelectedPolicyId] = useState<string>(policies[0]?.id || 'POL-001');
  const currentPolicy = policies.find(p => p.id === selectedPolicyId) || policies[0];

  // Editable draft state
  const [name, setName] = useState<string>(currentPolicy.name);
  const [description, setDescription] = useState<string>(currentPolicy.description);
  const [targetRepository, setTargetRepository] = useState<string>(currentPolicy.targetRepository || 'repository');
  const [pointOfRecovery, setPointOfRecovery] = useState<'server' | 'device'>(currentPolicy.pointOfRecovery || 'server');
  const [deviceRecoveryPath, setDeviceRecoveryPath] = useState<string>(currentPolicy.deviceRecoveryPath || 'C:\\RetroVaultRecovery');
  const [recoveryDeviceName, setRecoveryDeviceName] = useState<string>(currentPolicy.recoveryDeviceName || '');
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
  const [showPromptModal, setShowPromptModal] = useState<boolean>(false);
  const [targetClientIds, setTargetClientIds] = useState<string[]>(
    clients.filter(c => c.policyId === currentPolicy.id).map(c => c.id)
  );

  // When policy selection changes, reload draft state
  const handleSelectPolicy = (p: BackupPolicy) => {
    setSelectedPolicyId(p.id);
    setName(p.name);
    setDescription(p.description);
    setTargetRepository(p.targetRepository || 'repository');
    setPointOfRecovery(p.pointOfRecovery || 'server');
    setDeviceRecoveryPath(p.deviceRecoveryPath || 'C:\\RetroVaultRecovery');
    setRecoveryDeviceName(p.recoveryDeviceName || '');
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
      targetRepository: targetRepository.trim() || 'repository',
      pointOfRecovery,
      deviceRecoveryPath: deviceRecoveryPath.trim() || 'C:\\RetroVaultRecovery',
      recoveryDeviceName: recoveryDeviceName.trim() || undefined,
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
    setShowPromptModal(true);
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
              Configure universal logical path definitions, storage destination repositories, throttling, and retention
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
                    RPO: {p.rpoTargetSeconds}s | {p.backupType} | Repo: {p.targetRepository || 'repository'}
                  </div>
                  <div className="flex items-center gap-1 mt-0.5">
                    <span className={`text-[9px] px-1 font-semibold ${
                      p.pointOfRecovery === 'device'
                        ? (isSelected ? 'bg-amber-300 text-black' : 'bg-amber-100 text-amber-900 border border-amber-300')
                        : (isSelected ? 'bg-blue-300 text-black' : 'bg-blue-50 text-blue-900 border border-blue-200')
                    }`}>
                      {p.pointOfRecovery === 'device'
                        ? `Recovery: Device (${p.recoveryDeviceName || 'Source PC'})`
                        : 'Recovery: Server Vault'}
                    </span>
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
                targetRepository: 'repository',
                pointOfRecovery: 'server',
                deviceRecoveryPath: 'C:\\RetroVaultRecovery',
                recoveryDeviceName: '',
                protectedFolders: [
                  { path: '%USERPROFILE%\\Documents', isUniversal: true, enabled: false },
                  { path: '%USERPROFILE%\\Desktop', isUniversal: true, enabled: false }
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

          {/* Section: Point of Recovery Location (Before Repository Selection) */}
          <div className="win-fieldset bg-[#c0c0c0] p-2 flex flex-col gap-2">
            <legend className="text-[10px] font-bold text-[#000080] bg-[#c0c0c0] px-1 flex items-center gap-1">
              <span>POINT OF RECOVERY LOCATION</span>
            </legend>

            <div className="flex flex-col gap-2">
              <div className="grid grid-cols-2 gap-2">
                {/* Option A: Current Server */}
                <div
                  onClick={() => setPointOfRecovery('server')}
                  className={`win-inset p-2 flex flex-col gap-1 cursor-pointer select-none transition-colors ${
                    pointOfRecovery === 'server' ? 'bg-[#e0e8ff] ring-1 ring-blue-700' : 'bg-white hover:bg-[#f8f8f8]'
                  }`}
                >
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="pointOfRecovery"
                      value="server"
                      checked={pointOfRecovery === 'server'}
                      onChange={() => setPointOfRecovery('server')}
                      className="cursor-pointer"
                    />
                    <span className="text-[11px] font-bold text-black">Current Server (Central Storage Vault)</span>
                  </label>
                  <p className="text-[10px] text-[#505050] pl-5 leading-tight">
                    Standard central backup. Recovery points are stored in the server repository and restored over network.
                  </p>
                </div>

                {/* Option B: Device (Source Machine) */}
                <div
                  onClick={() => setPointOfRecovery('device')}
                  className={`win-inset p-2 flex flex-col gap-1 cursor-pointer select-none transition-colors ${
                    pointOfRecovery === 'device' ? 'bg-[#fff5e0] ring-1 ring-amber-700' : 'bg-white hover:bg-[#f8f8f8]'
                  }`}
                >
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="pointOfRecovery"
                      value="device"
                      checked={pointOfRecovery === 'device'}
                      onChange={() => setPointOfRecovery('device')}
                      className="cursor-pointer"
                    />
                    <span className="text-[11px] font-bold text-black">Device Point of Recovery (On-Device Cache)</span>
                  </label>
                  <p className="text-[10px] text-[#505050] pl-5 leading-tight">
                    Enables local on-device recovery point on the source machine for instant SSD/NVMe speed rollback.
                  </p>
                </div>
              </div>

              {/* Option B Configuration Fields (When Device Point of Recovery is selected) */}
              {pointOfRecovery === 'device' && (
                <div className="win-outset p-2 bg-[#ececec] flex flex-col gap-2 border border-[#a0a0a0]">
                  <div className="grid grid-cols-12 gap-2 items-center">
                    {/* Device / Hostname Selector */}
                    <div className="col-span-5 flex flex-col gap-0.5">
                      <label className="text-[10px] font-bold text-black flex items-center justify-between">
                        <span>Designated Client Device:</span>
                        <span className="text-[9px] text-[#505050]">Source PC</span>
                      </label>
                      <select
                        value={recoveryDeviceName || (clients.length > 0 ? clients[0].hostname : '')}
                        onChange={(e) => setRecoveryDeviceName(e.target.value)}
                        className="win-inset bg-white px-2 py-1 text-[11px] text-black w-full cursor-pointer font-medium"
                      >
                        <option value="">-- Active Backing-up Machine --</option>
                        {clients.map(c => (
                          <option key={c.id} value={c.hostname}>
                            {c.hostname} ({c.os})
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Local Recovery Path Location on that Device */}
                    <div className="col-span-7 flex flex-col gap-0.5">
                      <label className="text-[10px] font-bold text-black flex items-center justify-between">
                        <span>Device Recovery Storage Path / Folder:</span>
                        <span className="text-[9px] text-[#000080] font-mono font-semibold">Saved & recovered location</span>
                      </label>
                      <input
                        type="text"
                        value={deviceRecoveryPath}
                        onChange={(e) => setDeviceRecoveryPath(e.target.value)}
                        placeholder="e.g. C:\RetroVaultRecovery or D:\LocalBackupPoint"
                        className="win-inset bg-white px-2 py-1 text-[11px] font-mono font-bold text-black w-full"
                      />
                    </div>
                  </div>

                  <div className="text-[10px] text-[#603000] flex items-start gap-1.5 bg-[#fff8e6] px-2 py-1.5 border border-[#dfc890]">
                    <span className="text-[12px] leading-none">📂</span>
                    <span className="leading-tight">
                      <strong>On-Device Recovery Active:</strong> In the Recovery/Restore page, selecting <strong>"Source Recovery"</strong> will list this device (<span className="font-mono font-bold">{recoveryDeviceName || 'Source PC'}</span>). Recovered files can be written directly to this specified location (<span className="font-mono font-bold">{deviceRecoveryPath || 'C:\\RetroVaultRecovery'}</span>) or back to original source paths.
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Section: Target Backup Repository / Storage Destination */}
          <div className="win-fieldset bg-[#c0c0c0] p-2 flex flex-col gap-2">
            <legend className="text-[10px] font-bold text-[#000080] bg-[#c0c0c0] px-1 flex items-center gap-1">
              <span>SERVER BACKUP REPOSITORY / DESTINATION STORAGE FOLDER</span>
            </legend>

            <div className="grid grid-cols-12 gap-2 items-center">
              {/* Dropdown / Scroll Selector with Suggested Departments */}
              <div className="col-span-5 flex flex-col gap-0.5">
                <label className="text-[10px] font-bold text-black flex items-center justify-between">
                  <span>Suggested Department Presets:</span>
                  <span className="text-[9px] text-[#505050] font-normal">Scroll & select</span>
                </label>
                <select
                  value={REPOSITORY_PRESETS.some(p => p.id === targetRepository) ? targetRepository : 'custom'}
                  onChange={(e) => {
                    if (e.target.value !== 'custom') {
                      setTargetRepository(e.target.value);
                    }
                  }}
                  className="win-inset bg-white px-2 py-1 text-[11px] text-black w-full cursor-pointer font-medium"
                >
                  {REPOSITORY_PRESETS.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Direct Folder Name / Path Input */}
              <div className="col-span-7 flex flex-col gap-0.5">
                <label className="text-[10px] font-bold text-black flex items-center justify-between">
                  <span>Custom Target Folder Name / Input:</span>
                  <span className="text-[9px] text-[#000080] font-mono font-semibold">e.g. production hr, marketing, D:\Backups\HR</span>
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="text"
                    value={targetRepository}
                    onChange={(e) => setTargetRepository(e.target.value)}
                    placeholder="e.g. production hr, marketing, hr, or path"
                    className="win-inset bg-white px-2 py-1 text-[11px] font-mono font-bold text-black flex-1"
                  />
                  <WinButton
                    size="sm"
                    onClick={() => setTargetRepository('repository')}
                    title="Reset to default root repository"
                  >
                    Reset Default
                  </WinButton>
                </div>
              </div>
            </div>

            {/* Scrollable Quick Selection Badges */}
            <div className="flex items-center gap-1 overflow-x-auto py-1">
              <span className="text-[9px] font-bold text-[#404040] uppercase shrink-0">Quick Options:</span>
              {['repository', 'production', 'marketing', 'human-resources', 'finance', 'engineering', 'production hr'].map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setTargetRepository(opt)}
                  className={`px-2 py-0.5 text-[10px] font-mono border cursor-pointer whitespace-nowrap transition-colors ${
                    targetRepository === opt
                      ? 'bg-[#000080] text-white border-black font-bold shadow-inner'
                      : 'bg-[#dcdcdc] text-black border-[#808080] hover:bg-white'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>

            {/* Live Server Destination Path Preview */}
            <div className="win-inset bg-[#e8e8e8] px-2 py-1 text-[10px] font-mono flex items-center justify-between text-[#333333]">
              <div className="truncate">
                <span className="font-bold text-[#000080]">Server Storage Target: </span>
                <span className="text-black font-semibold">
                  {targetRepository && targetRepository !== 'repository' && !targetRepository.includes(':') && !targetRepository.startsWith('/')
                    ? `<REPOSITORY_ROOT>/${targetRepository}/clients/<client_id>/runs/<run_id>/objects/`
                    : targetRepository && (targetRepository.includes(':') || targetRepository.startsWith('/'))
                    ? `${targetRepository}/clients/<client_id>/runs/<run_id>/objects/`
                    : `<REPOSITORY_ROOT>/clients/<client_id>/runs/<run_id>/objects/ (Default)`}
                </span>
              </div>
              <span className="text-[9px] px-1 bg-[#c0c0c0] border border-[#808080] font-sans font-semibold shrink-0 ml-2">
                Isolated Folder
              </span>
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

      {/* Start or Wait Backup Prompt Modal */}
      <WinDialog
        isOpen={showPromptModal}
        onClose={() => setShowPromptModal(false)}
        title="Backup Confirmation"
        icon={<BackupTapeIcon size={16} />}
        width={350}
        okText="Start Backup"
        onOk={() => {
          targetClientIds.forEach(id => triggerBackup(id));
          setShowPromptModal(false);
        }}
        extraFooterButtons={
          <div className="mr-auto">
            <WinButton
              onClick={() => {
                markClientWaiting(targetClientIds);
                setShowPromptModal(false);
              }}
            >
              Wait
            </WinButton>
          </div>
        }
      >
        <div className="p-3 text-[12px] text-black bg-white win-inset">
          Policy applied successfully! Do you want to start the backup for the selected clients now, or wait?
        </div>
      </WinDialog>
    </div>
  );
};
