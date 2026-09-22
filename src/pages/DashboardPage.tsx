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
  HardDriveIcon, 
  ShieldCheckIcon, 
  RestoreArrowIcon 
} from '../components/win95/WinIcons';
import type { BackupJob } from '../types';

export const DashboardPage: React.FC = () => {
  const { clients, jobs, storage, triggerBackup, addToast } = useApp();
  const navigate = useNavigate();

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
          <WinButton onClick={() => navigate('/storage')}>
            <HardDriveIcon size={14} />
            <span>Storage Mgmt</span>
          </WinButton>
        </div>
      </div>

      {/* 4 Classic Win95 Stat Panels */}
      <div className="grid grid-cols-4 gap-2 shrink-0">
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
              <span className="font-mono font-semibold text-[#000080]">USN Journal</span>
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
