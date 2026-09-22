import React from 'react';

interface IconProps {
  className?: string;
  size?: number;
}

export const ComputerIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <rect x="2" y="2" width="12" height="9" fill="#000080" stroke="#000000" strokeWidth="1" />
    <rect x="3" y="3" width="10" height="7" fill="#008080" />
    <rect x="6" y="11" width="4" height="2" fill="#c0c0c0" stroke="#808080" strokeWidth="0.5" />
    <path d="M4 13 H12 V14 H4 Z" fill="#808080" />
    <rect x="4" y="14" width="8" height="1" fill="#000000" />
  </svg>
);

export const HardDriveIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <rect x="2" y="4" width="12" height="8" fill="#c0c0c0" stroke="#000000" strokeWidth="1" />
    <rect x="4" y="6" width="3" height="4" fill="#808080" />
    <circle cx="11" cy="8" r="1" fill="#00ff00" />
    <circle cx="9" cy="8" r="1" fill="#ff0000" />
  </svg>
);

export const FolderIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <path d="M1 3 H6 L8 5 H15 V13 H1 Z" fill="#ffff80" stroke="#808000" strokeWidth="1" />
    <path d="M2 5 H14 V12 H2 Z" fill="#ffff00" />
    <path d="M1 5 H15 V6 H1 Z" fill="#ffffff" opacity="0.6" />
  </svg>
);

export const FolderOpenIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <path d="M1 3 H6 L8 5 H14 V7 H1 Z" fill="#ffff80" stroke="#808000" strokeWidth="1" />
    <polygon points="1,13 4,7 15,7 13,13" fill="#ffff00" stroke="#808000" strokeWidth="1" />
  </svg>
);

export const DocumentIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <path d="M3 1 H10 L13 4 V15 H3 Z" fill="#ffffff" stroke="#000000" strokeWidth="1" />
    <polygon points="10,1 10,4 13,4" fill="#c0c0c0" stroke="#000000" strokeWidth="0.8" />
    <line x1="5" y1="6" x2="11" y2="6" stroke="#808080" strokeWidth="1" strokeDasharray="1,1" />
    <line x1="5" y1="8" x2="11" y2="8" stroke="#808080" strokeWidth="1" strokeDasharray="1,1" />
    <line x1="5" y1="10" x2="10" y2="10" stroke="#808080" strokeWidth="1" strokeDasharray="1,1" />
  </svg>
);

export const BackupTapeIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <rect x="1" y="3" width="14" height="10" rx="1" fill="#404040" stroke="#000000" strokeWidth="1" />
    <rect x="3" y="5" width="10" height="6" fill="#808080" />
    <circle cx="5.5" cy="8" r="1.5" fill="#ffffff" stroke="#000000" strokeWidth="0.8" />
    <circle cx="10.5" cy="8" r="1.5" fill="#ffffff" stroke="#000000" strokeWidth="0.8" />
    <line x1="5.5" y1="8" x2="10.5" y2="8" stroke="#000000" strokeWidth="0.8" />
  </svg>
);

export const ShieldCheckIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <path d="M8 1 L14 4 V8 C14 12 8 15 8 15 C8 15 2 12 2 8 V4 Z" fill="#000080" stroke="#000000" strokeWidth="1" />
    <path d="M5 8 L7 10 L11 5" stroke="#ffffff" strokeWidth="1.5" strokeLinecap="square" />
  </svg>
);

export const ServerIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <rect x="2" y="2" width="12" height="3.5" fill="#c0c0c0" stroke="#000000" strokeWidth="1" />
    <circle cx="4" cy="3.75" r="0.8" fill="#00ff00" />
    <rect x="2" y="6.25" width="12" height="3.5" fill="#c0c0c0" stroke="#000000" strokeWidth="1" />
    <circle cx="4" cy="8" r="0.8" fill="#00ff00" />
    <rect x="2" y="10.5" width="12" height="3.5" fill="#c0c0c0" stroke="#000000" strokeWidth="1" />
    <circle cx="4" cy="12.25" r="0.8" fill="#00ff00" />
  </svg>
);

export const SettingsWrenchIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <path d="M13 3 A3 3 0 0 0 8 7 L3 12 L4 13 L6 13 L7 12 L10 9 A3 3 0 0 0 13 3 Z" fill="#c0c0c0" stroke="#000000" strokeWidth="1" />
    <circle cx="11.5" cy="4.5" r="1" fill="#ffffff" />
  </svg>
);

export const ActivityLogIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <rect x="2" y="1" width="12" height="14" fill="#ffffff" stroke="#000000" strokeWidth="1" />
    <rect x="4" y="3" width="8" height="2" fill="#000080" />
    <line x1="4" y1="7" x2="8" y2="7" stroke="#000000" strokeWidth="1" />
    <line x1="4" y1="9" x2="11" y2="9" stroke="#808080" strokeWidth="1" />
    <line x1="4" y1="11" x2="10" y2="11" stroke="#808080" strokeWidth="1" />
  </svg>
);

export const CheckIcon: React.FC<IconProps> = ({ className = '', size = 14 }) => (
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none" className={`inline-block shrink-0 ${className}`}>
    <path d="M2 7 L5 10 L12 2" stroke="#008000" strokeWidth="2" strokeLinecap="square" />
  </svg>
);

export const WarningIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <polygon points="8,1 15,14 1,14" fill="#ffff00" stroke="#000000" strokeWidth="1" />
    <line x1="8" y1="6" x2="8" y2="9" stroke="#000000" strokeWidth="1.5" />
    <circle cx="8" cy="11.5" r="0.8" fill="#000000" />
  </svg>
);

export const ErrorIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <circle cx="8" cy="8" r="6" fill="#ff0000" stroke="#000000" strokeWidth="1" />
    <line x1="5" y1="5" x2="11" y2="11" stroke="#ffffff" strokeWidth="1.8" />
    <line x1="11" y1="5" x2="5" y2="11" stroke="#ffffff" strokeWidth="1.8" />
  </svg>
);

export const InfoIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <circle cx="8" cy="8" r="6" fill="#000080" stroke="#000000" strokeWidth="1" />
    <circle cx="8" cy="5" r="1" fill="#ffffff" />
    <rect x="7" y="7" width="2" height="4" fill="#ffffff" />
  </svg>
);

export const RecycleBinIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <rect x="4" y="4" width="8" height="10" fill="#808080" stroke="#000000" strokeWidth="1" />
    <path d="M2 3 H14 V4 H2 Z" fill="#c0c0c0" stroke="#000000" strokeWidth="0.8" />
    <rect x="6" y="1" width="4" height="2" fill="#c0c0c0" stroke="#000000" strokeWidth="0.8" />
  </svg>
);

export const RestoreArrowIcon: React.FC<IconProps> = ({ className = '', size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={`inline-block shrink-0 ${className}`}>
    <path d="M12 4 H7 A4 4 0 0 0 3 8 A4 4 0 0 0 7 12 H12" stroke="#000080" strokeWidth="2" />
    <polyline points="10,2 14,4 10,6" fill="#000080" />
  </svg>
);
