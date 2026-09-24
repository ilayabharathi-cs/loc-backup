import React from 'react';
import type { InstantMountSession } from '../../api/v12';
import { HardDriveIcon, InstantMountIcon } from '../win95/WinIcons';

interface MountStatusPanelProps {
  session: InstantMountSession;
  onDismount: (session: InstantMountSession) => void;
}

export const MountStatusPanel: React.FC<MountStatusPanelProps> = ({ session, onDismount }) => {
  const isMounting = session.status === 'MOUNTING';
  const isActive = session.status === 'ACTIVE';
  const isDismounted = session.status === 'DISMOUNTED';
  const isError = session.status === 'ERROR';

  return (
    <div className="win-outset p-3 bg-[#dcdcdc] flex flex-col gap-3 font-sans text-xs">
      {/* Header */}
      <div className="flex justify-between items-center border-b border-[#808080] pb-2">
        <div className="flex items-center gap-2">
          <InstantMountIcon size={18} />
          <div>
            <strong className="text-xs">{session.workload_name || 'Instant Workload Mount'}</strong>
            <div className="text-[10px] text-gray-500 font-mono">{session.mount_id}</div>
          </div>
        </div>

        <div>
          {isMounting && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-600 text-white animate-pulse">
              MOUNTING...
            </span>
          )}
          {isActive && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-green-700 text-white flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-white inline-block" />
              ACTIVE LIVE MOUNT
            </span>
          )}
          {isDismounted && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-gray-500 text-white">
              DISMOUNTED
            </span>
          )}
          {isError && (
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-700 text-white">
              MOUNT ERROR
            </span>
          )}
        </div>
      </div>

      {/* Mount Path Banner */}
      <div className="win-inset bg-white p-2.5 flex items-center justify-between">
        <div>
          <span className="text-[10px] text-gray-500 block uppercase font-bold">Assigned Virtual Mount Point</span>
          <div className="font-mono text-sm font-bold text-[#000080] flex items-center gap-1.5 mt-0.5">
            <HardDriveIcon size={14} />
            <span>{session.mount_point}</span>
          </div>
        </div>
        <div className="text-right">
          <span className="text-[10px] text-gray-500 block uppercase font-bold">Mount Mode</span>
          <span className="px-1.5 py-0.5 bg-gray-100 border border-gray-400 font-mono text-[10px] font-bold">
            {session.mount_mode === 'READ_WRITE_COW' ? 'READ/WRITE (COW SNAPSHOT)' : 'READ-ONLY EXPOSURE'}
          </span>
        </div>
      </div>

      {/* Detail Grid */}
      <div className="win-inset bg-[#fdfdfd] p-2.5 grid grid-cols-2 gap-2 text-[11px]">
        <div>
          <span className="text-gray-600 block">Target Client Host:</span>
          <strong>{session.target_hostname}</strong>
        </div>
        <div>
          <span className="text-gray-600 block">Recovery Point Source:</span>
          <code className="text-[10px] font-mono">{session.recovery_point_id}</code>
        </div>
        <div>
          <span className="text-gray-600 block">Mounted Since:</span>
          <span>{session.mounted_at ? new Date(session.mounted_at).toLocaleString() : 'Pending'}</span>
        </div>
        <div>
          <span className="text-gray-600 block">Virtual Volume Size:</span>
          <span className="font-mono font-bold">{(session.bytes_mounted / (1024 * 1024 * 1024)).toFixed(1)} GB</span>
        </div>
      </div>

      {/* Safety Notice & Action */}
      <div className="flex justify-between items-center pt-2 border-t border-[#808080]">
        <div className="text-[10px] text-gray-600 max-w-xs">
          Instant Recovery bypasses physical data restoration by presenting CAS blocks as a virtual block device directly to target workloads.
        </div>

        {isActive && (
          <button
            onClick={() => onDismount(session)}
            className="win-btn px-3 py-1 font-bold text-[#cc0000] bg-[#ffebee]"
            title="Safely flush buffers and release virtual mount point"
          >
            Safe Dismount...
          </button>
        )}
      </div>
    </div>
  );
};

export default MountStatusPanel;
