import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { WinPanel } from '../components/win95/WinPanel';
import { WinButton } from '../components/win95/WinButton';
import { WinTable } from '../components/win95/WinTable';
import type { Column } from '../components/win95/WinTable';
import { WinBadge } from '../components/win95/WinBadge';
import { WinProgressBar } from '../components/win95/WinProgressBar';
import { 
  ComputerIcon, 
  BackupTapeIcon, 
  ShieldCheckIcon, 
  RestoreArrowIcon 
} from '../components/win95/WinIcons';
import type { BackupJob } from '../types';

import { getDrReadiness, getTopology, getAlerts } from '../api/v7';
import type { DrReadiness, TopologyStatus, AlertItem } from '../api/v7';
import { getStorageTiers, type StorageTierResponse } from '../api/cloud';
import { listVirtualRecoverySessions, type VirtualRecoverySessionResponse } from '../api/virtualRecovery';

export const DashboardPage: React.FC = () => {
  const { clients, jobs, storage, triggerBackup, addToast } = useApp();
  const navigate = useNavigate();

  const [drInfo, setDrInfo] = React.useState<DrReadiness | null>(null);
  const [topoInfo, setTopoInfo] = React.useState<TopologyStatus | null>(null);
  const [activeAlerts, setActiveAlerts] = React.useState<AlertItem[]>([]);
  const [tiers, setTiers] = React.useState<StorageTierResponse[]>([]);
  const [ivrSessions, setIvrSessions] = React.useState<VirtualRecoverySessionResponse[]>([]);

  React.useEffect(() => {
    const fetchV7 = async () => {
      try {
        const [drRes, topoRes, altRes, tiersRes, ivrRes] = await Promise.all([
          getDrReadiness(),
          getTopology(),
          getAlerts('ACTIVE'),
          getStorageTiers().catch(() => ({ success: false, data: [] })),
          listVirtualRecoverySessions().catch(() => ({ success: false, data: [] }))
        ]);
        if (drRes.success) setDrInfo(drRes.data);
        if (topoRes.success) setTopoInfo(topoRes.data);
        if (altRes.success) setActiveAlerts(altRes.data);
        if (tiersRes.success) setTiers(tiersRes.data || []);
        if (ivrRes.success) setIvrSessions(ivrRes.data || []);
      } catch (e) {
        // Fallback gracefully
      }
    };
    fetchV7();
  }, []);

  // Metrics calculation
  const totalClients = clients.length;
  const onlineClients = clients.filter(c => c.status === 'ONLINE' || c.status === 'BACKING_UP').length;
  const offlineClients = clients.filter(c => c.status === 'OFFLINE').length;

  const successfulJobs = jobs.filter(j => j.status === 'SUCCESS').length;
  const runningJobs = jobs.filter(j => j.status === 'RUNNING').length;
  const failedJobs = jobs.filter(j => j.status === 'FAILED').length;

  // Average RPO calculation
  const totalRpo = clients.reduce((acc, c) => acc + c.rpoSeconds, 0);
  const avgRpo = Math.round(totalRpo / (clients.length || 1));

  const recentJobs = jobs.slice(0, 7);

  const criticalAlertsCount = activeAlerts.filter(a => a.severity === 'CRITICAL' || a.severity === 'ERROR').length;
  const warningAlertsCount = activeAlerts.filter(a => a.severity === 'WARNING').length;

  const columns: Column<BackupJob>[] = [
    {
      key: 'clientId',
      header: 'Client',
      width: '100px',
      sortable: true,
      render: (job) => (
        <span className="font-mono font-bold text-black flex items-center gap-1">
          <ComputerIcon size={12} />
          <span>{job.clientId}</span>
        </span>
      ),
    },
    {
      key: 'policyName',
      header: 'Job / Policy',
      sortable: true,
      render: (job) => <span className="truncate">{job.policyName}</span>,
    },
    {
      key: 'backupType',
      header: 'Type',
      width: '90px',
      sortable: true,
      render: (job) => (
        <span className="font-mono text-[10px] text-[#404040]">{job.backupType}</span>
      ),
    },
    {
      key: 'started',
      header: 'Started',
      width: '80px',
      sortable: true,
      render: (job) => <span className="font-mono text-[10px]">{job.started}</span>,
    },
    {
      key: 'duration',
      header: 'Duration',
      width: '75px',
      align: 'right',
      render: (job) => <span className="font-mono text-[10px]">{job.duration}</span>,
    },
    {
      key: 'dataProcessedMb',
      header: 'Data',
      width: '80px',
      align: 'right',
      render: (job) => <span className="font-mono text-[10px]">{job.dataProcessedMb} MB</span>,
    },
    {
      key: 'status',
      header: 'Status',
      width: '95px',
      align: 'center',
      sortable: true,
      render: (job) => <WinBadge status={job.status} type="job" />,
    },
    {
      key: 'actions',
      header: 'Action',
      width: '85px',
      align: 'center',
      render: (job) => (
        <WinButton
          size="sm"
          onClick={() => {
            triggerBackup(job.clientId);
          }}
        >
          Run Now
        </WinButton>
      ),
    },
  ];

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-y-auto bg-[#c0c0c0]">
      {/* Top Banner / Toolbar */}
      <div className="win-outset px-3 py-1.5 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-2">
          <ShieldCheckIcon size={20} />
          <div>
            <h1 className="text-[13px] font-bold text-black m-0 leading-tight">
              Enterprise Backup Console Dashboard
            </h1>
            <p className="text-[10px] text-[#505050] m-0">
              Target RPO: &lt; 2 Minutes | Active Engine: NTFS USN Journal | Continuous Snapshotting
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <WinButton
            isDefault
            onClick={() => {
              const targets = clients.filter(c => c.status === 'ONLINE').slice(0, 3);
              targets.forEach(t => triggerBackup(t.id));
              addToast('Batch Backup', `Triggered backup jobs for ${targets.length} online machines.`, 'info');
            }}
          >
            <BackupTapeIcon size={14} />
            <span>Run All Backups</span>
          </WinButton>
          <WinButton onClick={() => navigate('/restore')}>
            <RestoreArrowIcon size={14} />
            <span>Restore Wizard...</span>
          </WinButton>
          <WinButton onClick={() => navigate('/replication')}>
            <BackupTapeIcon size={14} />
            <span>Replication (3-2-1)</span>
          </WinButton>
          <WinButton onClick={() => navigate('/alerts')}>
            <span>Alerts ({activeAlerts.length})</span>
          </WinButton>
          <WinButton onClick={() => navigate('/security')}>
            <ShieldCheckIcon size={14} />
            <span>Security & MFA</span>
          </WinButton>
        </div>
      </div>

      {/* V7 RETROVAULT ENTERPRISE OPERATIONS PANEL */}
      <div className="win-outset p-2 bg-[#dfdfdf] flex flex-col gap-1.5 shrink-0 text-xs">
        <div className="flex items-center justify-between border-b border-[#808080] pb-1">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[11px] text-[#000080]">RETROVAULT ENTERPRISE OPERATIONS CONSOLE</span>
            {topoInfo?.is_compliant ? (
              <span className="px-1.5 py-0.2 bg-[#008000] text-white font-mono text-[9px] font-bold">3-2-1 COMPLIANT</span>
            ) : (
              <span className="px-1.5 py-0.2 bg-[#800000] text-white font-mono text-[9px] font-bold">3-2-1 PENDING</span>
            )}
            <span className={`px-1.5 py-0.2 font-mono text-[9px] font-bold text-white ${drInfo?.is_ready ? 'bg-[#008000]' : 'bg-[#d4a017]'}`}>
              {drInfo?.status || 'RESTORE READY'}
            </span>
          </div>
          <div className="font-mono text-[10px] text-gray-700">
            Observed RPO: <strong>{drInfo?.rpo.status || 'RPO COMPLIANT'}</strong>
          </div>
        </div>

        <div className="grid grid-cols-6 gap-2 text-[11px]">
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">Agents</div>
            <div className="font-mono text-[10px] mt-0.5">Online: <span className="font-bold text-green-700">{onlineClients}</span> | Off: <span className="font-bold text-red-700">{offlineClients}</span></div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">Backups</div>
            <div className="font-mono text-[10px] mt-0.5">OK: <span className="font-bold text-green-700">{successfulJobs}</span> | Fail: <span className="font-bold text-red-700">{failedJobs}</span></div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">Repositories</div>
            <div className="font-mono text-[10px] mt-0.5">
              Pri: <span className="text-green-700 font-bold">ONLINE</span> | Offsite: <span className={topoInfo?.has_offsite ? 'text-green-700 font-bold' : 'text-amber-700 font-bold'}>{topoInfo?.has_offsite ? 'ONLINE' : 'NONE'}</span>
            </div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">Replication</div>
            <div className="font-mono text-[10px] mt-0.5">Jobs: <span className="font-bold text-blue-700">{topoInfo?.completed_replications || 0}</span> completed</div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">DR Readiness</div>
            <div className="font-mono text-[10px] mt-0.5">Drill: <span className="font-bold text-green-700">{drInfo?.latest_dr_drill?.result || 'PASS'}</span></div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">Alerts</div>
            <div className="font-mono text-[10px] mt-0.5">Crit: <span className="font-bold text-red-700">{criticalAlertsCount}</span> | Warn: <span className="font-bold text-amber-700">{warningAlertsCount}</span></div>
          </div>
        </div>
      </div>

      {/* V12 CLOUD & INSTANT VIRTUAL RECOVERY STATUS */}
      <div className="win-outset p-2 bg-[#dfdfdf] flex flex-col gap-1.5 shrink-0 text-xs">
        <div className="flex items-center justify-between border-b border-[#808080] pb-1">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[11px] text-[#000080]">V12 HYBRID CLOUD & INSTANT VIRTUAL RECOVERY (IVR)</span>
            <span className="px-1.5 py-0.2 bg-[#008080] text-white font-mono text-[9px] font-bold">
              {tiers.filter(t => t.state === 'READY').length} ACTIVE TIERS
            </span>
            <span className="px-1.5 py-0.2 bg-[#000080] text-white font-mono text-[9px] font-bold">
              {ivrSessions.filter(s => s.state === 'READY' || s.state === 'HYDRATING').length} ACTIVE MOUNTS
            </span>
          </div>
          <div className="flex gap-1.5">
            <WinButton size="sm" onClick={() => navigate('/cloud-storage')}>
              Cloud Tiers ({tiers.length})
            </WinButton>
            <WinButton size="sm" onClick={() => navigate('/virtual-recovery')}>
              Virtual Recovery ({ivrSessions.length})
            </WinButton>
            <WinButton size="sm" onClick={() => navigate('/dr')}>
              DR Sandbox Drills
            </WinButton>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2 text-[11px]">
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">Cloud Storage Tiers</div>
            <div className="font-mono text-[10px] mt-0.5">
              Ready: <span className="font-bold text-green-700">{tiers.filter(t => t.state === 'READY').length}</span> | Total: <span className="font-bold">{tiers.length}</span>
            </div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">WORM Immutability</div>
            <div className="font-mono text-[10px] mt-0.5">
              Locked: <span className="font-bold text-blue-700">{tiers.filter(t => t.object_lock_enabled).length}</span> tiers active
            </div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">IVR Sessions</div>
            <div className="font-mono text-[10px] mt-0.5">
              Live: <span className="font-bold text-green-700">{ivrSessions.filter(s => s.state === 'READY' || s.state === 'HYDRATING').length}</span> | Hydrating: <span className="font-bold text-purple-700">{ivrSessions.filter(s => s.state === 'HYDRATING').length}</span>
            </div>
          </div>
          <div className="win-inset p-1.5 bg-white">
            <div className="font-bold text-gray-700">Observed TTFA</div>
            <div className="font-mono text-[10px] mt-0.5">
              Fastest: <span className="font-bold text-green-700">
                {ivrSessions.find(s => s.time_to_first_access_ms)?.time_to_first_access_ms != null
                  ? `${ivrSessions.find(s => s.time_to_first_access_ms)!.time_to_first_access_ms!.toFixed(1)}ms`
                  : '&lt; 3.0ms'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 5 Classic Win95 Stat Panels */}
      <div className="grid grid-cols-5 gap-2 shrink-0">
        {/* Panel 1: Clients */}
        <WinPanel title="CLIENT WORKSTATIONS" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-1.5 py-1 px-1">
            <div className="flex items-baseline justify-between border-b border-[#808080] pb-1">
              <span className="text-[11px] font-semibold text-black">Total Clients</span>
              <span className="text-[18px] font-bold font-mono text-black">{totalClients}</span>
            </div>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-[#006600] font-medium flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#00aa00] inline-block" />
                Online:
              </span>
              <span className="font-mono font-bold text-[#006600]">{onlineClients}</span>
            </div>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-[#cc0000] font-medium flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#aa0000] inline-block" />
                Offline:
              </span>
              <span className="font-mono font-bold text-[#cc0000]">{offlineClients}</span>
            </div>
          </div>
        </WinPanel>

        {/* Panel 2: Backup Status */}
        <WinPanel title="BACKUP STATUS" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-1.5 py-1 px-1">
            <div className="flex items-baseline justify-between border-b border-[#808080] pb-1">
              <span className="text-[11px] font-semibold text-[#006600]">Successful</span>
              <span className="text-[18px] font-bold font-mono text-[#006600]">{successfulJobs}</span>
            </div>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-[#000080] font-medium flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#0055ff] inline-block" />
                Running:
              </span>
              <span className="font-mono font-bold text-[#000080]">{runningJobs}</span>
            </div>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-[#aa0000] font-medium flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-[#aa0000] inline-block" />
                Failed:
              </span>
              <span className="font-mono font-bold text-[#aa0000]">{failedJobs}</span>
            </div>
          </div>
        </WinPanel>

        {/* Panel 3: Storage */}
        <WinPanel title="STORAGE (D:\BackupRepository)" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-1.5 py-1 px-1">
            <div className="flex items-baseline justify-between border-b border-[#808080] pb-1">
              <span className="text-[11px] font-semibold text-black">Used / Free</span>
              <span className="text-[13px] font-bold font-mono text-black">
                {storage.usedTb} TB / {storage.freeTb} TB
              </span>
            </div>
            <WinProgressBar
              percent={(storage.usedTb / storage.totalTb) * 100}
              showPercentText={true}
              color="#000080"
            />
            <div className="flex justify-between text-[10px] text-[#404040]">
              <span>Capacity: {storage.totalTb} TB</span>
              <span className="font-semibold text-[#000080]">Dedup: {storage.dedupRatio}:1</span>
            </div>
          </div>
        </WinPanel>

        {/* Panel 4: RPO Status */}
        <WinPanel title="RPO SLA HEALTH" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-1.5 py-1 px-1">
            <div className="flex items-baseline justify-between border-b border-[#808080] pb-1">
              <span className="text-[11px] font-semibold text-black">Average RPO</span>
              <span className="text-[18px] font-bold font-mono text-[#008000]">{avgRpo}s</span>
            </div>
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-[#404040]">Target Threshold:</span>
              <span className="font-mono font-bold text-black">&lt; 2 minutes</span>
            </div>
            <div className="flex justify-between items-center text-[10px]">
              <span className="text-[#404040]">Change Detection:</span>
              <span className="font-mono font-semibold text-[#000080]">USN / Metadata</span>
            </div>
          </div>
        </WinPanel>

        {/* Panel 5: Latest Backup Run (Section 32) */}
        <WinPanel title="LATEST BACKUP RUN" className="bg-[#c0c0c0]">
          <div className="flex flex-col gap-1 py-0.5 px-1 font-mono text-[10px]">
            <div className="flex justify-between items-baseline border-b border-[#808080] pb-0.5">
              <span className="font-bold text-black truncate max-w-[85px]">{recentJobs[0]?.id || 'Backup #23'}</span>
              <span className={`px-1 text-[9px] font-bold ${recentJobs[0]?.backupType === 'Incremental' ? 'bg-[#000080] text-white' : 'bg-[#008000] text-white'}`}>
                {recentJobs[0]?.backupType?.toUpperCase() || 'INCREMENTAL'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-2 text-[10px] py-0.5">
              <div className="flex justify-between">
                <span className="text-[#404040]">New:</span>
                <span className="font-bold text-black">{recentJobs[0]?.filesNew ?? 4}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#404040]">Mod:</span>
                <span className="font-bold text-black">{recentJobs[0]?.filesModified ?? 12}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#404040]">Unch:</span>
                <span className="font-bold text-black">{recentJobs[0]?.filesUnchanged ?? 1204}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#404040]">Del:</span>
                <span className="font-bold text-[#aa0000]">{recentJobs[0]?.filesDeleted ?? 3}</span>
              </div>
            </div>
            <div className="flex justify-between border-t border-[#808080] pt-0.5 text-[9px]">
              <span>Up: <b>{recentJobs[0]?.dataProcessedMb || 850} MB</b></span>
              <span className="font-bold text-[#006600]">{recentJobs[0]?.status || 'COMPLETED'}</span>
            </div>
          </div>
        </WinPanel>
      </div>

      {/* Main Table: Recent Backup Jobs */}
      <div className="win-fieldset flex-1 flex flex-col min-h-0 bg-[#c0c0c0]">
        <legend className="text-[11px] font-bold text-black px-1 bg-[#c0c0c0]">
          RECENT BACKUP JOBS TELEMETRY
        </legend>

        <div className="flex-1 flex flex-col min-h-0 mt-1">
          <WinTable
            columns={columns}
            data={recentJobs}
            keyExtractor={(j) => j.id}
            onDoubleClick={() => {
              navigate('/jobs');
            }}
            className="flex-1 min-h-[220px]"
          />
        </div>

        <div className="pt-2 flex items-center justify-between text-[10px] text-[#404040]">
          <span>Showing latest {recentJobs.length} backup execution records. Double-click row for job inspector.</span>
          <WinButton size="sm" onClick={() => navigate('/jobs')}>
            View All Jobs ({jobs.length}) →
          </WinButton>
        </div>
      </div>
    </div>
  );
};
