import type { Client, BackupJob, BackupPolicy, RecoveryPoint, BackupFileNode, StorageMetrics, ActivityLog, AppSettings } from '../types';

// Zero mock clients - only real clients registered from agents appear
export const INITIAL_CLIENTS: Client[] = [];

// Zero mock jobs - only real backup runs appear
export const INITIAL_JOBS: BackupJob[] = [];

// Default System Backup Policies
export const INITIAL_POLICIES: BackupPolicy[] = [
  {
    id: 'POL-001',
    name: 'Windows User Data',
    description: 'Standard enterprise workstation policy safeguarding essential user directories',
    protectedFolders: [
      { path: '%USERPROFILE%\\Documents', isUniversal: true, enabled: false },
      { path: '%USERPROFILE%\\Desktop', isUniversal: true, enabled: false },
      { path: '%USERPROFILE%\\Downloads', isUniversal: true, enabled: false },
      { path: '%USERPROFILE%\\Pictures', isUniversal: true, enabled: false }
    ],
    customFolders: [],
    excludedPaths: ['%TEMP%', '%LOCALAPPDATA%\\Temp', 'C:\\Windows\\Temp', '*.tmp', '*.log', '*.cache'],
    backupType: 'Incremental',
    changeDetection: 'USN Journal',
    rpoTargetSeconds: 120,
    compressionEnabled: true,
    encryptionEnabled: true,
    cpuLimitPercent: 10,
    networkLimitMbps: 100,
    retentionDays: 7,
    appliedClientsCount: 0
  },
  {
    id: 'POL-002',
    name: 'Finance Sensitive Vault',
    description: 'High-frequency encrypted backup with strict RPO and immutable retention',
    protectedFolders: [
      { path: '%USERPROFILE%\\Documents', isUniversal: true, enabled: false },
      { path: '%USERPROFILE%\\Desktop', isUniversal: true, enabled: false }
    ],
    customFolders: [],
    excludedPaths: ['%TEMP%', '*.bak', '*.swp', '*.tmp'],
    backupType: 'Incremental',
    changeDetection: 'USN Journal',
    rpoTargetSeconds: 60,
    compressionEnabled: true,
    encryptionEnabled: true,
    cpuLimitPercent: 15,
    networkLimitMbps: 150,
    retentionDays: 30,
    appliedClientsCount: 0
  },
  {
    id: 'POL-003',
    name: 'Developer Workstation',
    description: 'Code repository backup with build-artifact exclusions',
    protectedFolders: [
      { path: '%USERPROFILE%\\Documents', isUniversal: true, enabled: false },
      { path: '%USERPROFILE%\\Desktop', isUniversal: true, enabled: false }
    ],
    customFolders: [],
    excludedPaths: ['%TEMP%', 'node_modules', 'target', '.git', '*.pdb', '*.obj', '*.o', '*.dmp'],
    backupType: 'Incremental',
    changeDetection: 'USN Journal',
    rpoTargetSeconds: 120,
    compressionEnabled: true,
    encryptionEnabled: true,
    cpuLimitPercent: 20,
    networkLimitMbps: 200,
    retentionDays: 14,
    appliedClientsCount: 0
  }
];

export const INITIAL_STORAGE: StorageMetrics = {
  repositoryPath: './repository',
  totalTb: 1.0,
  usedTb: 0.0,
  freeTb: 1.0,
  diskHealth: 'ONLINE',
  backupObjectsCount: 0,
  recoveryPointsCount: 0,
  dedupRatio: 1.0,
  compressionRatio: 1.0,
  lastVerification: 'Never'
};

export const MOCK_RECOVERY_POINTS: Record<string, RecoveryPoint[]> = {};

export const MOCK_FILE_TREE: BackupFileNode = {
  id: 'node-root',
  name: 'No Recovery Points',
  path: '/',
  isDirectory: true,
  modified: '',
  children: []
};

export const INITIAL_LOGS: ActivityLog[] = [];

export const INITIAL_SETTINGS: AppSettings = {
  server: {
    serverName: 'RETROVAULT-PRIMARY-01',
    serverIp: '127.0.0.1',
    apiPort: 8000,
    repositoryPath: './repository'
  },
  security: {
    authType: 'JWT Authentication',
    tlsStatus: true,
    encryptionAlgorithm: 'AES-256-GCM',
    rbacEnabled: true,
    sessionTimeoutMinutes: 60
  },
  agent: {
    minimumAgentVersion: '1.0.0',
    heartbeatIntervalSeconds: 30,
    retryCount: 3,
    bandwidthThrottleEnabled: false
  },
  notifications: {
    backupFailure: true,
    clientOffline: true,
    rpoBreach: true,
    storageLow: true,
    alertEmail: 'admin@retrovault.local'
  }
};
