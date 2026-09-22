export type ClientStatus = 'ONLINE' | 'OFFLINE' | 'WARNING' | 'BACKING_UP';

export interface Client {
  id: string;
  hostname: string;
  user: string;
  os: string;
  agentVersion: string;
  ipAddress: string;
  cpu: string;
  ram: string;
  status: ClientStatus;
  lastSeen: string;
  lastBackup: string;
  rpoSeconds: number;
  storageConsumedGb: number;
  policyId: string;
  policyName: string;
  universalPaths: string[];
  customPaths: string[];
  excludedPaths: string[];
}

export type JobStatus = 'SUCCESS' | 'RUNNING' | 'FAILED' | 'PAUSED';
export type BackupType = 'Full' | 'Incremental';

export interface BackupJob {
  id: string;
  clientId: string;
  clientHostname: string;
  policyName: string;
  backupType: BackupType;
  source: string;
  started: string;
  completed: string | null;
  duration: string;
  dataProcessedMb: number;
  status: JobStatus;
  progressPercent?: number;
  errorMessage?: string;
  changeDetection?: string;
  transferSpeedMbps?: number;
}

export interface PolicyFolder {
  path: string;
  isUniversal: boolean;
  enabled: boolean;
}

export interface BackupPolicy {
  id: string;
  name: string;
  description: string;
  protectedFolders: PolicyFolder[];
  customFolders: string[];
  excludedPaths: string[];
  backupType: BackupType;
  changeDetection: 'USN Journal' | 'File Watcher' | 'Timestamp';
  rpoTargetSeconds: number;
  compressionEnabled: boolean;
  encryptionEnabled: boolean;
  cpuLimitPercent: number;
  networkLimitMbps: number;
  retentionDays: number;
  appliedClientsCount?: number;
}

export interface RecoveryPoint {
  id: string;
  clientId: string;
  timestamp: string;
  type: BackupType;
  sizeMb: number;
  fileCount: number;
  rootPath: string;
}

export interface BackupFileNode {
  id: string;
  name: string;
  path: string;
  isDirectory: boolean;
  sizeBytes?: number;
  modified: string;
  children?: BackupFileNode[];
}

export interface StorageMetrics {
  repositoryPath: string;
  totalTb: number;
  usedTb: number;
  freeTb: number;
  diskHealth: string;
  backupObjectsCount: number;
  recoveryPointsCount: number;
  dedupRatio: number;
  compressionRatio: number;
  lastVerification: string;
}

export type LogSeverity = 'INFO' | 'WARNING' | 'ERROR';
export type LogEventCategory = 'BACKUP' | 'RESTORE' | 'POLICY' | 'SYSTEM' | 'AGENT' | 'SECURITY';

export interface ActivityLog {
  id: string;
  time: string;
  clientId: string;
  event: LogEventCategory;
  severity: LogSeverity;
  message: string;
  details?: string;
}

export interface AppSettings {
  server: {
    serverName: string;
    serverIp: string;
    apiPort: number;
    repositoryPath: string;
  };
  security: {
    authType: string;
    tlsStatus: boolean;
    encryptionAlgorithm: string;
    rbacEnabled: boolean;
    sessionTimeoutMinutes: number;
  };
  agent: {
    minimumAgentVersion: string;
    heartbeatIntervalSeconds: number;
    retryCount: number;
    bandwidthThrottleEnabled: boolean;
  };
  notifications: {
    backupFailure: boolean;
    clientOffline: boolean;
    rpoBreach: boolean;
    storageLow: boolean;
    alertEmail: string;
  };
}

export interface ToastNotification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'warning' | 'error' | 'success';
  timestamp: string;
}
