import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import type { AppSettings } from '../types';
import { WinButton } from '../components/win95/WinButton';
import { WinTabs } from '../components/win95/WinTabs';
import { WinInput, WinCheckbox, WinSelect } from '../components/win95/WinFormControls';
import { WinPanel } from '../components/win95/WinPanel';
import { SettingsWrenchIcon, ServerIcon, ShieldCheckIcon, ComputerIcon } from '../components/win95/WinIcons';

export const SettingsPage: React.FC = () => {
  const { settings, updateSettings, addToast } = useApp();

  const [activeTab, setActiveTab] = useState<string>('server');
  const [formData, setFormData] = useState<AppSettings>(settings);

  const handleSave = () => {
    updateSettings(formData);
  };

  const tabs = [
    {
      id: 'server',
      label: 'Server Parameters',
      icon: <ServerIcon size={14} />,
      content: (
        <div className="flex flex-col gap-3">
          <WinPanel title="MANAGEMENT SERVER IDENTITY" className="p-2">
            <div className="grid grid-cols-2 gap-3">
              <WinInput
                label="Server Hostname / Node:"
                value={formData.server.serverName}
                onChange={(e) => setFormData({
                  ...formData,
                  server: { ...formData.server, serverName: e.target.value }
                })}
              />
              <WinInput
                label="Primary IPv4 Address:"
                value={formData.server.serverIp}
                onChange={(e) => setFormData({
                  ...formData,
                  server: { ...formData.server, serverIp: e.target.value }
                })}
              />
              <WinInput
                label="RPC / TLS Management Port:"
                type="number"
                value={formData.server.apiPort}
                onChange={(e) => setFormData({
                  ...formData,
                  server: { ...formData.server, apiPort: Number(e.target.value) }
                })}
              />
              <WinInput
                label="Primary Repository Storage Directory:"
                value={formData.server.repositoryPath}
                onChange={(e) => setFormData({
                  ...formData,
                  server: { ...formData.server, repositoryPath: e.target.value }
                })}
              />
            </div>
          </WinPanel>

          <div className="win-inset-gray p-2 text-[10px] text-[#404040] bg-[#dfdfdf]">
            Note: Changing the repository path requires an administrative service restart of the RetroVault Windows Service.
          </div>
        </div>
      ),
    },
    {
      id: 'security',
      label: 'Security & Encryption',
      icon: <ShieldCheckIcon size={14} />,
      content: (
        <div className="flex flex-col gap-3">
          <WinPanel title="AUTHENTICATION & CIPHER SUITES" className="p-2">
            <div className="grid grid-cols-2 gap-3">
              <WinSelect
                label="Enterprise Authentication Model:"
                value={formData.security.authType}
                onChange={(e) => setFormData({
                  ...formData,
                  security: { ...formData.security, authType: e.target.value }
                })}
              >
                <option value="Windows Kerberos / Active Directory">Windows Kerberos / Active Directory</option>
                <option value="LDAP over TLS (LDAPS)">LDAP over TLS (LDAPS)</option>
                <option value="Local Administrator SAM Database">Local Administrator SAM Database</option>
                <option value="PKI Smart Card / X.509 Certificate">PKI Smart Card / X.509 Certificate</option>
              </WinSelect>

              <WinSelect
                label="Volume Encryption Algorithm:"
                value={formData.security.encryptionAlgorithm}
                onChange={(e) => setFormData({
                  ...formData,
                  security: { ...formData.security, encryptionAlgorithm: e.target.value }
                })}
              >
                <option value="AES-256-GCM">AES-256-GCM (Hardware Accelerated)</option>
                <option value="AES-128-CBC">AES-128-CBC</option>
                <option value="ChaCha20-Poly1305">ChaCha20-Poly1305</option>
              </WinSelect>

              <WinInput
                label="Administrative Session Inactivity Timeout (Minutes):"
                type="number"
                value={formData.security.sessionTimeoutMinutes}
                onChange={(e) => setFormData({
                  ...formData,
                  security: { ...formData.security, sessionTimeoutMinutes: Number(e.target.value) }
                })}
              />
            </div>

            <div className="flex flex-col gap-2 mt-3 pt-2 border-t border-[#808080]">
              <WinCheckbox
                label="Enforce TLS 1.3 Transport Security on all Agent socket endpoints"
                checked={formData.security.tlsStatus}
                onChange={(checked) => setFormData({
                  ...formData,
                  security: { ...formData.security, tlsStatus: checked }
                })}
              />
              <WinCheckbox
                label="Enforce Role-Based Access Control (RBAC) on operator accounts"
                checked={formData.security.rbacEnabled}
                onChange={(checked) => setFormData({
                  ...formData,
                  security: { ...formData.security, rbacEnabled: checked }
                })}
              />
            </div>
          </WinPanel>
        </div>
      ),
    },
    {
      id: 'agent',
      label: 'Agent Daemon',
      icon: <ComputerIcon size={14} />,
      content: (
        <div className="flex flex-col gap-3">
          <WinPanel title="CLIENT AGENT ORCHESTRATION" className="p-2">
            <div className="grid grid-cols-2 gap-3">
              <WinInput
                label="Minimum Allowed Agent Version:"
                value={formData.agent.minimumAgentVersion}
                onChange={(e) => setFormData({
                  ...formData,
                  agent: { ...formData.agent, minimumAgentVersion: e.target.value }
                })}
                helperText="Workstations below this version will be flagged for automatic update."
              />

              <WinInput
                label="Heartbeat Polling Interval (Seconds):"
                type="number"
                value={formData.agent.heartbeatIntervalSeconds}
                onChange={(e) => setFormData({
                  ...formData,
                  agent: { ...formData.agent, heartbeatIntervalSeconds: Number(e.target.value) }
                })}
              />

              <WinInput
                label="VSS Snapshot Failure Retry Count:"
                type="number"
                value={formData.agent.retryCount}
                onChange={(e) => setFormData({
                  ...formData,
                  agent: { ...formData.agent, retryCount: Number(e.target.value) }
                })}
              />
            </div>

            <div className="mt-3 pt-2 border-t border-[#808080]">
              <WinCheckbox
                label="Enable Adaptive Bandwidth Throttling during peak business hours (08:00 - 18:00)"
                checked={formData.agent.bandwidthThrottleEnabled}
                onChange={(checked) => setFormData({
                  ...formData,
                  agent: { ...formData.agent, bandwidthThrottleEnabled: checked }
                })}
              />
            </div>
          </WinPanel>
        </div>
      ),
    },
    {
      id: 'notifications',
      label: 'Notifications & Alerts',
      icon: <SettingsWrenchIcon size={14} />,
      content: (
        <div className="flex flex-col gap-3">
          <WinPanel title="EVENT ALERT DISPATCH RULES" className="p-2">
            <div className="flex flex-col gap-2.5">
              <WinCheckbox
                label="Trigger High-Priority Alert when a Backup Job encounters a VSS or I/O failure"
                checked={formData.notifications.backupFailure}
                onChange={(checked) => setFormData({
                  ...formData,
                  notifications: { ...formData.notifications, backupFailure: checked }
                })}
              />

              <WinCheckbox
                label="Trigger Warning Alert when an enrolled Client Workstation goes offline"
                checked={formData.notifications.clientOffline}
                onChange={(checked) => setFormData({
                  ...formData,
                  notifications: { ...formData.notifications, clientOffline: checked }
                })}
              />

              <WinCheckbox
                label="Trigger Critical Alert when Workstation RPO exceeds Policy SLA threshold"
                checked={formData.notifications.rpoBreach}
                onChange={(checked) => setFormData({
                  ...formData,
                  notifications: { ...formData.notifications, rpoBreach: checked }
                })}
              />

              <WinCheckbox
                label="Trigger Warning Alert when Repository Free Space drops below 15%"
                checked={formData.notifications.storageLow}
                onChange={(checked) => setFormData({
                  ...formData,
                  notifications: { ...formData.notifications, storageLow: checked }
                })}
              />

              <div className="mt-2 pt-2 border-t border-[#808080]">
                <WinInput
                  label="Sysadmin Alert Dispatch Email / Pager Destination:"
                  value={formData.notifications.alertEmail}
                  onChange={(e) => setFormData({
                    ...formData,
                    notifications: { ...formData.notifications, alertEmail: e.target.value }
                  })}
                />
              </div>
            </div>
          </WinPanel>

          <div className="flex items-center gap-2">
            <WinButton
              onClick={() => {
                addToast('Test Alert', 'Simulated test alert sent to ' + formData.notifications.alertEmail, 'warning');
              }}
            >
              Test Notification Dispatch...
            </WinButton>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-y-auto bg-[#c0c0c0]">
      {/* Header */}
      <div className="win-outset px-3 py-2 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-2">
          <SettingsWrenchIcon size={20} />
          <div>
            <h1 className="text-[13px] font-bold text-black m-0 leading-tight">
              Enterprise System Administrator Configuration
            </h1>
            <p className="text-[10px] text-[#505050] m-0">
              Tune daemon parameters, transport security, cryptographic keys, and notification triggers
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <WinButton isDefault onClick={handleSave}>
            Save Configuration
          </WinButton>
          <WinButton onClick={() => setFormData(settings)}>
            Revert
          </WinButton>
        </div>
      </div>

      {/* Main Tabs */}
      <div className="flex-1">
        <WinTabs
          tabs={tabs}
          activeTab={activeTab}
          onChange={setActiveTab}
        />
      </div>
    </div>
  );
};
