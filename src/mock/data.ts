import type { Client, BackupJob, BackupPolicy, RecoveryPoint, BackupFileNode, StorageMetrics, ActivityLog, AppSettings } from '../types';

export const INITIAL_CLIENTS: Client[] = [
  {
    id: 'PC-001',
    hostname: 'OFFICE-PC-01',
    user: 'Arun Kumar',
    os: 'Windows 11 Pro 23H2',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.101',
    cpu: 'Intel Core i7-13700 (16 Cores)',
    ram: '32 GB DDR5',
    status: 'ONLINE',
    lastSeen: '12 sec ago',
    lastBackup: '20:12:45',
    rpoSeconds: 42,
    storageConsumedGb: 142.8,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop', '%USERPROFILE%\\Downloads', '%USERPROFILE%\\Pictures'],
    customPaths: ['D:\\Projects\\ClientDeliverables'],
    excludedPaths: ['%TEMP%', '%LOCALAPPDATA%\\Temp', '*.tmp', '*.log']
  },
  {
    id: 'PC-002',
    hostname: 'OFFICE-PC-02',
    user: 'Sarah Jenkins',
    os: 'Windows 11 Enterprise',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.102',
    cpu: 'AMD Ryzen 7 7700X (8 Cores)',
    ram: '32 GB DDR5',
    status: 'ONLINE',
    lastSeen: '18 sec ago',
    lastBackup: '20:11:30',
    rpoSeconds: 48,
    storageConsumedGb: 188.4,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop', '%USERPROFILE%\\Downloads'],
    customPaths: ['D:\\CompanyData\\LegalBriefs'],
    excludedPaths: ['%TEMP%', 'node_modules', '*.iso']
  },
  {
    id: 'PC-003',
    hostname: 'OFFICE-PC-03',
    user: 'David Chen',
    os: 'Windows 10 Pro 22H2',
    agentVersion: '1.3.8',
    ipAddress: '192.168.1.103',
    cpu: 'Intel Core i5-11400 (6 Cores)',
    ram: '16 GB DDR4',
    status: 'OFFLINE',
    lastSeen: '3 hrs ago',
    lastBackup: '17:14:02',
    rpoSeconds: 11420,
    storageConsumedGb: 95.2,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop'],
    customPaths: [],
    excludedPaths: ['%TEMP%', '*.tmp']
  },
  {
    id: 'PC-004',
    hostname: 'FINANCE-WS-01',
    user: 'Elena Rostova',
    os: 'Windows 11 Enterprise',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.104',
    cpu: 'Intel Core i9-13900K (24 Cores)',
    ram: '64 GB DDR5',
    status: 'ONLINE',
    lastSeen: '5 sec ago',
    lastBackup: '20:13:10',
    rpoSeconds: 36,
    storageConsumedGb: 312.6,
    policyId: 'POL-002',
    policyName: 'Finance Sensitive Vault',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop'],
    customPaths: ['E:\\FinanceVault\\2026_Ledgers', 'E:\\Audits'],
    excludedPaths: ['%TEMP%', '*.bak', '*.swp']
  },
  {
    id: 'PC-005',
    hostname: 'DEV-RIG-01',
    user: 'Marcus Vance',
    os: 'Windows 11 Pro 23H2',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.105',
    cpu: 'AMD Ryzen 9 7950X (16 Cores)',
    ram: '64 GB DDR5',
    status: 'BACKING_UP',
    lastSeen: '1 sec ago',
    lastBackup: '20:09:15',
    rpoSeconds: 15,
    storageConsumedGb: 264.1,
    policyId: 'POL-003',
    policyName: 'Developer Workstation',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop'],
    customPaths: ['D:\\Source\\CoreService', 'D:\\Workspace'],
    excludedPaths: ['%TEMP%', 'node_modules', 'target', '.git', '*.cache']
  },
  {
    id: 'PC-006',
    hostname: 'EXEC-LAPTOP-01',
    user: 'Chloe Bennett',
    os: 'Windows 11 Pro 23H2',
    agentVersion: '1.4.1',
    ipAddress: '192.168.1.106',
    cpu: 'Intel Core i7-1360P (12 Cores)',
    ram: '32 GB LPDDR5',
    status: 'ONLINE',
    lastSeen: '24 sec ago',
    lastBackup: '20:05:00',
    rpoSeconds: 520,
    storageConsumedGb: 110.5,
    policyId: 'POL-004',
    policyName: 'Executive Secure Mobile',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop', '%USERPROFILE%\\Pictures'],
    customPaths: ['C:\\Confidential'],
    excludedPaths: ['%TEMP%', '*.mp4', '*.mkv']
  },
  {
    id: 'PC-007',
    hostname: 'DESIGN-MAC-PC',
    user: 'Alex Rivera',
    os: 'Windows 11 Pro 23H2',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.107',
    cpu: 'AMD Ryzen 9 7900X (12 Cores)',
    ram: '64 GB DDR5',
    status: 'ONLINE',
    lastSeen: '14 sec ago',
    lastBackup: '20:10:05',
    rpoSeconds: 88,
    storageConsumedGb: 440.0,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop', '%USERPROFILE%\\Pictures'],
    customPaths: ['D:\\FigmaExports', 'D:\\Renders'],
    excludedPaths: ['%TEMP%', '*.tmp', 'AutodeskCache']
  },
  {
    id: 'PC-008',
    hostname: 'HR-TERMINAL-01',
    user: 'Priya Sharma',
    os: 'Windows 10 Enterprise',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.108',
    cpu: 'Intel Core i5-10400 (6 Cores)',
    ram: '16 GB DDR4',
    status: 'ONLINE',
    lastSeen: '30 sec ago',
    lastBackup: '20:08:22',
    rpoSeconds: 65,
    storageConsumedGb: 78.3,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop'],
    customPaths: ['D:\\HR_Records_Encrypted'],
    excludedPaths: ['%TEMP%']
  },
  {
    id: 'PC-009',
    hostname: 'SALES-OPS-01',
    user: 'Thomas Wright',
    os: 'Windows 11 Pro 22H2',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.109',
    cpu: 'Intel Core i7-12700 (12 Cores)',
    ram: '32 GB DDR4',
    status: 'ONLINE',
    lastSeen: '40 sec ago',
    lastBackup: '20:04:12',
    rpoSeconds: 74,
    storageConsumedGb: 135.2,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop', '%USERPROFILE%\\Downloads'],
    customPaths: ['D:\\CRM_Snapshots'],
    excludedPaths: ['%TEMP%', '*.zip']
  },
  {
    id: 'PC-010',
    hostname: 'LEGAL-STATION-01',
    user: 'Diana Ross',
    os: 'Windows 11 Enterprise',
    agentVersion: '1.4.0',
    ipAddress: '192.168.1.110',
    cpu: 'Intel Core i7-13700 (16 Cores)',
    ram: '32 GB DDR5',
    status: 'WARNING',
    lastSeen: '1 min ago',
    lastBackup: '19:42:10',
    rpoSeconds: 1980,
    storageConsumedGb: 215.4,
    policyId: 'POL-002',
    policyName: 'Finance Sensitive Vault',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop'],
    customPaths: ['E:\\Contracts_2026'],
    excludedPaths: ['%TEMP%', '*.part']
  },
  {
    id: 'PC-011',
    hostname: 'DEV-RIG-02',
    user: 'Kenji Sato',
    os: 'Windows 11 Pro 23H2',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.111',
    cpu: 'AMD Ryzen 9 7950X3D (16 Cores)',
    ram: '64 GB DDR5',
    status: 'ONLINE',
    lastSeen: '10 sec ago',
    lastBackup: '20:13:40',
    rpoSeconds: 22,
    storageConsumedGb: 290.1,
    policyId: 'POL-003',
    policyName: 'Developer Workstation',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop'],
    customPaths: ['D:\\Repositories\\Backend', 'D:\\DockerVolumes'],
    excludedPaths: ['%TEMP%', 'node_modules', '*.o', '*.pdb']
  },
  {
    id: 'PC-012',
    hostname: 'SUPPORT-PC-01',
    user: 'Rachel Green',
    os: 'Windows 10 Pro 22H2',
    agentVersion: '1.3.9',
    ipAddress: '192.168.1.112',
    cpu: 'Intel Core i5-11500 (6 Cores)',
    ram: '16 GB DDR4',
    status: 'ONLINE',
    lastSeen: '55 sec ago',
    lastBackup: '20:02:18',
    rpoSeconds: 98,
    storageConsumedGb: 82.5,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Downloads'],
    customPaths: [],
    excludedPaths: ['%TEMP%']
  },
  {
    id: 'PC-013',
    hostname: 'QA-LAB-HOST-01',
    user: 'Victor Vance',
    os: 'Windows 11 Enterprise',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.113',
    cpu: 'Intel Core i9-14900K (24 Cores)',
    ram: '128 GB DDR5',
    status: 'ONLINE',
    lastSeen: '8 sec ago',
    lastBackup: '20:11:00',
    rpoSeconds: 45,
    storageConsumedGb: 380.7,
    policyId: 'POL-003',
    policyName: 'Developer Workstation',
    universalPaths: ['%USERPROFILE%\\Documents'],
    customPaths: ['D:\\TestArtifacts', 'D:\\QABuilds'],
    excludedPaths: ['%TEMP%', '*.dmp', '*.log']
  },
  {
    id: 'PC-014',
    hostname: 'RECEPTION-PC-01',
    user: 'Mary Watson',
    os: 'Windows 10 Pro 22H2',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.114',
    cpu: 'Intel Core i3-10100 (4 Cores)',
    ram: '8 GB DDR4',
    status: 'ONLINE',
    lastSeen: '1 min ago',
    lastBackup: '19:55:00',
    rpoSeconds: 110,
    storageConsumedGb: 42.1,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents'],
    customPaths: [],
    excludedPaths: ['%TEMP%']
  },
  {
    id: 'PC-015',
    hostname: 'ANALYTICS-SRV-01',
    user: 'Vikram Singh',
    os: 'Windows Server 2022 Datacenter',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.115',
    cpu: 'Dual Intel Xeon Gold 6330',
    ram: '256 GB ECC DDR4',
    status: 'ONLINE',
    lastSeen: '4 sec ago',
    lastBackup: '20:12:00',
    rpoSeconds: 38,
    storageConsumedGb: 512.4,
    policyId: 'POL-002',
    policyName: 'Finance Sensitive Vault',
    universalPaths: ['%USERPROFILE%\\Documents'],
    customPaths: ['F:\\AnalyticsModels', 'F:\\WarehouseExports'],
    excludedPaths: ['%TEMP%', '*.raw']
  },
  {
    id: 'PC-016',
    hostname: 'MARKETING-MAC-01',
    user: 'Jessica Alba',
    os: 'Windows 11 Pro 23H2',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.116',
    cpu: 'AMD Ryzen 7 7800X3D (8 Cores)',
    ram: '32 GB DDR5',
    status: 'ONLINE',
    lastSeen: '15 sec ago',
    lastBackup: '20:07:30',
    rpoSeconds: 58,
    storageConsumedGb: 195.0,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop', '%USERPROFILE%\\Pictures'],
    customPaths: ['D:\\VideoProjects'],
    excludedPaths: ['%TEMP%', '*.prproj.autosave']
  },
  {
    id: 'PC-017',
    hostname: 'WAREHOUSE-PC-01',
    user: 'Bill Goldberg',
    os: 'Windows 10 Enterprise LTSC',
    agentVersion: '1.3.5',
    ipAddress: '192.168.1.117',
    cpu: 'Intel Celeron G5905 (2 Cores)',
    ram: '8 GB DDR4',
    status: 'OFFLINE',
    lastSeen: '2 days ago',
    lastBackup: '20 Sep 14:10',
    rpoSeconds: 172800,
    storageConsumedGb: 28.5,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents'],
    customPaths: ['C:\\Scans'],
    excludedPaths: ['%TEMP%']
  },
  {
    id: 'PC-018',
    hostname: 'AUDIT-WS-01',
    user: 'Nathan Drake',
    os: 'Windows 11 Pro 23H2',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.118',
    cpu: 'Intel Core i7-13700 (16 Cores)',
    ram: '32 GB DDR5',
    status: 'ONLINE',
    lastSeen: '22 sec ago',
    lastBackup: '20:10:45',
    rpoSeconds: 41,
    storageConsumedGb: 168.2,
    policyId: 'POL-002',
    policyName: 'Finance Sensitive Vault',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop'],
    customPaths: ['D:\\AuditReports_Confidential'],
    excludedPaths: ['%TEMP%']
  },
  {
    id: 'PC-019',
    hostname: 'FIELD-ENGINEER-01',
    user: 'Samuel Fisher',
    os: 'Windows 11 Pro 23H2',
    agentVersion: '1.4.1',
    ipAddress: '192.168.1.119',
    cpu: 'Intel Core i7-1365U (10 Cores)',
    ram: '16 GB LPDDR5',
    status: 'ONLINE',
    lastSeen: '35 sec ago',
    lastBackup: '20:06:12',
    rpoSeconds: 76,
    storageConsumedGb: 112.9,
    policyId: 'POL-004',
    policyName: 'Executive Secure Mobile',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop'],
    customPaths: ['C:\\TelemetryLogs'],
    excludedPaths: ['%TEMP%']
  },
  {
    id: 'PC-020',
    hostname: 'ARCHIVE-DISPATCH-01',
    user: 'George Costanza',
    os: 'Windows 10 Pro 22H2',
    agentVersion: '1.4.2',
    ipAddress: '192.168.1.120',
    cpu: 'Intel Core i5-10500 (6 Cores)',
    ram: '16 GB DDR4',
    status: 'ONLINE',
    lastSeen: '19 sec ago',
    lastBackup: '20:11:55',
    rpoSeconds: 49,
    storageConsumedGb: 88.0,
    policyId: 'POL-001',
    policyName: 'Windows User Data',
    universalPaths: ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop', '%USERPROFILE%\\Downloads'],
    customPaths: ['D:\\InvoicesArchive'],
    excludedPaths: ['%TEMP%']
  }
];

export const INITIAL_JOBS: BackupJob[] = [
  {
    id: 'JOB-9401',
    clientId: 'PC-005',
    clientHostname: 'DEV-RIG-01',
    policyName: 'Developer Workstation',
    backupType: 'Incremental',
    source: '%USERPROFILE%\\Documents, D:\\Source\\CoreService',
    started: '20:14:02',
    completed: null,
    duration: '00:01:23',
    dataProcessedMb: 1420.5,
    status: 'RUNNING',
    progressPercent: 68,
    changeDetection: 'USN Journal (NTFS)',
    transferSpeedMbps: 88.4
  },
  {
    id: 'JOB-9400',
    clientId: 'PC-001',
    clientHostname: 'OFFICE-PC-01',
    policyName: 'Windows User Data',
    backupType: 'Incremental',
    source: '%USERPROFILE%\\Documents, Desktop, Downloads',
    started: '20:10:00',
    completed: '20:12:45',
    duration: '00:02:45',
    dataProcessedMb: 412.3,
    status: 'SUCCESS',
    progressPercent: 100,
    changeDetection: 'USN Journal (NTFS)',
    transferSpeedMbps: 94.2
  },
  {
    id: 'JOB-9399',
    clientId: 'PC-002',
    clientHostname: 'OFFICE-PC-02',
    policyName: 'Windows User Data',
    backupType: 'Incremental',
    source: '%USERPROFILE%\\Documents, D:\\CompanyData',
    started: '20:08:15',
    completed: '20:11:30',
    duration: '00:03:15',
    dataProcessedMb: 618.0,
    status: 'SUCCESS',
    progressPercent: 100,
    changeDetection: 'USN Journal (NTFS)',
    transferSpeedMbps: 81.6
  },
  {
    id: 'JOB-9398',
    clientId: 'PC-003',
    clientHostname: 'OFFICE-PC-03',
    policyName: 'Windows User Data',
    backupType: 'Incremental',
    source: '%USERPROFILE%\\Documents',
    started: '20:05:00',
    completed: '20:05:40',
    duration: '00:00:40',
    dataProcessedMb: 12.0,
    status: 'FAILED',
    progressPercent: 18,
    errorMessage: 'VSS Error: Shadow copy creation timed out (0x80042306)',
    changeDetection: 'USN Journal (NTFS)',
    transferSpeedMbps: 0.0
  },
  {
    id: 'JOB-9397',
    clientId: 'PC-004',
    clientHostname: 'FINANCE-WS-01',
    policyName: 'Finance Sensitive Vault',
    backupType: 'Incremental',
    source: 'E:\\FinanceVault\\2026_Ledgers',
    started: '20:02:00',
    completed: '20:04:15',
    duration: '00:02:15',
    dataProcessedMb: 890.4,
    status: 'SUCCESS',
    progressPercent: 100,
    changeDetection: 'USN Journal (NTFS)',
    transferSpeedMbps: 99.1
  },
  {
    id: 'JOB-9396',
    clientId: 'PC-011',
    clientHostname: 'DEV-RIG-02',
    policyName: 'Developer Workstation',
    backupType: 'Full',
    source: '%USERPROFILE%\\Documents, D:\\Repositories',
    started: '19:40:00',
    completed: '19:58:30',
    duration: '00:18:30',
    dataProcessedMb: 24500.0,
    status: 'SUCCESS',
    progressPercent: 100,
    changeDetection: 'Full Catalog Traversal',
    transferSpeedMbps: 120.5
  },
  {
    id: 'JOB-9395',
    clientId: 'PC-010',
    clientHostname: 'LEGAL-STATION-01',
    policyName: 'Finance Sensitive Vault',
    backupType: 'Incremental',
    source: 'E:\\Contracts_2026',
    started: '19:35:00',
    completed: null,
    duration: '00:07:10',
    dataProcessedMb: 350.2,
    status: 'PAUSED',
    progressPercent: 45,
    changeDetection: 'USN Journal (NTFS)',
    transferSpeedMbps: 0.0
  },
  {
    id: 'JOB-9394',
    clientId: 'PC-007',
    clientHostname: 'DESIGN-MAC-PC',
    policyName: 'Windows User Data',
    backupType: 'Incremental',
    source: 'D:\\FigmaExports, D:\\Renders',
    started: '19:20:00',
    completed: '19:28:40',
    duration: '00:08:40',
    dataProcessedMb: 8400.0,
    status: 'SUCCESS',
    progressPercent: 100,
    changeDetection: 'USN Journal (NTFS)',
    transferSpeedMbps: 95.0
  }
];

export const INITIAL_POLICIES: BackupPolicy[] = [
  {
    id: 'POL-001',
    name: 'Windows User Data',
    description: 'Standard enterprise workstation policy safeguarding essential user directories',
    protectedFolders: [
      { path: '%USERPROFILE%\\Documents', isUniversal: true, enabled: true },
      { path: '%USERPROFILE%\\Desktop', isUniversal: true, enabled: true },
      { path: '%USERPROFILE%\\Downloads', isUniversal: true, enabled: true },
      { path: '%USERPROFILE%\\Pictures', isUniversal: true, enabled: true }
    ],
    customFolders: ['D:\\Projects', 'D:\\CompanyData'],
    excludedPaths: ['%TEMP%', '%LOCALAPPDATA%\\Temp', 'C:\\Windows\\Temp', '*.tmp', '*.log', '*.cache'],
    backupType: 'Incremental',
    changeDetection: 'USN Journal',
    rpoTargetSeconds: 120, // 2 minutes
    compressionEnabled: true,
    encryptionEnabled: true,
    cpuLimitPercent: 10,
    networkLimitMbps: 100,
    retentionDays: 7,
    appliedClientsCount: 12
  },
  {
    id: 'POL-002',
    name: 'Finance Sensitive Vault',
    description: 'High-frequency encrypted backup with strict RPO and immutable retention',
    protectedFolders: [
      { path: '%USERPROFILE%\\Documents', isUniversal: true, enabled: true },
      { path: '%USERPROFILE%\\Desktop', isUniversal: true, enabled: true }
    ],
    customFolders: ['E:\\FinanceVault', 'E:\\Audits', 'D:\\AuditReports_Confidential'],
    excludedPaths: ['%TEMP%', '*.bak', '*.swp', '*.tmp'],
    backupType: 'Incremental',
    changeDetection: 'USN Journal',
    rpoTargetSeconds: 60, // 1 minute
    compressionEnabled: true,
    encryptionEnabled: true,
    cpuLimitPercent: 15,
    networkLimitMbps: 150,
    retentionDays: 30,
    appliedClientsCount: 4
  },
  {
    id: 'POL-003',
    name: 'Developer Workstation',
    description: 'Code repository backup with aggressive build-artifact exclusions',
    protectedFolders: [
      { path: '%USERPROFILE%\\Documents', isUniversal: true, enabled: true },
      { path: '%USERPROFILE%\\Desktop', isUniversal: true, enabled: false }
    ],
    customFolders: ['D:\\Source', 'D:\\Workspace', 'D:\\Repositories'],
    excludedPaths: ['%TEMP%', 'node_modules', 'target', '.git', '*.pdb', '*.obj', '*.o', '*.dmp'],
    backupType: 'Incremental',
    changeDetection: 'USN Journal',
    rpoTargetSeconds: 120,
    compressionEnabled: true,
    encryptionEnabled: true,
    cpuLimitPercent: 20,
    networkLimitMbps: 200,
    retentionDays: 14,
    appliedClientsCount: 3
  },
  {
    id: 'POL-004',
    name: 'Executive Secure Mobile',
    description: 'Low-bandwidth adaptive backup for roaming laptops and field teams',
    protectedFolders: [
      { path: '%USERPROFILE%\\Documents', isUniversal: true, enabled: true },
      { path: '%USERPROFILE%\\Desktop', isUniversal: true, enabled: true },
      { path: '%USERPROFILE%\\Pictures', isUniversal: true, enabled: true }
    ],
    customFolders: ['C:\\Confidential'],
    excludedPaths: ['%TEMP%', '*.mp4', '*.mkv', '*.iso', '*.vmdk'],
    backupType: 'Incremental',
    changeDetection: 'USN Journal',
    rpoTargetSeconds: 300, // 5 minutes
    compressionEnabled: true,
    encryptionEnabled: true,
    cpuLimitPercent: 5,
    networkLimitMbps: 50,
    retentionDays: 14,
    appliedClientsCount: 2
  }
];

export const INITIAL_STORAGE: StorageMetrics = {
  repositoryPath: 'D:\\BackupRepository',
  totalTb: 10.0,
  usedTb: 2.4,
  freeTb: 7.6,
  diskHealth: 'OPTIMAL (S.M.A.R.T. Verified)',
  backupObjectsCount: 142850,
  recoveryPointsCount: 4892,
  dedupRatio: 2.8,
  compressionRatio: 1.7,
  lastVerification: '22 Sep 2026 18:00:00 (PASSED)'
};

export const MOCK_RECOVERY_POINTS: Record<string, RecoveryPoint[]> = {
  'PC-001': [
    { id: 'RP-01-01', clientId: 'PC-001', timestamp: '22 Sep 2026 20:12:45', type: 'Incremental', sizeMb: 412.3, fileCount: 42, rootPath: 'C:\\' },
    { id: 'RP-01-02', clientId: 'PC-001', timestamp: '22 Sep 2026 20:10:12', type: 'Incremental', sizeMb: 85.0, fileCount: 14, rootPath: 'C:\\' },
    { id: 'RP-01-03', clientId: 'PC-001', timestamp: '22 Sep 2026 20:08:00', type: 'Incremental', sizeMb: 120.4, fileCount: 19, rootPath: 'C:\\' },
    { id: 'RP-01-04', clientId: 'PC-001', timestamp: '22 Sep 2026 20:06:22', type: 'Incremental', sizeMb: 64.2, fileCount: 8, rootPath: 'C:\\' },
    { id: 'RP-01-05', clientId: 'PC-001', timestamp: '22 Sep 2026 12:00:00', type: 'Full', sizeMb: 142000.0, fileCount: 38240, rootPath: 'C:\\' }
  ],
  'PC-002': [
    { id: 'RP-02-01', clientId: 'PC-002', timestamp: '22 Sep 2026 20:11:30', type: 'Incremental', sizeMb: 618.0, fileCount: 55, rootPath: 'C:\\' },
    { id: 'RP-02-02', clientId: 'PC-002', timestamp: '22 Sep 2026 20:05:00', type: 'Incremental', sizeMb: 190.2, fileCount: 22, rootPath: 'C:\\' }
  ]
};

export const MOCK_FILE_TREE: BackupFileNode = {
  id: 'node-c',
  name: 'C:\\',
  path: 'C:\\',
  isDirectory: true,
  modified: '22 Sep 2026 20:12',
  children: [
    {
      id: 'node-users',
      name: 'Users',
      path: 'C:\\Users',
      isDirectory: true,
      modified: '22 Sep 2026 20:12',
      children: [
        {
          id: 'node-arun',
          name: 'Arun',
          path: 'C:\\Users\\Arun',
          isDirectory: true,
          modified: '22 Sep 2026 20:12',
          children: [
            {
              id: 'node-docs',
              name: 'Documents',
              path: 'C:\\Users\\Arun\\Documents',
              isDirectory: true,
              modified: '22 Sep 2026 20:12',
              children: [
                { id: 'f1', name: 'Q3_Enterprise_Architecture.docx', path: 'C:\\Users\\Arun\\Documents\\Q3_Enterprise_Architecture.docx', isDirectory: false, sizeBytes: 2457600, modified: '22 Sep 2026 19:40' },
                { id: 'f2', name: 'Vendor_Contracts_Master.xlsx', path: 'C:\\Users\\Arun\\Documents\\Vendor_Contracts_Master.xlsx', isDirectory: false, sizeBytes: 1843200, modified: '22 Sep 2026 20:05' },
                { id: 'f3', name: 'Disaster_Recovery_SOP_v2.pdf', path: 'C:\\Users\\Arun\\Documents\\Disaster_Recovery_SOP_v2.pdf', isDirectory: false, sizeBytes: 5242880, modified: '22 Sep 2026 18:15' }
              ]
            },
            {
              id: 'node-desk',
              name: 'Desktop',
              path: 'C:\\Users\\Arun\\Desktop',
              isDirectory: true,
              modified: '22 Sep 2026 20:08',
              children: [
                { id: 'f4', name: 'Urgent_Meeting_Notes.txt', path: 'C:\\Users\\Arun\\Desktop\\Urgent_Meeting_Notes.txt', isDirectory: false, sizeBytes: 4096, modified: '22 Sep 2026 20:08' },
                { id: 'f5', name: 'Network_Topology_2026.vsdx', path: 'C:\\Users\\Arun\\Desktop\\Network_Topology_2026.vsdx', isDirectory: false, sizeBytes: 3145728, modified: '22 Sep 2026 14:20' }
              ]
            },
            {
              id: 'node-down',
              name: 'Downloads',
              path: 'C:\\Users\\Arun\\Downloads',
              isDirectory: true,
              modified: '22 Sep 2026 19:50',
              children: [
                { id: 'f6', name: 'Windows11_Security_Patch_KB5039211.msu', path: 'C:\\Users\\Arun\\Downloads\\Windows11_Security_Patch_KB5039211.msu', isDirectory: false, sizeBytes: 268435456, modified: '22 Sep 2026 17:30' },
                { id: 'f7', name: 'OpenSSL_Cert_Chain_2026.pem', path: 'C:\\Users\\Arun\\Downloads\\OpenSSL_Cert_Chain_2026.pem', isDirectory: false, sizeBytes: 8192, modified: '22 Sep 2026 19:50' }
              ]
            },
            {
              id: 'node-pic',
              name: 'Pictures',
              path: 'C:\\Users\\Arun\\Pictures',
              isDirectory: true,
              modified: '22 Sep 2026 15:10',
              children: [
                { id: 'f8', name: 'ServerRack_Datacenter_Bay4.png', path: 'C:\\Users\\Arun\\Pictures\\ServerRack_Datacenter_Bay4.png', isDirectory: false, sizeBytes: 4194304, modified: '22 Sep 2026 15:10' }
              ]
            }
          ]
        }
      ]
    },
    {
      id: 'node-d',
      name: 'D:\\Projects',
      path: 'D:\\Projects',
      isDirectory: true,
      modified: '22 Sep 2026 19:30',
      children: [
        {
          id: 'node-cdeliv',
          name: 'ClientDeliverables',
          path: 'D:\\Projects\\ClientDeliverables',
          isDirectory: true,
          modified: '22 Sep 2026 19:30',
          children: [
            { id: 'f9', name: 'Release_Manifest_v4.4.json', path: 'D:\\Projects\\ClientDeliverables\\Release_Manifest_v4.4.json', isDirectory: false, sizeBytes: 28400, modified: '22 Sep 2026 19:30' },
            { id: 'f10', name: 'Database_Schema_Migration.sql', path: 'D:\\Projects\\ClientDeliverables\\Database_Schema_Migration.sql', isDirectory: false, sizeBytes: 142000, modified: '22 Sep 2026 19:25' }
          ]
        }
      ]
    }
  ]
};

export const INITIAL_LOGS: ActivityLog[] = [
  {
    id: 'LOG-1048',
    time: '20:14:20',
    clientId: 'PC-001',
    event: 'BACKUP',
    severity: 'INFO',
    message: 'Incremental backup completed successfully (412.3 MB processed in 00:02:45)',
    details: 'USN Journal parsed 341 file records. Changed files: 42. Deduplication saved 280 MB.'
  },
  {
    id: 'LOG-1047',
    time: '20:14:12',
    clientId: 'PC-003',
    event: 'AGENT',
    severity: 'ERROR',
    message: 'Connection timeout: Client agent unresponsive on 192.168.1.103:4882',
    details: 'Heartbeat ping failed 3 consecutive times. Marked status as OFFLINE. RPO SLA breached.'
  },
  {
    id: 'LOG-1046',
    time: '20:13:45',
    clientId: 'PC-002',
    event: 'RESTORE',
    severity: 'INFO',
    message: 'Restore completed for LegalBriefs\\Contract_Final.pdf to original location',
    details: 'Restored from Recovery Point RP-02-01. File hash SHA-256 verified.'
  },
  {
    id: 'LOG-1045',
    time: '20:12:00',
    clientId: 'PC-005',
    event: 'BACKUP',
    severity: 'INFO',
    message: 'Job JOB-9401 started: Incremental backup for DEV-RIG-01',
    details: 'Volume Shadow Copy (VSS) snapshot created on volume C:\\, D:\\.'
  },
  {
    id: 'LOG-1044',
    time: '20:10:05',
    clientId: 'PC-010',
    event: 'SECURITY',
    severity: 'WARNING',
    message: 'RPO Target warning: Client RPO reached 33 minutes (Policy threshold 1 min)',
    details: 'Backup job paused due to throttled network window.'
  },
  {
    id: 'LOG-1043',
    time: '20:05:40',
    clientId: 'PC-003',
    event: 'BACKUP',
    severity: 'ERROR',
    message: 'Backup failed: VSS Error: Shadow copy creation timed out (0x80042306)',
    details: 'Microsoft Software Shadow Copy Provider timed out while holding writes.'
  },
  {
    id: 'LOG-1042',
    time: '20:00:15',
    clientId: 'PC-015',
    event: 'SYSTEM',
    severity: 'INFO',
    message: 'Repository integrity check verified: 142,850 objects clean, 0 corruptions',
    details: 'D:\\BackupRepository block hashes validated with SHA-256 integrity scrub.'
  },
  {
    id: 'LOG-1041',
    time: '19:45:30',
    clientId: 'PC-004',
    event: 'POLICY',
    severity: 'INFO',
    message: 'Policy "Finance Sensitive Vault" applied to client FINANCE-WS-01',
    details: 'Universal path expansion: %USERPROFILE%\\Documents mapped to C:\\Users\\Elena\\Documents.'
  },
  {
    id: 'LOG-1040',
    time: '19:30:00',
    clientId: 'SYSTEM',
    event: 'SYSTEM',
    severity: 'INFO',
    message: 'Automatic dedup compaction finished: 14.8 GB space reclaimed',
    details: 'Deduplication ratio optimized to 2.8:1.'
  }
];

export const INITIAL_SETTINGS: AppSettings = {
  server: {
    serverName: 'RETROVAULT-PRIMARY-01',
    serverIp: '192.168.1.10',
    apiPort: 8443,
    repositoryPath: 'D:\\BackupRepository'
  },
  security: {
    authType: 'Windows Kerberos / Active Directory',
    tlsStatus: true,
    encryptionAlgorithm: 'AES-256-GCM',
    rbacEnabled: true,
    sessionTimeoutMinutes: 60
  },
  agent: {
    minimumAgentVersion: '1.4.0',
    heartbeatIntervalSeconds: 15,
    retryCount: 3,
    bandwidthThrottleEnabled: true
  },
  notifications: {
    backupFailure: true,
    clientOffline: true,
    rpoBreach: true,
    storageLow: true,
    alertEmail: 'admin-backups@company.corp'
  }
};
