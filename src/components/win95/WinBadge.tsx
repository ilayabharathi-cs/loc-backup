import React from 'react';
import type { ClientStatus, JobStatus, LogSeverity } from '../../types';

interface WinBadgeProps {
  status?: ClientStatus | JobStatus | LogSeverity | string;
  type?: 'client' | 'job' | 'severity' | 'custom';
  className?: string;
  label?: string;
}

export const WinBadge: React.FC<WinBadgeProps> = ({
  status,
  type = 'custom',
  className = '',
  label,
}) => {
  let text = label || status || '';
  let dotColor = '#808080';
  let textColor = '#000000';
  let bgColor = '#dfdfdf';

  if (type === 'client') {
    switch (status) {
      case 'ONLINE':
        dotColor = '#00aa00';
        text = 'ONLINE';
        break;
      case 'OFFLINE':
        dotColor = '#aa0000';
        text = 'OFFLINE';
        break;
      case 'WARNING':
        dotColor = '#ffaa00';
        text = 'WARNING';
        break;
      case 'BACKING_UP':
        dotColor = '#0055ff';
        text = 'BACKING UP';
        break;
    }
  } else if (type === 'job') {
    switch (status) {
      case 'SUCCESS':
        dotColor = '#00aa00';
        text = 'SUCCESS';
        break;
      case 'RUNNING':
        dotColor = '#0055ff';
        text = 'RUNNING';
        break;
      case 'FAILED':
        dotColor = '#aa0000';
        text = 'FAILED';
        break;
      case 'PAUSED':
        dotColor = '#ffaa00';
        text = 'PAUSED';
        break;
    }
  } else if (type === 'severity') {
    switch (status) {
      case 'INFO':
        dotColor = '#000080';
        text = 'INFO';
        break;
      case 'WARNING':
        dotColor = '#cc8800';
        text = 'WARNING';
        break;
      case 'ERROR':
        dotColor = '#cc0000';
        text = 'ERROR';
        break;
    }
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-1.5 py-0.2 win-inset-thin text-[10px] font-mono tracking-tight ${className}`}
      style={{ backgroundColor: bgColor, color: textColor }}
    >
      <span
        className="w-2 h-2 rounded-full inline-block border border-black/40 shadow-xs"
        style={{ backgroundColor: dotColor }}
      />
      <span className="font-semibold">{text}</span>
    </span>
  );
};
