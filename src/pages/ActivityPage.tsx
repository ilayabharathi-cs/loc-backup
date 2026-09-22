import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import type { ActivityLog } from '../types';
import { WinTable } from '../components/win95/WinTable';
import type { Column } from '../components/win95/WinTable';
import { WinButton } from '../components/win95/WinButton';
import { WinBadge } from '../components/win95/WinBadge';
import { ActivityLogIcon, ComputerIcon } from '../components/win95/WinIcons';

export const ActivityPage: React.FC = () => {
  const { logs, addToast } = useApp();

  const [severityFilter, setSeverityFilter] = useState<'ALL' | 'INFO' | 'WARNING' | 'ERROR'>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<'ALL' | 'BACKUP' | 'RESTORE'>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedLogId, setSelectedLogId] = useState<string | null>(logs[0]?.id || null);

  const filteredLogs = logs.filter(l => {
    if (severityFilter !== 'ALL' && l.severity !== severityFilter) return false;
    if (categoryFilter !== 'ALL' && l.event !== categoryFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        l.message.toLowerCase().includes(q) ||
        l.clientId.toLowerCase().includes(q) ||
        l.event.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const selectedLog = logs.find(l => l.id === selectedLogId) || null;

  const columns: Column<ActivityLog>[] = [
    {
      key: 'time',
      header: 'Time',
      width: '85px',
      sortable: true,
      render: (log) => <span className="font-mono text-[10px]">{log.time}</span>,
    },
    {
      key: 'clientId',
      header: 'Client / Target',
      width: '110px',
      sortable: true,
      render: (log) => (
        <span className="font-mono font-bold text-black flex items-center gap-1">
          <ComputerIcon size={12} />
          <span>{log.clientId}</span>
        </span>
      ),
    },
    {
      key: 'event',
      header: 'Event Category',
      width: '95px',
      sortable: true,
      render: (log) => <span className="font-mono text-[10px] font-semibold">{log.event}</span>,
    },
    {
      key: 'severity',
      header: 'Severity',
      width: '95px',
      align: 'center',
      sortable: true,
      render: (log) => <WinBadge status={log.severity} type="severity" />,
    },
    {
      key: 'message',
      header: 'Log Message',
      render: (log) => <span className="truncate">{log.message}</span>,
    },
  ];

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-hidden bg-[#c0c0c0]">
      {/* Top Controls & Filter Bar */}
      <div className="win-outset p-2 flex items-center justify-between gap-3 bg-[#c0c0c0] shrink-0">
        {/* Severity Filters */}
        <div className="flex items-center gap-1">
          <span className="text-[11px] font-bold text-black mr-1">Severity:</span>
          <WinButton
            size="sm"
            active={severityFilter === 'ALL'}
            onClick={() => setSeverityFilter('ALL')}
          >
            All
          </WinButton>
          <WinButton
            size="sm"
            active={severityFilter === 'INFO'}
            onClick={() => setSeverityFilter('INFO')}
          >
            [INFO]
          </WinButton>
          <WinButton
            size="sm"
            active={severityFilter === 'WARNING'}
            onClick={() => setSeverityFilter('WARNING')}
          >
            [WARNING]
          </WinButton>
          <WinButton
            size="sm"
            active={severityFilter === 'ERROR'}
            onClick={() => setSeverityFilter('ERROR')}
          >
            [ERROR]
          </WinButton>
        </div>

        {/* Category Filters */}
        <div className="flex items-center gap-1">
          <span className="text-[11px] font-bold text-black mr-1">Event:</span>
          <WinButton
            size="sm"
            active={categoryFilter === 'ALL'}
            onClick={() => setCategoryFilter('ALL')}
          >
            All
          </WinButton>
          <WinButton
            size="sm"
            active={categoryFilter === 'BACKUP'}
            onClick={() => setCategoryFilter('BACKUP')}
          >
            [BACKUP]
          </WinButton>
          <WinButton
            size="sm"
            active={categoryFilter === 'RESTORE'}
            onClick={() => setCategoryFilter('RESTORE')}
          >
            [RESTORE]
          </WinButton>
        </div>

        {/* Search & Actions */}
        <div className="flex items-center gap-1.5">
          <input
            type="text"
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="win-inset bg-white px-2 py-0.5 text-[11px] w-40 text-black"
          />
          <WinButton
            onClick={() => {
              addToast('Log Export', 'Activity event log exported to D:\\RetroVault_Events.evtx', 'success');
            }}
          >
            Export Log...
          </WinButton>
        </div>
      </div>

      {/* Main Log Table (Split View) */}
      <div className="flex-1 flex flex-col min-h-0 bg-[#c0c0c0]">
        <WinTable
          columns={columns}
          data={filteredLogs}
          keyExtractor={(l) => l.id}
          selectedId={selectedLogId}
          onSelect={(l) => setSelectedLogId(l.id)}
          className="flex-1"
        />
      </div>

      {/* Windows Event Viewer Detail Preview Pane */}
      <div className="win-fieldset h-36 flex flex-col p-2 bg-[#c0c0c0] shrink-0">
        <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1 flex items-center gap-1">
          <ActivityLogIcon size={12} />
          <span>EVENT LOG RECORD DETAILS</span>
        </legend>

        {selectedLog ? (
          <div className="win-inset bg-white p-2 flex-1 overflow-y-auto font-mono text-[10px] text-black select-text flex flex-col gap-1">
            <div className="flex items-center justify-between border-b border-[#dfdfdf] pb-1 font-bold">
              <span>Event: {selectedLog.event} [{selectedLog.severity}]</span>
              <span>Client: {selectedLog.clientId} | Logged: {selectedLog.time}</span>
            </div>
            <div className="font-semibold text-[11px] text-[#000080]">
              {selectedLog.message}
            </div>
            {selectedLog.details && (
              <div className="text-[#404040] pt-1 border-t border-dotted border-[#808080]">
                {selectedLog.details}
              </div>
            )}
          </div>
        ) : (
          <div className="win-inset bg-white p-2 flex-1 flex items-center justify-center text-[#808080] italic">
            Select a log entry from the table above to view complete diagnostic telemetry.
          </div>
        )}
      </div>
    </div>
  );
};
