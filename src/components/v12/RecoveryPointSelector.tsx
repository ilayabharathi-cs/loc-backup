import React, { useState } from 'react';
import { BackupTapeIcon, SearchIcon } from '../win95/WinIcons';

export interface RecoveryPointItem {
  id: string;
  client_id: string;
  client_name: string;
  workload_name: string;
  backup_type: 'FULL' | 'INCREMENTAL';
  consistency_mode: 'APPLICATION_CONSISTENT' | 'CRASH_CONSISTENT';
  size_bytes: number;
  created_at: string;
}

const mockAvailableRecoveryPoints: RecoveryPointItem[] = [
  {
    id: 'RP-20260924-0001',
    client_id: 'CLI-WINSRV-01',
    client_name: 'SRV-DB-PRIMARY',
    workload_name: 'SQL Server Core Financial DB',
    backup_type: 'FULL',
    consistency_mode: 'APPLICATION_CONSISTENT',
    size_bytes: 84 * 1024 * 1024 * 1024,
    created_at: '2026-09-24T06:00:00Z'
  },
  {
    id: 'RP-20260923-0045',
    client_id: 'CLI-WINSRV-02',
    client_name: 'SRV-FILE-02',
    workload_name: 'Corporate Document Repository',
    backup_type: 'INCREMENTAL',
    consistency_mode: 'CRASH_CONSISTENT',
    size_bytes: 210 * 1024 * 1024 * 1024,
    created_at: '2026-09-23T23:00:00Z'
  },
  {
    id: 'RP-20260923-0012',
    client_id: 'CLI-WINSRV-01',
    client_name: 'SRV-DB-PRIMARY',
    workload_name: 'SQL Server Audit Logs',
    backup_type: 'FULL',
    consistency_mode: 'APPLICATION_CONSISTENT',
    size_bytes: 32 * 1024 * 1024 * 1024,
    created_at: '2026-09-23T12:00:00Z'
  }
];

interface RecoveryPointSelectorProps {
  onSelect: (rp: RecoveryPointItem) => void;
  selectedRpId?: string | null;
}

export const RecoveryPointSelector: React.FC<RecoveryPointSelectorProps> = ({
  onSelect,
  selectedRpId
}) => {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredPoints = mockAvailableRecoveryPoints.filter(
    (rp) =>
      rp.workload_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      rp.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      rp.client_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-2 font-sans text-xs">
      {/* Search Input */}
      <div className="flex items-center gap-1.5 win-inset bg-white px-2 py-1">
        <SearchIcon size={14} className="text-gray-500" />
        <input
          type="text"
          className="w-full text-xs outline-none bg-transparent"
          placeholder="Filter recovery points by workload, client, or point ID..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      {/* Grid of Recovery Points */}
      <div className="win-inset bg-white overflow-auto max-h-56">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="bg-[#e0e0e0] sticky top-0 border-b border-[#808080]">
            <tr>
              <th className="p-1.5 border-r border-[#808080]">Recovery Point ID</th>
              <th className="p-1.5 border-r border-[#808080]">Workload</th>
              <th className="p-1.5 border-r border-[#808080]">Host</th>
              <th className="p-1.5 border-r border-[#808080]">Type</th>
              <th className="p-1.5 border-r border-[#808080]">Consistency</th>
              <th className="p-1.5 border-r border-[#808080]">Size</th>
              <th className="p-1.5">Created</th>
            </tr>
          </thead>
          <tbody>
            {filteredPoints.map((rp) => {
              const isSelected = selectedRpId === rp.id;
              return (
                <tr
                  key={rp.id}
                  onClick={() => onSelect(rp)}
                  className={`cursor-pointer border-b border-gray-200 select-none ${
                    isSelected ? 'bg-[#000080] text-white' : 'hover:bg-[#f0f0f0]'
                  }`}
                >
                  <td className="p-1.5 font-mono font-bold flex items-center gap-1">
                    <BackupTapeIcon size={14} />
                    <span>{rp.id}</span>
                  </td>
                  <td className="p-1.5 font-semibold">{rp.workload_name}</td>
                  <td className="p-1.5">{rp.client_name}</td>
                  <td className="p-1.5 font-mono text-[10px]">{rp.backup_type}</td>
                  <td className="p-1.5">
                    <span
                      className={`text-[9px] px-1 py-0.2 rounded font-bold ${
                        isSelected
                          ? 'bg-blue-300 text-black'
                          : rp.consistency_mode === 'APPLICATION_CONSISTENT'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}
                    >
                      {rp.consistency_mode === 'APPLICATION_CONSISTENT' ? 'APP-CONSISTENT' : 'CRASH-CONSISTENT'}
                    </span>
                  </td>
                  <td className="p-1.5 font-mono">{(rp.size_bytes / (1024 * 1024 * 1024)).toFixed(1)} GB</td>
                  <td className="p-1.5 text-[10px]">{new Date(rp.created_at).toLocaleString()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RecoveryPointSelector;
