import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import type { BackupJob } from '../types';
import { WinTable } from '../components/win95/WinTable';
import type { Column } from '../components/win95/WinTable';
import { WinButton } from '../components/win95/WinButton';
import { WinBadge } from '../components/win95/WinBadge';
import { WinProgressBar } from '../components/win95/WinProgressBar';
import { WinDialog } from '../components/win95/WinDialog';
import { BackupTapeIcon, ComputerIcon } from '../components/win95/WinIcons';

export const JobsPage: React.FC = () => {
  const { jobs, pauseJob, cancelJob, triggerBackup, addToast } = useApp();
  const [selectedJobId, setSelectedJobId] = useState<string | null>(jobs[0]?.id || null);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'PAUSED'>('ALL');
  const [inspectedJob, setInspectedJob] = useState<BackupJob | null>(null);

  const filteredJobs = jobs.filter(j => {
    if (statusFilter === 'ALL') return true;
    return j.status === statusFilter;
  });

  const selectedJob = jobs.find(j => j.id === selectedJobId) || null;

  const columns: Column<BackupJob>[] = [
    {
      key: 'id',
      header: 'Job ID',
      width: '85px',
      sortable: true,
      render: (job) => (
        <span className="font-mono font-bold text-black flex items-center gap-1">
          <BackupTapeIcon size={13} />
          <span>{job.id}</span>
        </span>
      ),
    },
    {
      key: 'clientHostname',
      header: 'Client Hostname',
      width: '130px',
      sortable: true,
      render: (job) => (
        <span className="font-mono text-black font-semibold flex items-center gap-1">
          <ComputerIcon size={12} />
          <span>{job.clientHostname}</span>
        </span>
      ),
    },
    {
      key: 'policyName',
      header: 'Policy',
      width: '140px',
      sortable: true,
      render: (job) => <span className="truncate">{job.policyName}</span>,
    },
    {
      key: 'backupType',
      header: 'Type',
      width: '85px',
      sortable: true,
      render: (job) => <span className="font-mono text-[10px]">{job.backupType}</span>,
    },
    {
      key: 'source',
      header: 'Source Paths',
      sortable: true,
      render: (job) => <span className="font-mono text-[10px] text-[#404040] truncate">{job.source}</span>,
    },
    {
      key: 'started',
      header: 'Started',
      width: '75px',
      sortable: true,
      render: (job) => <span className="font-mono text-[10px]">{job.started}</span>,
    },
    {
      key: 'completed',
      header: 'Completed',
      width: '80px',
      sortable: true,
      render: (job) => (
        <span className="font-mono text-[10px]">
          {job.completed || (job.status === 'RUNNING' ? 'In Progress...' : '--')}
        </span>
      ),
    },
    {
      key: 'dataProcessedMb',
      header: 'Processed',
      width: '85px',
      align: 'right',
      sortable: true,
      render: (job) => (
        <span className="font-mono text-[10px]">
          {job.dataProcessedMb.toLocaleString()} MB
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status / Progress',
      width: '140px',
      render: (job) => {
        if (job.status === 'RUNNING') {
          return (
            <div className="flex flex-col gap-0.5">
              <WinProgressBar
                percent={job.progressPercent || 20}
                showPercentText={false}
                className="w-full"
              />
              <div className="flex justify-between text-[9px] font-mono">
                <span className="text-[#000080] font-bold">RUNNING</span>
                <span>{job.progressPercent || 0}%</span>
              </div>
            </div>
          );
        }
        return <WinBadge status={job.status} type="job" />;
      },
    },
    {
      key: 'actions',
      header: 'Job Control',
      width: '160px',
      align: 'center',
      render: (job) => (
        <div className="flex items-center justify-center gap-1">
          {job.status === 'RUNNING' && (
            <>
              <WinButton
                size="sm"
                onClick={() => pauseJob(job.id)}
                title="Pause job"
              >
                Pause
              </WinButton>
              <WinButton
                size="sm"
                onClick={() => cancelJob(job.id)}
                title="Cancel job"
              >
                Abort
              </WinButton>
            </>
          )}

          {job.status === 'PAUSED' && (
            <WinButton
              size="sm"
              onClick={() => pauseJob(job.id)}
              title="Resume job"
            >
              Resume
            </WinButton>
          )}

          {(job.status === 'SUCCESS' || job.status === 'FAILED') && (
            <WinButton
              size="sm"
              onClick={() => triggerBackup(job.clientId)}
              title="Run backup again"
            >
              Run Now
            </WinButton>
          )}

          <WinButton
            size="sm"
            onClick={() => setInspectedJob(job)}
            title="Inspect job telemetry details"
          >
            Details
          </WinButton>
        </div>
      ),
    },
  ];

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-hidden bg-[#c0c0c0]">
      {/* Action Header */}
      <div className="win-outset p-2 flex items-center justify-between gap-3 bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-bold text-black mr-1">Filter Jobs:</span>
          <WinButton
            size="sm"
            active={statusFilter === 'ALL'}
            onClick={() => setStatusFilter('ALL')}
          >
            All ({jobs.length})
          </WinButton>
          <WinButton
            size="sm"
            active={statusFilter === 'RUNNING'}
            onClick={() => setStatusFilter('RUNNING')}
          >
            Running ({jobs.filter(j => j.status === 'RUNNING').length})
          </WinButton>
          <WinButton
            size="sm"
            active={statusFilter === 'SUCCESS'}
            onClick={() => setStatusFilter('SUCCESS')}
          >
            Success ({jobs.filter(j => j.status === 'SUCCESS').length})
          </WinButton>
          <WinButton
            size="sm"
            active={statusFilter === 'FAILED'}
            onClick={() => setStatusFilter('FAILED')}
          >
            Failed ({jobs.filter(j => j.status === 'FAILED').length})
          </WinButton>
          <WinButton
            size="sm"
            active={statusFilter === 'PAUSED'}
            onClick={() => setStatusFilter('PAUSED')}
          >
            Paused ({jobs.filter(j => j.status === 'PAUSED').length})
          </WinButton>
        </div>

        <div className="flex items-center gap-1">
          <WinButton
            isDefault
            onClick={() => {
              if (selectedJob) {
                triggerBackup(selectedJob.clientId);
              } else {
                addToast('Queue Info', 'Select a client row to run backup operation.', 'info');
              }
            }}
          >
            Run Now
          </WinButton>
          <WinButton
            disabled={!selectedJob}
            onClick={() => selectedJob && setInspectedJob(selectedJob)}
          >
            View Details
          </WinButton>
        </div>
      </div>

      {/* Main Jobs Table */}
      <div className="flex-1 flex flex-col min-h-0 bg-[#c0c0c0]">
        <WinTable
          columns={columns}
          data={filteredJobs}
          keyExtractor={(j) => j.id}
          selectedId={selectedJobId}
          onSelect={(j) => setSelectedJobId(j.id)}
          onDoubleClick={(j) => setInspectedJob(j)}
          className="flex-1"
        />
      </div>

      {/* Footer Info */}
      <div className="win-inset-gray px-2 py-1 text-[10px] text-[#404040] flex items-center justify-between shrink-0 bg-[#dfdfdf]">
        <span>
          Showing {filteredJobs.length} of {jobs.length} jobs in queue. Active change detection: NTFS USN Journal.
        </span>
        {selectedJob && (
          <span className="font-mono">
            Job <b>{selectedJob.id}</b> | Client: <b>{selectedJob.clientHostname}</b> ({selectedJob.clientId})
          </span>
        )}
      </div>

      {/* Job Details Modal */}
      {inspectedJob && (
        <WinDialog
          isOpen={Boolean(inspectedJob)}
          onClose={() => setInspectedJob(null)}
          title={`Job Inspector — ${inspectedJob.id} (${inspectedJob.clientHostname})`}
          icon={<BackupTapeIcon size={16} />}
          width={520}
          okText="Close"
          onOk={() => setInspectedJob(null)}
          extraFooterButtons={
            inspectedJob.status === 'FAILED' ? (
              <WinButton
                isDefault
                onClick={() => {
                  triggerBackup(inspectedJob.clientId);
                  setInspectedJob(null);
                }}
              >
                Retry Job Now
              </WinButton>
            ) : undefined
          }
        >
          <div className="flex flex-col gap-2.5">
            <div className="win-inset-gray p-2.5 bg-[#dfdfdf] grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <span className="text-[#606060] block font-medium">Job Identifier:</span>
                <span className="font-mono font-bold text-black">{inspectedJob.id}</span>
              </div>
              <div>
                <span className="text-[#606060] block font-medium">Current Status:</span>
                <WinBadge status={inspectedJob.status} type="job" />
              </div>
              <div>
                <span className="text-[#606060] block font-medium">Target Hostname:</span>
                <span className="font-bold text-black">{inspectedJob.clientHostname} ({inspectedJob.clientId})</span>
              </div>
              <div>
                <span className="text-[#606060] block font-medium">Assigned Policy:</span>
                <span className="text-[#000080] font-semibold">{inspectedJob.policyName}</span>
              </div>
              <div>
                <span className="text-[#606060] block font-medium">Backup Mode:</span>
                <span className="font-mono text-black">{inspectedJob.backupType}</span>
              </div>
              <div>
                <span className="text-[#606060] block font-medium">Change Tracking:</span>
                <span className="font-mono text-black font-semibold">{inspectedJob.changeDetection || 'USN Journal (NTFS)'}</span>
              </div>
              <div>
                <span className="text-[#606060] block font-medium">Started At:</span>
                <span className="font-mono text-black">{inspectedJob.started}</span>
              </div>
              <div>
                <span className="text-[#606060] block font-medium">Completed At:</span>
                <span className="font-mono text-black">{inspectedJob.completed || 'Active'}</span>
              </div>
              <div>
                <span className="text-[#606060] block font-medium">Elapsed Duration:</span>
                <span className="font-mono text-black">{inspectedJob.duration}</span>
              </div>
              <div>
                <span className="text-[#606060] block font-medium">Transfer Speed:</span>
                <span className="font-mono text-black font-semibold">{inspectedJob.transferSpeedMbps || 88.4} Mbps</span>
              </div>
            </div>

            {/* Error box if failed */}
            {inspectedJob.errorMessage && (
              <div className="win-inset bg-[#fff0f0] border border-[#cc0000] p-2 text-[10px] text-[#990000] font-mono">
                <div className="font-bold flex items-center gap-1 text-[11px] mb-1">
                  <span>⚠ VSS Subsystem Failure Alert:</span>
                </div>
                <div>{inspectedJob.errorMessage}</div>
              </div>
            )}

            {/* Incremental Change Breakdown if available */}
            {(inspectedJob.filesNew !== undefined || inspectedJob.filesModified !== undefined || inspectedJob.backupType === 'Incremental') && (
              <div className="win-fieldset">
                <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
                  Incremental File Change Breakdown
                </legend>
                <div className="win-inset bg-[#dfdfdf] p-2 grid grid-cols-4 gap-2 text-center font-mono text-[11px]">
                  <div className="bg-white p-1 border border-[#808080]">
                    <span className="text-[#008000] block font-bold text-[13px]">{inspectedJob.filesNew ?? 0}</span>
                    <span className="text-[9px] text-[#505050]">NEW</span>
                  </div>
                  <div className="bg-white p-1 border border-[#808080]">
                    <span className="text-[#000080] block font-bold text-[13px]">{inspectedJob.filesModified ?? 0}</span>
                    <span className="text-[9px] text-[#505050]">MODIFIED</span>
                  </div>
                  <div className="bg-white p-1 border border-[#808080]">
                    <span className="text-black block font-bold text-[13px]">{inspectedJob.filesUnchanged ?? 0}</span>
                    <span className="text-[9px] text-[#505050]">UNCHANGED</span>
                  </div>
                  <div className="bg-white p-1 border border-[#808080]">
                    <span className="text-[#aa0000] block font-bold text-[13px]">{inspectedJob.filesDeleted ?? 0}</span>
                    <span className="text-[9px] text-[#505050]">DELETED</span>
                  </div>
                </div>
              </div>
            )}

            {/* Source folders */}
            <div className="win-fieldset">
              <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
                Source Paths & Exclusions
              </legend>
              <div className="win-inset bg-white p-2 font-mono text-[10px] text-black">
                {inspectedJob.source}
              </div>
            </div>
          </div>
        </WinDialog>
      )}
    </div>
  );
};
