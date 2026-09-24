import React from 'react';
import type { StorageTier } from '../../api/v12';
import { ObjectLockBadge } from './ObjectLockBadge';
import { HardDriveIcon, CloudStorageIcon } from '../win95/WinIcons';

interface StorageTierCardProps {
  tier: StorageTier;
  selected?: boolean;
  onSelect?: (tier: StorageTier) => void;
  onOffload?: (tier: StorageTier) => void;
}

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export const StorageTierCard: React.FC<StorageTierCardProps> = ({
  tier,
  selected = false,
  onSelect,
  onOffload
}) => {
  const percentUsed =
    tier.total_capacity_bytes > 0
      ? Math.min(100, Math.round((tier.used_capacity_bytes / tier.total_capacity_bytes) * 100))
      : 0;

  const isCloud = tier.provider_type !== 'LOCAL';

  const getTierColor = (type: string) => {
    switch (type) {
      case 'HOT':
        return 'bg-[#ff6600] text-white';
      case 'COOL':
        return 'bg-[#008080] text-white';
      case 'COLD':
        return 'bg-[#000080] text-white';
      case 'ARCHIVE':
        return 'bg-[#400080] text-white';
      default:
        return 'bg-[#808080] text-white';
    }
  };

  return (
    <div
      onClick={() => onSelect?.(tier)}
      className={`p-2 cursor-pointer transition-all flex flex-col gap-2 ${
        selected ? 'win-inset bg-[#e6f2ff] border-2 border-[#000080]' : 'win-outset bg-[#c0c0c0] hover:bg-[#d4d4d4]'
      }`}
    >
      {/* Header */}
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-2">
          {isCloud ? <CloudStorageIcon size={18} /> : <HardDriveIcon size={18} />}
          <div>
            <div className="font-bold text-xs flex items-center gap-1.5">
              <span>{tier.name}</span>
              <span className={`px-1 py-0.2 text-[9px] rounded font-mono ${getTierColor(tier.tier_type)}`}>
                {tier.tier_type}
              </span>
            </div>
            <div className="text-[10px] text-gray-600 font-mono">
              ID: {tier.tier_id} &bull; {tier.provider_type}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <span
            className={`w-2 h-2 rounded-full inline-block ${
              tier.status === 'ONLINE' ? 'bg-[#00aa00]' : tier.status === 'DEGRADED' ? 'bg-[#ffaa00]' : 'bg-[#cc0000]'
            }`}
            title={`Status: ${tier.status}`}
          />
          <span className="text-[10px] font-bold">{tier.status}</span>
        </div>
      </div>

      {/* Capacity Bar */}
      <div className="flex flex-col gap-1">
        <div className="flex justify-between text-[10px]">
          <span className="text-gray-700">Capacity Usage:</span>
          <span className="font-mono font-bold">
            {formatBytes(tier.used_capacity_bytes)} / {formatBytes(tier.total_capacity_bytes)} ({percentUsed}%)
          </span>
        </div>
        <div className="w-full h-3 win-inset-gray relative overflow-hidden bg-[#dfdfdf]">
          <div
            className={`h-full transition-all duration-300 ${
              percentUsed > 85 ? 'bg-[#aa0000]' : percentUsed > 65 ? 'bg-[#ff9900]' : 'bg-[#000080]'
            }`}
            style={{ width: `${percentUsed}%` }}
          />
        </div>
      </div>

      {/* Badges & Meta */}
      <div className="flex justify-between items-center pt-1 border-t border-[#808080] text-[10px]">
        <ObjectLockBadge
          enabled={tier.object_lock_enabled}
          mode={tier.object_lock_mode}
          retentionDays={tier.retention_days}
        />

        {isCloud && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onOffload?.(tier);
            }}
            className="win-btn text-[10px] px-2 py-0.5 font-bold"
            title="Trigger policy-driven tiering offload to this cloud target"
          >
            Offload Data
          </button>
        )}
      </div>
    </div>
  );
};

export default StorageTierCard;
