/**
 * RetroVault V7 Enterprise Operations API Client
 */

import { apiClient as api } from './client';

export interface StorageRepository {
  id: number;
  name: string;
  repository_type: string;
  path: string;
  endpoint?: string;
  root_path?: string;
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
  capacity_bytes: number;
  status: string;
  protection_mode: string;
  encryption_enabled: boolean;
  last_health_check?: string;
}

export interface RepositoryHealth {
  repository_id: number;
  name: string;
  type: string;
  status: string;
  protection_mode: string;
  reachable: boolean;
  read_test: boolean;
  write_test: boolean;
  delete_test: boolean;
  latency_ms: number;
  capacity_bytes: number;
  used_bytes: number;
  available_bytes: number;
  free_percent: number;
  object_count: number;
  corrupted_object_count: number;
  pending_gc_count: number;
  pending_replication_jobs: number;
  last_successful_backup?: string;
  last_successful_replication?: string;
  last_health_check?: string;
  errors: string[];
}

export interface ReplicationJob {
  id: number;
  job_id: string;
  source_repository_id: number;
  destination_repository_id: number;
  recovery_point_id?: number;
  status: string;
  total_objects: number;
  completed_objects: number;
  failed_objects: number;
  skipped_objects: number;
  total_bytes: number;
  transferred_bytes: number;
  bandwidth_limit_mbps?: number;
  progress_percent: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  created_at: string;
}

export interface TopologyStatus {
  status: string;
  is_compliant: boolean;
  total_repositories: number;
  total_copies: number;
  media_types: string[];
  media_types_count: number;
  has_offsite: boolean;
  offsite_repositories: string[];
  primary_repositories: string[];
  secondary_repositories: string[];
  completed_replications: number;
  missing_requirements: string[];
  recommendation: string;
}

export interface AlertItem {
  id: number;
  rule_id?: number;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  status: string;
  resource_type?: string;
  resource_id?: string;
  acknowledged_by?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  created_at: string;
}

export interface DrReadiness {
  status: string;
  is_ready: boolean;
  reasons: string[];
  latest_recovery_point?: {
    id?: number;
    timestamp?: string;
    backup_type?: string;
  };
  latest_replication?: {
    job_id?: string;
    completed_at?: string;
  };
  latest_dr_drill?: {
    test_id?: string;
    result?: string;
    duration_seconds?: number;
    timestamp?: string;
  };
  rpo: {
    status: string;
    target_rpo_seconds: number;
    compliant_clients: number;
    breached_clients: number;
  };
  health_indicators: Record<string, { state: string; reason: string }>;
}

export interface SystemSetting {
  id: number;
  category: string;
  key: string;
  value: string;
  description?: string;
  updated_at: string;
}

// Repositories API
export const getRepositories = async () => (await api.get<{ success: boolean; data: StorageRepository[] }>('/repositories')).data;
export const getRepositoryHealth = async (id: number) => (await api.get<{ success: boolean; data: RepositoryHealth }>(`/repositories/${id}/health`)).data;
export const setRepositoryMaintenance = async (id: number, enabled: boolean) => (await api.post<{ success: boolean; data: StorageRepository }>(`/repositories/${id}/maintenance?enabled=${enabled}`)).data;

// Replication API
export const getReplicationJobs = async (status?: string) => (await api.get<{ success: boolean; data: ReplicationJob[] }>(`/replication/jobs${status ? `?status=${status}` : ''}`)).data;
export const createReplicationJob = async (payload: { source_repository_id: number; destination_repository_id: number; recovery_point_id?: number; bandwidth_limit_mbps?: number }) => (await api.post<{ success: boolean; data: ReplicationJob }>('/replication/jobs', payload)).data;
export const pauseReplicationJob = async (id: string) => (await api.post<{ success: boolean; data: ReplicationJob }>(`/replication/jobs/${id}/pause`)).data;
export const resumeReplicationJob = async (id: string) => (await api.post<{ success: boolean; data: ReplicationJob }>(`/replication/jobs/${id}/resume`)).data;
export const cancelReplicationJob = async (id: string) => (await api.post<{ success: boolean; data: ReplicationJob }>(`/replication/jobs/${id}/cancel`)).data;
export const retryReplicationJob = async (id: string) => (await api.post<{ success: boolean; data: ReplicationJob }>(`/replication/jobs/${id}/retry`)).data;
export const getTopology = async () => (await api.get<{ success: boolean; data: TopologyStatus }>('/replication/topology')).data;

// Alerts API
export const getAlerts = async (status?: string, severity?: string) => {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (severity) params.append('severity', severity);
  return (await api.get<{ success: boolean; data: AlertItem[] }>(`/alerts?${params.toString()}`)).data;
};
export const acknowledgeAlert = async (id: number) => (await api.post<{ success: boolean; data: AlertItem }>(`/alerts/${id}/acknowledge`)).data;
export const resolveAlert = async (id: number) => (await api.post<{ success: boolean; data: AlertItem }>(`/alerts/${id}/resolve`)).data;

// Security & MFA API
export const getSecurityOverview = async () => (await api.get<{ success: boolean; data: any }>('/security/overview')).data;
export const setupMfa = async () => (await api.post<{ success: boolean; data: { secret: string; provisioning_uri: string; recovery_codes: string[] } }>('/security/mfa/setup')).data;
export const verifyMfa = async (code: string) => (await api.post<{ success: boolean; data: { mfa_enabled: boolean } }>('/security/mfa/verify', { code })).data;
export const disableMfa = async (code: string) => (await api.post<{ success: boolean; data: { mfa_enabled: boolean } }>('/security/mfa/disable', { code })).data;
export const getSecurityAudit = async () => (await api.get<{ success: boolean; data: any[] }>('/security/audit')).data;

// DR API
export const getDrReadiness = async () => (await api.get<{ success: boolean; data: DrReadiness }>('/dr/readiness')).data;
export const runDrTest = async (recovery_point_id?: number) => (await api.post<{ success: boolean; data: any }>('/dr/tests', { recovery_point_id })).data;
export const getDrTests = async () => (await api.get<{ success: boolean; data: any[] }>('/dr/tests')).data;

// Settings API
export const getSystemSettings = async () => (await api.get<{ success: boolean; data: Record<string, SystemSetting[]> }>('/settings')).data;
export const updateSystemSetting = async (key: string, value: string) => (await api.put<{ success: boolean; data: SystemSetting }>(`/settings/${key}`, { value })).data;
export const getOperationalSchedules = async () => (await api.get<{ success: boolean; data: any[] }>('/settings/schedules')).data;
