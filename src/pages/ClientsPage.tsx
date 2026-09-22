import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import type { Client } from '../types';
import { WinTable } from '../components/win95/WinTable';
import type { Column } from '../components/win95/WinTable';
import { WinButton } from '../components/win95/WinButton';
import { WinBadge } from '../components/win95/WinBadge';
import { WinContextMenu } from '../components/win95/WinContextMenu';
import type { ContextMenuItem } from '../components/win95/WinContextMenu';
import { ClientDetailDialog } from '../components/dialogs/ClientDetailDialog';
import { ComputerIcon, BackupTapeIcon, RestoreArrowIcon, ActivityLogIcon, ShieldCheckIcon } from '../components/win95/WinIcons';

export const ClientsPage: React.FC = () => {
  const { clients, triggerBackup, addToast } = useApp();
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ONLINE' | 'OFFLINE' | 'WARNING'>('ALL');
  const [selectedClientId, setSelectedClientId] = useState<string | null>(clients[0]?.id || null);
  const [detailModalClient, setDetailModalClient] = useState<Client | null>(null);

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; client: Client } | null>(null);

  const filteredClients = clients.filter(c => {
    const matchesSearch = 
      c.hostname.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.ipAddress.includes(searchQuery);

    if (!matchesSearch) return false;
    if (statusFilter === 'ALL') return true;
    if (statusFilter === 'ONLINE') return c.status === 'ONLINE' || c.status === 'BACKING_UP';
    if (statusFilter === 'OFFLINE') return c.status === 'OFFLINE';
    if (statusFilter === 'WARNING') return c.status === 'WARNING';
    return true;
  });

  const selectedClient = clients.find(c => c.id === selectedClientId) || null;

  const handleRowContextMenu = (client: Client, e: React.MouseEvent) => {
    setSelectedClientId(client.id);
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      client,
    });
  };

  const getContextMenuItems = (client: Client): ContextMenuItem[] => [
    {
      label: `Backup ${client.hostname} Now`,
      icon: <BackupTapeIcon size={14} />,
      action: () => triggerBackup(client.id),
    },
    {
      label: 'Initiate Recovery Wizard...',
      icon: <RestoreArrowIcon size={14} />,
      action: () => navigate('/restore'),
    },
    { divider: true, label: '', action: () => {} },
    {
      label: 'View Workstation Event Logs',
      icon: <ActivityLogIcon size={14} />,
      action: () => navigate('/activity'),
    },
    {
      label: 'Edit Assigned Policy...',
      icon: <ShieldCheckIcon size={14} />,
      action: () => navigate('/policies'),
    },
    { divider: true, label: '', action: () => {} },
    {
      label: 'Client Properties...',
      icon: <ComputerIcon size={14} />,
      action: () => setDetailModalClient(client),
    },
  ];

  const columns: Column<Client>[] = [
    {
      key: 'id',
      header: 'Client ID',
      width: '90px',
      sortable: true,
      render: (client) => (
        <span className="font-mono font-bold text-black flex items-center gap-1.5">
          <ComputerIcon size={13} />
          <span>{client.id}</span>
        </span>
      ),
    },
    {
      key: 'hostname',
      header: 'Hostname',
      width: '130px',
      sortable: true,
      render: (client) => <span className="font-mono font-bold text-black">{client.hostname}</span>,
    },
    {
      key: 'user',
      header: 'User',
      width: '120px',
      sortable: true,
      render: (client) => <span className="truncate">{client.user}</span>,
    },
    {
      key: 'os',
      header: 'Operating System',
      width: '140px',
      sortable: true,
      render: (client) => <span className="truncate text-[10px]">{client.os}</span>,
    },
    {
      key: 'agentVersion',
      header: 'Agent',
      width: '70px',
      sortable: true,
      render: (client) => <span className="font-mono text-[10px]">v{client.agentVersion}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      width: '100px',
      align: 'center',
      sortable: true,
      render: (client) => <WinBadge status={client.status} type="client" />,
    },
    {
      key: 'lastSeen',
      header: 'Last Seen',
      width: '90px',
      sortable: true,
      render: (client) => <span className="text-[10px] text-[#404040]">{client.lastSeen}</span>,
    },
    {
      key: 'lastBackup',
      header: 'Last Backup',
      width: '90px',
      sortable: true,
      render: (client) => <span className="font-mono text-[10px] font-semibold">{client.lastBackup}</span>,
    },
    {
      key: 'rpoSeconds',
      header: 'RPO',
      width: '80px',
      sortable: true,
      render: (client) => {
        const isBreached = client.rpoSeconds > 120;
        const text = client.rpoSeconds < 60 
          ? `${client.rpoSeconds}s` 
          : `${Math.round(client.rpoSeconds / 60)}m`;
        return (
          <span className={`font-mono text-[10px] font-bold ${isBreached ? 'text-[#cc0000]' : 'text-[#008000]'}`}>
            {text}
          </span>
        );
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      width: '160px',
      align: 'center',
      render: (client) => (
        <div className="flex items-center justify-center gap-1">
          <WinButton
            size="sm"
            onClick={() => triggerBackup(client.id)}
            title="Run manual incremental snapshot"
          >
            Backup
          </WinButton>
          <WinButton
            size="sm"
            onClick={() => setDetailModalClient(client)}
            title="Inspect properties and protected paths"
          >
            Details
          </WinButton>
        </div>
      ),
    },
  ];

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-hidden bg-[#c0c0c0]">
      {/* Top Controls Bar */}
      <div className="win-outset p-2 flex items-center justify-between gap-3 bg-[#c0c0c0] shrink-0">
        {/* Search */}
        <div className="flex items-center gap-2">
          <span className="font-bold text-black text-[11px]">Filter Clients:</span>
          <input
            type="text"
            placeholder="Search by ID, Hostname, User, or IP..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="win-inset bg-white px-2 py-0.5 text-[11px] w-64 text-black font-sans"
          />
          {searchQuery && (
            <WinButton size="sm" onClick={() => setSearchQuery('')}>Clear</WinButton>
          )}
        </div>

        {/* Status Filter Chips */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-[#505050] mr-1">Status:</span>
          <WinButton
            size="sm"
            active={statusFilter === 'ALL'}
            onClick={() => setStatusFilter('ALL')}
          >
            All ({clients.length})
          </WinButton>
          <WinButton
            size="sm"
            active={statusFilter === 'ONLINE'}
            onClick={() => setStatusFilter('ONLINE')}
          >
            Online ({clients.filter(c => c.status === 'ONLINE' || c.status === 'BACKING_UP').length})
          </WinButton>
          <WinButton
            size="sm"
            active={statusFilter === 'OFFLINE'}
            onClick={() => setStatusFilter('OFFLINE')}
          >
            Offline ({clients.filter(c => c.status === 'OFFLINE').length})
          </WinButton>
          <WinButton
            size="sm"
            active={statusFilter === 'WARNING'}
            onClick={() => setStatusFilter('WARNING')}
          >
            Warning ({clients.filter(c => c.status === 'WARNING').length})
          </WinButton>
        </div>

        {/* Global Toolbar Actions */}
        <div className="flex items-center gap-1">
          <WinButton
            isDefault
            disabled={!selectedClient}
            onClick={() => selectedClient && setDetailModalClient(selectedClient)}
          >
            Properties...
          </WinButton>
          <WinButton
            onClick={() => {
              addToast('Client Export', 'Exported 20 enrolled workstation profiles to D:\\Clients-Inventory.csv', 'success');
            }}
          >
            Export List...
          </WinButton>
        </div>
      </div>

      {/* Main Clients Table */}
      <div className="flex-1 flex flex-col min-h-0 bg-[#c0c0c0]">
        <WinTable
          columns={columns}
          data={filteredClients}
          keyExtractor={(c) => c.id}
          selectedId={selectedClientId}
          onSelect={(c) => setSelectedClientId(c.id)}
          onDoubleClick={(c) => setDetailModalClient(c)}
          onContextMenu={handleRowContextMenu}
          className="flex-1"
        />
      </div>

      {/* Table Footer Helper */}
      <div className="win-inset-gray px-2 py-1 text-[10px] text-[#404040] flex items-center justify-between shrink-0 bg-[#dfdfdf]">
        <span>
          Showing {filteredClients.length} of {clients.length} enrolled enterprise clients. Double-click or Right-click any row for context menu actions.
        </span>
        {selectedClient && (
          <span className="font-mono">
            Selected: <b>{selectedClient.hostname}</b> ({selectedClient.ipAddress}) | Policy: <b>{selectedClient.policyName}</b>
          </span>
        )}
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <WinContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={getContextMenuItems(contextMenu.client)}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Client Detail Dialog */}
      <ClientDetailDialog
        client={detailModalClient}
        isOpen={Boolean(detailModalClient)}
        onClose={() => setDetailModalClient(null)}
      />
    </div>
  );
};
