import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Client } from '../../types';
import { WinDialog } from '../win95/WinDialog';
import { WinButton } from '../win95/WinButton';
import { WinTabs } from '../win95/WinTabs';
import { WinBadge } from '../win95/WinBadge';
import { WinPanel } from '../win95/WinPanel';
import { ComputerIcon, BackupTapeIcon, RestoreArrowIcon, ActivityLogIcon, ShieldCheckIcon } from '../win95/WinIcons';
import { useApp } from '../../context/AppContext';

interface ClientDetailDialogProps {
  client: Client | null;
  isOpen: boolean;
  onClose: () => void;
}

export const ClientDetailDialog: React.FC<ClientDetailDialogProps> = ({
  client,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<string>('system');
  const [newCustomPath, setNewCustomPath] = useState<string>('');
  const [newExcludedPath, setNewExcludedPath] = useState<string>('');
  const navigate = useNavigate();
  const { triggerBackup, updateClientPaths } = useApp();

  if (!client) return null;

  const handleAddCustomPath = () => {
    if (!newCustomPath.trim()) return;
    const updated = [...client.customPaths, newCustomPath.trim()];
    updateClientPaths(client.id, updated, client.excludedPaths);
    setNewCustomPath('');
  };

  const handleRemoveCustomPath = (pathToRemove: string) => {
    const updated = client.customPaths.filter(p => p !== pathToRemove);
    updateClientPaths(client.id, updated, client.excludedPaths);
  };

  const handleAddExcludedPath = () => {
    if (!newExcludedPath.trim()) return;
    const updated = [...client.excludedPaths, newExcludedPath.trim()];
    updateClientPaths(client.id, client.customPaths, updated);
    setNewExcludedPath('');
  };

  const handleRemoveExcludedPath = (pathToRemove: string) => {
    const updated = client.excludedPaths.filter(p => p !== pathToRemove);
    updateClientPaths(client.id, client.customPaths, updated);
  };

  const formatRpo = (sec: number) => {
    if (sec < 60) return `${sec} seconds`;
    if (sec < 3600) return `${Math.round(sec / 60)} minutes`;
    return `${(sec / 3600).toFixed(1)} hours (BREACH)`;
  };

  const tabs = [
    {
      id: 'system',
      label: 'System Information',
      icon: <ComputerIcon size={14} />,
      content: (
        <div className="flex flex-col gap-3">
          <WinPanel variant="groove" className="p-2.5">
            <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-[11px]">
              <div>
                <span className="text-[#606060] font-medium block">Hostname:</span>
                <span className="font-bold text-black font-mono">{client.hostname}</span>
              </div>
              <div>
                <span className="text-[#606060] font-medium block">Client ID:</span>
                <span className="font-bold text-black font-mono">{client.id}</span>
              </div>
              <div>
                <span className="text-[#606060] font-medium block">Assigned User:</span>
                <span className="font-bold text-black">{client.user}</span>
              </div>
              <div>
                <span className="text-[#606060] font-medium block">Client Status:</span>
                <WinBadge status={client.status} type="client" />
              </div>
              <div>
                <span className="text-[#606060] font-medium block">Operating System:</span>
                <span className="text-black font-semibold">{client.os}</span>
              </div>
              <div>
                <span className="text-[#606060] font-medium block">IP Address:</span>
                <span className="font-mono text-black">{client.ipAddress}</span>
              </div>
              <div>
                <span className="text-[#606060] font-medium block">CPU Architecture:</span>
                <span className="text-black truncate block">{client.cpu}</span>
              </div>
              <div>
                <span className="text-[#606060] font-medium block">Physical Memory (RAM):</span>
                <span className="text-black font-mono">{client.ram}</span>
              </div>
              <div>
                <span className="text-[#606060] font-medium block">Agent Daemon Version:</span>
                <span className="font-mono text-[#000080] font-bold">v{client.agentVersion} (USN-Enabled)</span>
              </div>
              <div>
                <span className="text-[#606060] font-medium block">Last Contact Seen:</span>
                <span className="text-black">{client.lastSeen}</span>
              </div>
            </div>
          </WinPanel>

          <WinPanel title="BACKUP TELEMETRY" className="p-2">
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <span className="text-[#606060]">Backup Policy:</span>
                <div className="font-bold text-[#000080] flex items-center gap-1">
                  <ShieldCheckIcon size={12} />
                  <span>{client.policyName}</span>
                </div>
              </div>
              <div>
                <span className="text-[#606060]">Last Successful Snapshot:</span>
                <div className="font-mono font-bold text-black">{client.lastBackup}</div>
              </div>
              <div>
                <span className="text-[#606060]">Current RPO Latency:</span>
                <div className={`font-mono font-bold ${client.rpoSeconds > 120 ? 'text-[#cc0000]' : 'text-[#008000]'}`}>
                  {formatRpo(client.rpoSeconds)}
                </div>
              </div>
              <div>
                <span className="text-[#606060]">Repository Storage Consumed:</span>
                <div className="font-mono font-bold text-black">{client.storageConsumedGb} GB</div>
              </div>
            </div>
          </WinPanel>
        </div>
      ),
    },
    {
      id: 'paths',
      label: 'Protected Paths & Overrides',
      icon: <ShieldCheckIcon size={14} />,
      content: (
        <div className="flex flex-col gap-2.5 max-h-80 overflow-y-auto pr-1">
          {/* Section 1: Universal Policy Paths */}
          <div className="win-fieldset">
            <legend className="text-[10px] font-bold uppercase text-[#000080] bg-[#c0c0c0] px-1">
              Universal Policy Paths (Inherited from {client.policyName})
            </legend>
            <div className="flex flex-col gap-1 mt-1">
              {client.universalPaths.map((p, idx) => (
                <div key={idx} className="win-inset bg-white px-2 py-0.5 font-mono text-[10px] text-black flex items-center justify-between">
                  <div className="flex items-center gap-1.5 truncate">
                    <span className="text-[#000080] font-bold">[UNIVERSAL]</span>
                    <span className="truncate">{p}</span>
                  </div>
                  <span className="text-[9px] text-[#008000] font-sans font-semibold">Active</span>
                </div>
              ))}
            </div>
          </div>

          {/* Section 2: Client-Specific Overrides */}
          <div className="win-fieldset">
            <legend className="text-[10px] font-bold uppercase text-[#800000] bg-[#c0c0c0] px-1">
              Client-Specific Overrides (Custom Workstation Folders)
            </legend>
            <div className="flex flex-col gap-1 mt-1">
              {client.customPaths.length === 0 ? (
                <div className="text-[10px] text-[#606060] italic py-1">
                  No client-specific override folders assigned.
                </div>
              ) : (
                client.customPaths.map((p, idx) => (
                  <div key={idx} className="win-inset bg-white px-2 py-0.5 font-mono text-[10px] text-black flex items-center justify-between">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="text-[#800000] font-bold">[OVERRIDE]</span>
                      <span className="truncate">{p}</span>
                    </div>
                    <button
                      type="button"
                      className="text-[#aa0000] hover:font-bold text-[10px] px-1 cursor-pointer"
                      title="Remove custom path"
                      onClick={() => handleRemoveCustomPath(p)}
                    >
                      ✕ Remove
                    </button>
                  </div>
                ))
              )}

              {/* Add Custom Path */}
              <div className="flex gap-1 mt-1">
                <input
                  type="text"
                  placeholder="e.g. D:\Projects\EnterpriseData"
                  value={newCustomPath}
                  onChange={(e) => setNewCustomPath(e.target.value)}
                  className="win-inset bg-white px-1.5 py-0.5 text-[10px] font-mono flex-1 text-black"
                />
                <WinButton size="sm" onClick={handleAddCustomPath}>
                  + Add Override
                </WinButton>
              </div>
            </div>
          </div>

          {/* Section 3: Excluded Paths */}
          <div className="win-fieldset">
            <legend className="text-[10px] font-bold uppercase text-[#404040] bg-[#c0c0c0] px-1">
              Excluded Paths & Wildcards
            </legend>
            <div className="flex flex-col gap-1 mt-1">
              <div className="flex flex-wrap gap-1">
                {client.excludedPaths.map((p, idx) => (
                  <span key={idx} className="win-inset-gray px-1.5 py-0.5 font-mono text-[9px] text-[#303030] flex items-center gap-1 bg-[#dfdfdf]">
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
              <div className="flex gap-1 mt-1">
                <input
                  type="text"
                  placeholder="e.g. *.iso, node_modules"
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
        </div>
      ),
    }
  ];

  return (
    <WinDialog
      isOpen={isOpen}
      onClose={onClose}
      title={`Workstation Client Properties — ${client.hostname} (${client.id})`}
      icon={<ComputerIcon size={16} />}
      width={580}
      okText="Close"
      onOk={onClose}
      extraFooterButtons={
        <div className="flex items-center gap-1.5 mr-auto">
          <WinButton
            isDefault
            onClick={() => {
              triggerBackup(client.id);
            }}
          >
            <BackupTapeIcon size={13} />
            <span>Backup Now</span>
          </WinButton>
          <WinButton
            onClick={() => {
              onClose();
              navigate('/restore');
            }}
          >
            <RestoreArrowIcon size={13} />
            <span>Restore</span>
          </WinButton>
          <WinButton
            onClick={() => {
              onClose();
              navigate('/activity');
            }}
          >
            <ActivityLogIcon size={13} />
            <span>View Logs</span>
          </WinButton>
          <WinButton
            onClick={() => {
              onClose();
              navigate('/policies');
            }}
          >
            <ShieldCheckIcon size={13} />
            <span>Edit Policy</span>
          </WinButton>
        </div>
      }
    >
      <WinTabs
        tabs={tabs}
        activeTab={activeTab}
        onChange={setActiveTab}
      />
    </WinDialog>
  );
};
