import React from 'react';
import type { ObjectLockMode } from '../../api/v12';

interface ObjectLockBadgeProps {
  enabled: boolean;
  mode?: ObjectLockMode | null;
  retentionDays?: number | null;
  className?: string;
}

export const ObjectLockBadge: React.FC<ObjectLockBadgeProps> = ({
  enabled,
  mode,
  retentionDays,
  className = ''
}) => {
  if (!enabled) {
    return (
      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 win-inset-thin text-[10px] bg-[#dcdcdc] text-gray-600 font-mono ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block" />
        NO IMMUTABILITY
      </span>
    );
  }

  const isCompliance = mode === 'COMPLIANCE';

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 win-outset-thin text-[10px] font-bold ${
        isCompliance ? 'bg-[#000080] text-white' : 'bg-[#008080] text-white'
      } ${className}`}
      title={
        isCompliance
          ? 'Object Lock COMPLIANCE mode: Immutable WORM lock cannot be shortened or deleted by any user or administrator.'
          : 'Object Lock GOVERNANCE mode: Protected from deletion unless privileged override is supplied.'
      }
    >
      <span className="text-[10px]">🔒</span>
      <span>{isCompliance ? 'WORM COMPLIANCE' : 'GOVERNANCE LOCK'}</span>
      {retentionDays && <span className="opacity-90 font-normal">({retentionDays}d)</span>}
    </span>
  );
};

export default ObjectLockBadge;
