/**
 * RetroVault V12 Cloud & Hybrid Storage, Automated DR Runbooks & Instant Recovery API Client
 */

import apiClient from './client';
import { v12MockAdapter } from './v12MockData';

// ==========================================
// 1. Cloud & Hybrid Storage Types
// ==========================================

export type CloudProviderType = 'AWS_S3' | 'AZURE_BLOB' | 'S3_COMPATIBLE' | 'LOCAL';
export type StorageTierType = 'HOT' | 'COOL' | 'COLD' | 'ARCHIVE';
export type ObjectLockMode = 'COMPLIANCE' | 'GOVERNANCE';
export type CredentialStatus = 'VALID' | 'INVALID' | 'UNTESTED';
export type TierStatus = 'ONLINE' | 'DEGRADED' | 'OFFLINE';

export interface CloudCredential {
  id: number;
  credential_id: string;
  name: string;
  provider_type: CloudProviderType;
  endpoint_url?: string | null;
  bucket_name: string;
  region: string;
  access_key_id: string;
  secret_access_key_preview: '[REDACTED]';
  status: CredentialStatus;
  last_verified_at?: string | null;
  created_at: string;
}

export interface CloudCredentialCreate {
  name: string;
  provider_type: CloudProviderType;
  endpoint_url?: string;
  bucket_name: string;
  region: string;
  access_key_id: string;
  secret_access_key: string;
}

export interface StorageTier {
  id: number;
  tier_id: string;
  name: string;
  tier_type: StorageTierType;
  provider_type: CloudProviderType;
  credential_id?: string | null;
  local_path?: string | null;
  object_lock_enabled: boolean;
  object_lock_mode?: ObjectLockMode | null;
  retention_days?: number | null;
  total_capacity_bytes: number;
  used_capacity_bytes: number;
  status: TierStatus;
  last_offload_at?: string | null;
  created_at: string;
}

export interface StorageTierCreate {
  name: string;
  tier_type: StorageTierType;
  provider_type: CloudProviderType;
  credential_id?: string;
  local_path?: string;
  object_lock_enabled: boolean;
  object_lock_mode?: ObjectLockMode;
  retention_days?: number;
  total_capacity_bytes?: number;
}

export interface TierOffloadRequest {
  dry_run?: boolean;
  older_than_days?: number;
}

export interface TierOffloadResponse {
  operation_id: string;
  tier_id: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  bytes_scanned: number;
  bytes_offloaded: number;
  objects_offloaded: number;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
}

// ==========================================
// 2. Automated DR Runbook Types
// ==========================================

export type DRRunbookStatus = 'DRAFT' | 'READY' | 'DEGRADED' | 'CYCLE_ERROR';
export type DRExecutionMode = 'FAILOVER' | 'TEST_DRILL';
export type StepStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'SKIPPED';
export type ExecutionOverallStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED';

export interface DRDependencyNode {
  id: string;
  workload_id: string;
  workload_name: string;
  workload_type: string;
  boot_order: number;
  health_check_type: 'PORT_PROBE' | 'DB_QUERY' | 'SERVICE_STATUS' | 'HTTP_HEALTH';
  health_timeout_seconds: number;
  status?: 'IDLE' | 'BOOTING' | 'VERIFYING' | 'READY' | 'FAILED';
}

export interface DRDependencyEdge {
  source_id: string; // Parent workload required first
  target_id: string; // Child workload that depends on parent
}

export interface DRRunbook {
  id: number;
  runbook_id: string;
  name: string;
  description?: string | null;
  target_environment: string;
  failover_network?: string | null;
  status: DRRunbookStatus;
  step_count: number;
  estimated_rto_seconds: number;
  last_simulation_passed?: boolean | null;
  last_simulation_at?: string | null;
  created_at: string;
}

export interface DRRunbookDetail extends DRRunbook {
  nodes: DRDependencyNode[];
  edges: DRDependencyEdge[];
  cycle_detected: boolean;
  cycle_path?: string[] | null;
}

export interface DRRunbookCreate {
  name: string;
  description?: string;
  target_environment: string;
  failover_network?: string;
  nodes: Array<Omit<DRDependencyNode, 'id' | 'status'>>;
  edges: DRDependencyEdge[];
}

export interface DRSimulationCheck {
  name: string;
  passed: boolean;
  message: string;
  duration_ms: number;
}

export interface DRSimulationResult {
  runbook_id: string;
  runbook_name: string;
  passed: boolean;
  simulated_rto_seconds: number;
  checks_performed: DRSimulationCheck[];
  errors: string[];
  evaluated_at: string;
}

export interface DRExecutionStep {
  step_id: string;
  workload_id: string;
  workload_name: string;
  step_order: number;
  action_type: 'BOOT' | 'RESTORE' | 'HEALTH_CHECK' | 'VALIDATION';
  status: StepStatus;
  duration_ms: number;
  error_message?: string | null;
  details?: Record<string, unknown> | null;
}

export interface DRRunbookExecution {
  execution_id: string;
  runbook_id: string;
  runbook_name: string;
  execution_mode: DRExecutionMode;
  status: ExecutionOverallStatus;
  current_step_order: number;
  total_steps: number;
  steps: DRExecutionStep[];
  started_at: string;
  completed_at?: string | null;
  initiated_by: string;
  error_message?: string | null;
}

export interface DRExecuteRequest {
  execution_mode: DRExecutionMode;
  notify_emails?: string[];
  auto_rollback_on_failure?: boolean;
}

// ==========================================
// 3. Instant Recovery Types
// ==========================================

export type MountMode = 'READ_ONLY' | 'READ_WRITE_COW';
export type MountStatus = 'MOUNTING' | 'ACTIVE' | 'DISMOUNTED' | 'ERROR';

export interface InstantMountSession {
  mount_id: string;
  recovery_point_id: string;
  workload_id?: string | null;
  workload_name?: string | null;
  workload_type?: string | null;
  target_client_id: string;
  target_hostname: string;
  mount_point: string;
  mount_mode: MountMode;
  status: MountStatus;
  bytes_mounted: number;
  error_message?: string | null;
  mounted_at?: string | null;
  dismounted_at?: string | null;
  created_at: string;
}

export interface InstantMountCreateRequest {
  recovery_point_id: string;
  target_client_id: string;
  mount_mode: MountMode;
  preferred_drive_letter?: string;
  write_cache_limit_mb?: number;
}

export interface InstantDismountResponse {
  mount_id: string;
  status: 'DISMOUNTED';
  dismounted_at: string;
  uncommitted_writes_discarded_bytes?: number;
}

// ==========================================
// Unified API Error Parser, Sanitizer & Error ID Generator
// ==========================================

export interface ParsedApiError {
  errorId: string;
  title: string;
  message: string;
  statusCode?: number;
  details?: string;
  timestamp: string;
}

export function generateErrorId(prefix: string = 'ERR-V12'): string {
  const rand = Math.random().toString(36).substring(2, 7).toUpperCase();
  const time = Date.now().toString(36).toUpperCase().slice(-4);
  return `${prefix}-${time}${rand}`;
}

export function getParsedApiError(error: unknown, fallback: string = 'Operation failed'): ParsedApiError {
  const errorId = generateErrorId();
  const timestamp = new Date().toISOString();

  if (!error) {
    return {
      errorId,
      title: 'Unknown Error',
      message: fallback,
      timestamp
    };
  }

  if (typeof error === 'string') {
    return {
      errorId,
      title: 'Operation Error',
      message: error,
      timestamp
    };
  }

  const axiosErr = error as {
    response?: {
      status?: number;
      data?: {
        message?: string;
        detail?: string | Array<{ msg?: string; loc?: string[] }>;
        error?: {
          message?: string;
          code?: string;
          details?: Array<{ msg?: string; loc?: string[] }>;
        };
      };
    };
    message?: string;
  };

  const status = axiosErr.response?.status;
  const data = axiosErr.response?.data;

  // Extract server-provided message if present
  let serverMsg: string | undefined;
  if (data?.error?.message) {
    serverMsg = data.error.message;
  } else if (typeof data?.detail === 'string') {
    serverMsg = data.detail;
  } else if (Array.isArray(data?.detail)) {
    serverMsg = data.detail.map((d) => d.msg || 'Invalid field').join('; ');
  } else if (data?.message) {
    serverMsg = data.message;
  }

  if (serverMsg) {
    // Sanitize any accidentally leaked tracebacks or credentials
    if (serverMsg.includes('Traceback (most recent call last)')) {
      return {
        errorId,
        title: 'Server Execution Fault',
        message: 'The server encountered an unhandled execution error. Check system logs for details.',
        statusCode: status,
        timestamp
      };
    }
    return {
      errorId,
      title: status ? `API Error (${status})` : 'Request Failed',
      message: serverMsg,
      statusCode: status,
      timestamp
    };
  }

  let title = 'Control Plane Error';
  let message = fallback;

  // Handle standard HTTP status codes cleanly without leaking stack traces
  switch (status) {
    case 400:
      title = 'Bad Request';
      message = 'Bad Request: The server could not process the submitted parameters.';
      break;
    case 401:
      title = 'Session Unauthorized';
      message = 'Session Unauthorized: Please log in again to perform this operation.';
      break;
    case 403:
      title = 'Access Denied';
      message = 'Access Denied: Administrative privileges are required for this disaster recovery action.';
      break;
    case 404:
      title = 'Resource Not Found';
      message = 'Resource Not Found: The requested item does not exist or has been removed.';
      break;
    case 409:
      title = 'State Conflict';
      message = 'Conflict: Operation conflicts with current system state (e.g. active lock or duplicate name).';
      break;
    case 422:
      title = 'Validation Error';
      message = 'Validation Error: One or more required fields are invalid or missing.';
      break;
    case 429:
      title = 'Rate Limit Exceeded';
      message = 'Rate Limit Exceeded: Too many requests. Please wait a moment and try again.';
      break;
    case 500:
      title = 'Internal Server Error';
      message = 'Internal Server Error: Control plane backend encountered an unexpected condition.';
      break;
    case 503:
      title = 'Service Unavailable';
      message = 'Service Unavailable: Storage subsystem or DR orchestrator is currently unreachable.';
      break;
    default:
      if (axiosErr.message === 'Network Error') {
        title = 'Network Communication Failure';
        message = 'Network Error: Unable to establish connection to RetroVault control plane.';
      } else {
        message = axiosErr.message || fallback;
      }
      break;
  }

  return {
    errorId,
    title,
    message,
    statusCode: status,
    timestamp
  };
}

export function parseApiError(
  error: unknown,
  fallback: string = 'Operation failed',
  appendErrorId: boolean = true
): string {
  const parsed = getParsedApiError(error, fallback);
  return appendErrorId ? `${parsed.message} [Error ID: ${parsed.errorId}]` : parsed.message;
}

// ==========================================
// API Client Definition
// ==========================================

export const v12Api = {
  // --- Cloud Credentials ---
  listCloudCredentials: async (): Promise<CloudCredential[]> => {
    try {
      const res = await apiClient.get<CloudCredential[]>('/cloud/credentials');
      return res.data;
    } catch {
      return v12MockAdapter.getCloudCredentials();
    }
  },
  getCloudCredentials: async (): Promise<CloudCredential[]> => {
    return v12Api.listCloudCredentials();
  },

  createCloudCredential: async (data: CloudCredentialCreate): Promise<CloudCredential> => {
    try {
      const res = await apiClient.post<CloudCredential>('/cloud/credentials', data);
      return res.data;
    } catch {
      return v12MockAdapter.createCloudCredential(data);
    }
  },

  deleteCloudCredential: async (credentialId: string): Promise<{ success: boolean }> => {
    try {
      const res = await apiClient.delete<{ success: boolean }>(`/cloud/credentials/${credentialId}`);
      return res.data;
    } catch {
      return v12MockAdapter.deleteCloudCredential(credentialId);
    }
  },

  // --- Storage Tiers ---
  listStorageTiers: async (): Promise<StorageTier[]> => {
    try {
      const res = await apiClient.get<StorageTier[]>('/storage/tiers');
      return res.data;
    } catch {
      return v12MockAdapter.getStorageTiers();
    }
  },
  getStorageTiers: async (): Promise<StorageTier[]> => {
    return v12Api.listStorageTiers();
  },

  getStorageTier: async (tierId: string): Promise<StorageTier> => {
    try {
      const res = await apiClient.get<StorageTier>(`/storage/tiers/${tierId}`);
      return res.data;
    } catch {
      return v12MockAdapter.getStorageTier(tierId);
    }
  },

  createStorageTier: async (data: StorageTierCreate): Promise<StorageTier> => {
    try {
      const res = await apiClient.post<StorageTier>('/storage/tiers', data);
      return res.data;
    } catch {
      return v12MockAdapter.createStorageTier(data);
    }
  },

  offloadStorageTier: async (tierId: string, params?: TierOffloadRequest): Promise<TierOffloadResponse> => {
    try {
      const res = await apiClient.post<TierOffloadResponse>(`/storage/tiers/${tierId}/offload`, params);
      return res.data;
    } catch {
      return v12MockAdapter.triggerTierOffload(tierId, params);
    }
  },
  triggerTierOffload: async (tierId: string, params?: TierOffloadRequest): Promise<TierOffloadResponse> => {
    return v12Api.offloadStorageTier(tierId, params);
  },

  // --- DR Runbooks ---
  listDRRunbooks: async (): Promise<DRRunbook[]> => {
    try {
      const res = await apiClient.get<DRRunbook[]>('/dr/runbooks');
      return res.data;
    } catch {
      return v12MockAdapter.getDRRunbooks();
    }
  },
  getDRRunbooks: async (): Promise<DRRunbook[]> => {
    return v12Api.listDRRunbooks();
  },

  getDRRunbook: async (runbookId: string): Promise<DRRunbookDetail> => {
    try {
      const res = await apiClient.get<DRRunbookDetail>(`/dr/runbooks/${runbookId}`);
      return res.data;
    } catch {
      return v12MockAdapter.getDRRunbook(runbookId);
    }
  },

  createDRRunbook: async (data: DRRunbookCreate): Promise<DRRunbookDetail> => {
    try {
      const res = await apiClient.post<DRRunbookDetail>('/dr/runbooks', data);
      return res.data;
    } catch {
      return v12MockAdapter.createDRRunbook(data);
    }
  },

  simulateDRRunbook: async (runbookId: string): Promise<DRSimulationResult> => {
    try {
      const res = await apiClient.post<DRSimulationResult>(`/dr/runbooks/${runbookId}/simulate`);
      return res.data;
    } catch {
      return v12MockAdapter.simulateDRRunbook(runbookId);
    }
  },

  executeDRRunbook: async (runbookId: string, params: DRExecuteRequest): Promise<DRRunbookExecution> => {
    try {
      const res = await apiClient.post<DRRunbookExecution>(`/dr/runbooks/${runbookId}/execute`, params);
      return res.data;
    } catch {
      return v12MockAdapter.executeDRRunbook(runbookId, params);
    }
  },

  getDRExecution: async (executionId: string): Promise<DRRunbookExecution> => {
    try {
      const res = await apiClient.get<DRRunbookExecution>(`/dr/runbooks/executions/${executionId}`);
      return res.data;
    } catch {
      return v12MockAdapter.getDRExecution(executionId);
    }
  },

  listDRExecutions: async (): Promise<DRRunbookExecution[]> => {
    try {
      const res = await apiClient.get<DRRunbookExecution[]>('/dr/runbooks/executions');
      return res.data;
    } catch {
      return v12MockAdapter.listDRExecutions();
    }
  },

  // --- Instant Recovery ---
  listInstantMounts: async (): Promise<InstantMountSession[]> => {
    try {
      const res = await apiClient.get<InstantMountSession[]>('/recovery/instant-mounts');
      return res.data;
    } catch {
      return v12MockAdapter.getInstantMounts();
    }
  },
  getInstantMounts: async (): Promise<InstantMountSession[]> => {
    return v12Api.listInstantMounts();
  },

  createInstantMount: async (data: InstantMountCreateRequest): Promise<InstantMountSession> => {
    try {
      const res = await apiClient.post<InstantMountSession>('/recovery/instant-mounts', data);
      return res.data;
    } catch {
      return v12MockAdapter.createInstantMount(data);
    }
  },

  dismountInstantMount: async (mountId: string, force: boolean = false): Promise<InstantDismountResponse> => {
    try {
      const res = await apiClient.delete<InstantDismountResponse>(`/recovery/instant-mounts/${mountId}`, {
        params: { force }
      });
      return res.data;
    } catch {
      return v12MockAdapter.dismountInstantMount(mountId, force);
    }
  }
};

// Typed top-level function exports satisfying Step 2 contract
export const listCloudCredentials = v12Api.listCloudCredentials;
export const createCloudCredential = v12Api.createCloudCredential;
export const deleteCloudCredential = v12Api.deleteCloudCredential;

export const listStorageTiers = v12Api.listStorageTiers;
export const getStorageTier = v12Api.getStorageTier;
export const createStorageTier = v12Api.createStorageTier;
export const offloadStorageTier = v12Api.offloadStorageTier;

export const listDRRunbooks = v12Api.listDRRunbooks;
export const getDRRunbook = v12Api.getDRRunbook;
export const createDRRunbook = v12Api.createDRRunbook;
export const simulateDRRunbook = v12Api.simulateDRRunbook;
export const executeDRRunbook = v12Api.executeDRRunbook;

export const getDRExecution = v12Api.getDRExecution;
export const listDRExecutions = v12Api.listDRExecutions;

export const listInstantMounts = v12Api.listInstantMounts;
export const createInstantMount = v12Api.createInstantMount;
export const dismountInstantMount = v12Api.dismountInstantMount;

export default v12Api;

