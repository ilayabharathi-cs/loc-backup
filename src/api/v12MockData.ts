/**
 * RetroVault V12 Isolated Mock & Test Data Adapter
 * Provides realistic offline development and QA test data when the V12 backend is being developed.
 */

import type {
  CloudCredential,
  CloudCredentialCreate,
  StorageTier,
  StorageTierCreate,
  TierOffloadRequest,
  TierOffloadResponse,
  DRRunbook,
  DRRunbookDetail,
  DRRunbookCreate,
  DRSimulationResult,
  DRExecuteRequest,
  DRRunbookExecution,
  InstantMountSession,
  InstantMountCreateRequest,
  InstantDismountResponse
} from './v12';

let mockCredentials: CloudCredential[] = [
  {
    id: 1,
    credential_id: 'CRED-AWS-EAST-01',
    name: 'AWS Primary East Backup Vault',
    provider_type: 'AWS_S3',
    endpoint_url: null,
    bucket_name: 'retrovault-primary-archive-us-east-1',
    region: 'us-east-1',
    access_key_id: 'AKIAIOSFODNN7EXAMPLE',
    secret_access_key_preview: '[REDACTED]',
    status: 'VALID',
    last_verified_at: '2026-09-24T06:00:00Z',
    created_at: '2026-08-15T12:00:00Z'
  },
  {
    id: 2,
    credential_id: 'CRED-AZURE-WEST-02',
    name: 'Azure Cool Tier Cold Storage',
    provider_type: 'AZURE_BLOB',
    endpoint_url: 'https://retrovaultwest.blob.core.windows.net',
    bucket_name: 'cold-backup-container',
    region: 'westus2',
    access_key_id: 'retrovaultweststorageacct',
    secret_access_key_preview: '[REDACTED]',
    status: 'VALID',
    last_verified_at: '2026-09-24T06:30:00Z',
    created_at: '2026-09-01T09:00:00Z'
  }
];

let mockTiers: StorageTier[] = [
  {
    id: 1,
    tier_id: 'TIER-NVME-HOT',
    name: 'Tier 1 — Ultra NVMe Cache (Local)',
    tier_type: 'HOT',
    provider_type: 'LOCAL',
    credential_id: null,
    local_path: '/backup/repository/nvme_hot',
    object_lock_enabled: false,
    object_lock_mode: null,
    retention_days: 7,
    total_capacity_bytes: 4 * 1024 * 1024 * 1024 * 1024, // 4 TB
    used_capacity_bytes: 2.8 * 1024 * 1024 * 1024 * 1024,
    status: 'ONLINE',
    last_offload_at: '2026-09-24T05:00:00Z',
    created_at: '2026-07-01T00:00:00Z'
  },
  {
    id: 2,
    tier_id: 'TIER-S3-COOL',
    name: 'Tier 2 — AWS S3 Standard-IA Immutable Vault',
    tier_type: 'COOL',
    provider_type: 'AWS_S3',
    credential_id: 'CRED-AWS-EAST-01',
    local_path: null,
    object_lock_enabled: true,
    object_lock_mode: 'COMPLIANCE',
    retention_days: 90,
    total_capacity_bytes: 50 * 1024 * 1024 * 1024 * 1024, // 50 TB
    used_capacity_bytes: 14.2 * 1024 * 1024 * 1024 * 1024,
    status: 'ONLINE',
    last_offload_at: '2026-09-24T04:15:00Z',
    created_at: '2026-08-15T12:05:00Z'
  },
  {
    id: 3,
    tier_id: 'TIER-AZURE-ARCHIVE',
    name: 'Tier 3 — Azure Deep Archive Worm Vault',
    tier_type: 'ARCHIVE',
    provider_type: 'AZURE_BLOB',
    credential_id: 'CRED-AZURE-WEST-02',
    local_path: null,
    object_lock_enabled: true,
    object_lock_mode: 'GOVERNANCE',
    retention_days: 365,
    total_capacity_bytes: 100 * 1024 * 1024 * 1024 * 1024, // 100 TB
    used_capacity_bytes: 38.6 * 1024 * 1024 * 1024 * 1024,
    status: 'ONLINE',
    last_offload_at: '2026-09-23T22:00:00Z',
    created_at: '2026-09-01T09:10:00Z'
  }
];

let mockRunbooks: DRRunbookDetail[] = [
  {
    id: 1,
    runbook_id: 'RBK-CORE-FINANCE-PROD',
    name: 'Mission-Critical Finance Stack Failover',
    description: 'Automated orchestrated failover for SQL Server cluster, ASP.NET API, and React frontend gateway',
    target_environment: 'DR-DATACENTER-WEST-ZONE',
    failover_network: 'VNet-10.200.0.0/16-IsolatedDR',
    status: 'READY',
    step_count: 4,
    estimated_rto_seconds: 420,
    last_simulation_passed: true,
    last_simulation_at: '2026-09-24T02:00:00Z',
    created_at: '2026-09-10T08:00:00Z',
    cycle_detected: false,
    nodes: [
      {
        id: 'node-1',
        workload_id: 'WKLD-MSSQL-PROD',
        workload_name: 'SQL Server Core Financial DB',
        workload_type: 'MSSQL_DATABASE',
        boot_order: 1,
        health_check_type: 'DB_QUERY',
        health_timeout_seconds: 120,
        status: 'READY'
      },
      {
        id: 'node-2',
        workload_id: 'WKLD-REDIS-CACHE',
        workload_name: 'Redis In-Memory Session Cache',
        workload_type: 'GENERIC_APPLICATION',
        boot_order: 2,
        health_check_type: 'PORT_PROBE',
        health_timeout_seconds: 30,
        status: 'READY'
      },
      {
        id: 'node-3',
        workload_id: 'WKLD-FIN-API',
        workload_name: 'Finance Core REST API',
        workload_type: 'WINDOWS_FILESYSTEM',
        boot_order: 3,
        health_check_type: 'HTTP_HEALTH',
        health_timeout_seconds: 60,
        status: 'READY'
      },
      {
        id: 'node-4',
        workload_id: 'WKLD-PAYMENT-GATEWAY',
        workload_name: 'External Settlement Worker',
        workload_type: 'GENERIC_APPLICATION',
        boot_order: 4,
        health_check_type: 'SERVICE_STATUS',
        health_timeout_seconds: 45,
        status: 'READY'
      }
    ],
    edges: [
      { source_id: 'node-1', target_id: 'node-3' },
      { source_id: 'node-2', target_id: 'node-3' },
      { source_id: 'node-3', target_id: 'node-4' }
    ]
  },
  {
    id: 2,
    runbook_id: 'RBK-CIRCULAR-TEST',
    name: 'Legacy Accounting ERP (Blocked by Dependency Cycle)',
    description: 'Test runbook illustrating circular dependency detection guard',
    target_environment: 'DR-SANDBOX-EAST',
    failover_network: 'VNet-Test-Isolated',
    status: 'CYCLE_ERROR',
    step_count: 3,
    estimated_rto_seconds: 600,
    last_simulation_passed: false,
    last_simulation_at: '2026-09-23T18:00:00Z',
    created_at: '2026-09-18T14:30:00Z',
    cycle_detected: true,
    cycle_path: ['SQL Server ERP Database', 'Accounting App Server', 'Data Sync Worker', 'SQL Server ERP Database'],
    nodes: [
      {
        id: 'c-node-1',
        workload_id: 'WKLD-ERP-DB',
        workload_name: 'SQL Server ERP Database',
        workload_type: 'MSSQL_DATABASE',
        boot_order: 1,
        health_check_type: 'DB_QUERY',
        health_timeout_seconds: 120,
        status: 'FAILED'
      },
      {
        id: 'c-node-2',
        workload_id: 'WKLD-ERP-APP',
        workload_name: 'Accounting App Server',
        workload_type: 'GENERIC_APPLICATION',
        boot_order: 2,
        health_check_type: 'HTTP_HEALTH',
        health_timeout_seconds: 60,
        status: 'FAILED'
      },
      {
        id: 'c-node-3',
        workload_id: 'WKLD-ERP-SYNC',
        workload_name: 'Data Sync Worker',
        workload_type: 'GENERIC_APPLICATION',
        boot_order: 3,
        health_check_type: 'SERVICE_STATUS',
        health_timeout_seconds: 60,
        status: 'FAILED'
      }
    ],
    edges: [
      { source_id: 'c-node-1', target_id: 'c-node-2' },
      { source_id: 'c-node-2', target_id: 'c-node-3' },
      { source_id: 'c-node-3', target_id: 'c-node-1' } // Creates circular cycle
    ]
  }
];

let mockMounts: InstantMountSession[] = [
  {
    mount_id: 'MNT-20260924-A101',
    recovery_point_id: 'RP-20260924-0001',
    workload_id: 'WKLD-MSSQL-PROD',
    workload_name: 'SQL Server Core Financial DB',
    workload_type: 'MSSQL_DATABASE',
    target_client_id: 'CLI-WINSRV-01',
    target_hostname: 'SRV-DB-FAILOVER.RETROVAULT.LOCAL',
    mount_point: 'X:\\RetroVaultMount\\FinanceDB',
    mount_mode: 'READ_WRITE_COW',
    status: 'ACTIVE',
    bytes_mounted: 84 * 1024 * 1024 * 1024, // 84 GB
    mounted_at: '2026-09-24T08:15:30Z',
    created_at: '2026-09-24T08:14:00Z'
  },
  {
    mount_id: 'MNT-20260924-B202',
    recovery_point_id: 'RP-20260923-0045',
    workload_id: 'WKLD-FIN-DOCS',
    workload_name: 'Corporate Document Repository',
    workload_type: 'WINDOWS_FILESYSTEM',
    target_client_id: 'CLI-WINSRV-02',
    target_hostname: 'SRV-FILE-02.RETROVAULT.LOCAL',
    mount_point: 'Y:\\AuditBrowse',
    mount_mode: 'READ_ONLY',
    status: 'ACTIVE',
    bytes_mounted: 210 * 1024 * 1024 * 1024,
    mounted_at: '2026-09-24T09:40:12Z',
    created_at: '2026-09-24T09:39:00Z'
  }
];

export const v12MockAdapter = {
  getCloudCredentials: async (): Promise<CloudCredential[]> => {
    return [...mockCredentials];
  },

  createCloudCredential: async (data: CloudCredentialCreate): Promise<CloudCredential> => {
    const newCred: CloudCredential = {
      id: Date.now(),
      credential_id: `CRED-${data.provider_type.replace('_', '-')}-${Math.floor(1000 + Math.random() * 9000)}`,
      name: data.name,
      provider_type: data.provider_type,
      endpoint_url: data.endpoint_url || null,
      bucket_name: data.bucket_name,
      region: data.region,
      access_key_id: data.access_key_id,
      secret_access_key_preview: '[REDACTED]',
      status: 'VALID',
      last_verified_at: new Date().toISOString(),
      created_at: new Date().toISOString()
    };
    mockCredentials.push(newCred);
    return newCred;
  },

  deleteCloudCredential: async (credentialId: string): Promise<{ success: boolean }> => {
    mockCredentials = mockCredentials.filter(c => c.credential_id !== credentialId);
    return { success: true };
  },

  getStorageTiers: async (): Promise<StorageTier[]> => {
    return [...mockTiers];
  },

  getStorageTier: async (tierId: string): Promise<StorageTier> => {
    const tier = mockTiers.find(t => t.tier_id === tierId);
    if (!tier) throw new Error(`Storage tier ${tierId} not found`);
    return tier;
  },

  createStorageTier: async (data: StorageTierCreate): Promise<StorageTier> => {
    const newTier: StorageTier = {
      id: Date.now(),
      tier_id: `TIER-${data.provider_type.replace('_', '-')}-${Math.floor(1000 + Math.random() * 9000)}`,
      name: data.name,
      tier_type: data.tier_type,
      provider_type: data.provider_type,
      credential_id: data.credential_id || null,
      local_path: data.local_path || null,
      object_lock_enabled: data.object_lock_enabled,
      object_lock_mode: data.object_lock_mode || null,
      retention_days: data.retention_days || null,
      total_capacity_bytes: data.total_capacity_bytes || 10 * 1024 * 1024 * 1024 * 1024,
      used_capacity_bytes: 0,
      status: 'ONLINE',
      created_at: new Date().toISOString()
    };
    mockTiers.push(newTier);
    return newTier;
  },

  triggerTierOffload: async (tierId: string, _params?: TierOffloadRequest): Promise<TierOffloadResponse> => {
    return {
      operation_id: `OFL-${Date.now()}`,
      tier_id: tierId,
      status: 'COMPLETED',
      bytes_scanned: 15420000000,
      bytes_offloaded: 8320000000,
      objects_offloaded: 324,
      started_at: new Date(Date.now() - 15000).toISOString(),
      completed_at: new Date().toISOString()
    };
  },

  getDRRunbooks: async (): Promise<DRRunbook[]> => {
    return mockRunbooks.map(({ nodes: _nodes, edges: _edges, cycle_detected: _c, cycle_path: _cp, ...rest }) => rest);
  },

  getDRRunbook: async (runbookId: string): Promise<DRRunbookDetail> => {
    const found = mockRunbooks.find(r => r.runbook_id === runbookId);
    if (!found) throw new Error(`DR Runbook ${runbookId} not found`);
    return found;
  },

  createDRRunbook: async (data: DRRunbookCreate): Promise<DRRunbookDetail> => {
    const newId = `RBK-CUSTOM-${Date.now()}`;
    const newDetail: DRRunbookDetail = {
      id: Date.now(),
      runbook_id: newId,
      name: data.name,
      description: data.description || null,
      target_environment: data.target_environment,
      failover_network: data.failover_network || null,
      status: 'READY',
      step_count: data.nodes.length,
      estimated_rto_seconds: data.nodes.length * 90,
      created_at: new Date().toISOString(),
      cycle_detected: false,
      nodes: data.nodes.map((n, idx) => ({ ...n, id: `node-${idx + 1}`, status: 'READY' })),
      edges: data.edges
    };
    mockRunbooks.push(newDetail);
    return newDetail;
  },

  simulateDRRunbook: async (runbookId: string): Promise<DRSimulationResult> => {
    const runbook = mockRunbooks.find(r => r.runbook_id === runbookId);
    const hasCycle = runbook?.cycle_detected || false;

    return {
      runbook_id: runbookId,
      runbook_name: runbook?.name || 'DR Runbook',
      passed: !hasCycle,
      simulated_rto_seconds: hasCycle ? 0 : 380,
      checks_performed: [
        {
          name: 'Dependency Graph Topological Sort',
          passed: !hasCycle,
          message: hasCycle
            ? 'FATAL: Circular dependency detected in execution graph.'
            : 'DAG verified acyclic. Valid boot order established.',
          duration_ms: 12
        },
        {
          name: 'Target DR Network Isolation & Quota Check',
          passed: true,
          message: 'Target VNet isolated with sufficient IP allocation (240 available).',
          duration_ms: 85
        },
        {
          name: 'Recovery Point CAS Integrity & Immobility Check',
          passed: true,
          message: 'All dependent recovery points verified with cryptographic checksum match.',
          duration_ms: 140
        },
        {
          name: 'VSS / Application Quiesce Consistency State',
          passed: true,
          message: 'Database transaction logs validated for crash-consistent recovery.',
          duration_ms: 60
        }
      ],
      errors: hasCycle
        ? ['Circular dependency detected in execution graph. Runbook cannot be executed.']
        : [],
      evaluated_at: new Date().toISOString()
    };
  },

  executeDRRunbook: async (runbookId: string, params: DRExecuteRequest): Promise<DRRunbookExecution> => {
    const runbook = mockRunbooks.find(r => r.runbook_id === runbookId);
    return {
      execution_id: `EXEC-DR-${Date.now()}`,
      runbook_id: runbookId,
      runbook_name: runbook?.name || 'DR Runbook',
      execution_mode: params.execution_mode,
      status: 'RUNNING',
      current_step_order: 1,
      total_steps: runbook?.nodes.length || 3,
      steps: (runbook?.nodes || []).map((n, idx) => ({
        step_id: `step-${idx + 1}`,
        workload_id: n.workload_id,
        workload_name: n.workload_name,
        step_order: idx + 1,
        action_type: idx === 0 ? 'BOOT' : idx === 1 ? 'RESTORE' : 'HEALTH_CHECK',
        status: idx === 0 ? 'RUNNING' : 'PENDING',
        duration_ms: idx === 0 ? 1240 : 0
      })),
      started_at: new Date().toISOString(),
      initiated_by: 'Administrator'
    };
  },

  getDRExecution: async (executionId: string): Promise<DRRunbookExecution> => {
    return {
      execution_id: executionId,
      runbook_id: 'RBK-CORE-FINANCE-PROD',
      runbook_name: 'Mission-Critical Finance Stack Failover',
      execution_mode: 'TEST_DRILL',
      status: 'SUCCEEDED',
      current_step_order: 4,
      total_steps: 4,
      steps: [
        {
          step_id: 'step-1',
          workload_id: 'WKLD-MSSQL-PROD',
          workload_name: 'SQL Server Core Financial DB',
          step_order: 1,
          action_type: 'BOOT',
          status: 'SUCCEEDED',
          duration_ms: 45200
        },
        {
          step_id: 'step-2',
          workload_id: 'WKLD-REDIS-CACHE',
          workload_name: 'Redis In-Memory Session Cache',
          step_order: 2,
          action_type: 'BOOT',
          status: 'SUCCEEDED',
          duration_ms: 12100
        },
        {
          step_id: 'step-3',
          workload_id: 'WKLD-FIN-API',
          workload_name: 'Finance Core REST API',
          step_order: 3,
          action_type: 'RESTORE',
          status: 'SUCCEEDED',
          duration_ms: 38400
        },
        {
          step_id: 'step-4',
          workload_id: 'WKLD-PAYMENT-GATEWAY',
          workload_name: 'External Settlement Worker',
          step_order: 4,
          action_type: 'HEALTH_CHECK',
          status: 'SUCCEEDED',
          duration_ms: 8500
        }
      ],
      started_at: new Date(Date.now() - 120000).toISOString(),
      completed_at: new Date().toISOString(),
      initiated_by: 'Administrator'
    };
  },

  listDRExecutions: async (): Promise<DRRunbookExecution[]> => {
    return [
      {
        execution_id: 'EXEC-DR-001',
        runbook_id: 'RBK-CORE-FINANCE-PROD',
        runbook_name: 'Mission-Critical Finance Stack Failover',
        execution_mode: 'TEST_DRILL',
        status: 'SUCCEEDED',
        current_step_order: 4,
        total_steps: 4,
        steps: [],
        started_at: new Date(Date.now() - 3600000).toISOString(),
        completed_at: new Date(Date.now() - 3400000).toISOString(),
        initiated_by: 'Administrator'
      }
    ];
  },

  getInstantMounts: async (): Promise<InstantMountSession[]> => {
    return [...mockMounts];
  },

  createInstantMount: async (data: InstantMountCreateRequest): Promise<InstantMountSession> => {
    const newSession: InstantMountSession = {
      mount_id: `MNT-${Date.now()}`,
      recovery_point_id: data.recovery_point_id,
      workload_name: 'Mounted Workload',
      target_client_id: data.target_client_id,
      target_hostname: 'TARGET-HOST.RETROVAULT.LOCAL',
      mount_point: `${data.preferred_drive_letter || 'Z'}:\\RetroVaultLiveMount`,
      mount_mode: data.mount_mode,
      status: 'ACTIVE',
      bytes_mounted: 52 * 1024 * 1024 * 1024,
      mounted_at: new Date().toISOString(),
      created_at: new Date().toISOString()
    };
    mockMounts.push(newSession);
    return newSession;
  },

  dismountInstantMount: async (mountId: string, _force: boolean = false): Promise<InstantDismountResponse> => {
    const session = mockMounts.find(m => m.mount_id === mountId);
    if (session) {
      session.status = 'DISMOUNTED';
      session.dismounted_at = new Date().toISOString();
    }
    return {
      mount_id: mountId,
      status: 'DISMOUNTED',
      dismounted_at: new Date().toISOString(),
      uncommitted_writes_discarded_bytes: 4194304
    };
  }
};
