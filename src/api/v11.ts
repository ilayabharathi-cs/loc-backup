/**
 * RetroVault V11 Application-Aware Data Protection & Automated Recovery API Client
 */

import apiClient from './client';

export interface Workload {
  id: number;
  workload_id: string;
  client_id: string;
  type: string;
  name: string;
  version?: string | null;
  status: string;
  health: string;
  protection_state: string;
  consistency_capability: string;
  last_protected_at?: string | null;
  last_verified_at?: string | null;
  config?: Record<string, any> | null;
  metadata?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface RecoveryVerificationStep {
  step_name: string;
  step_order: number;
  status: string;
  details?: Record<string, any> | null;
  error_message?: string | null;
}

export interface RecoveryVerification {
  id: number;
  verification_id: string;
  recovery_point_id: string;
  workload_id: string;
  verification_type: string;
  sandbox_path: string;
  status: string;
  duration_ms: number;
  error_message?: string | null;
  evidence?: Record<string, any> | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  steps?: RecoveryVerificationStep[];
}

export interface RecoveryReadiness {
  workload_id: string;
  readiness_state: 'READY' | 'DEGRADED' | 'NOT_READY' | 'UNKNOWN';
  rpo_compliance_percent: number;
  rto_estimate_seconds?: number | null;
  contributing_signals: Record<string, any>;
  blocking_factors: string[];
  degrading_factors: string[];
  evaluated_at: string;
}

export interface BackupChain {
  id: number;
  chain_id: string;
  workload_id: string;
  base_recovery_point_id: string;
  latest_recovery_point_id: string;
  chain_length: number;
  status: 'VALID' | 'DEGRADED' | 'BROKEN' | 'UNKNOWN';
  broken_reason?: string | null;
  last_validated_at: string;
  metadata?: Record<string, any> | null;
}

export interface PolicyLifecycle {
  id: number;
  policy_id: string;
  version: number;
  lifecycle_state: 'DRAFT' | 'VALIDATING' | 'APPROVED' | 'ACTIVE' | 'SUSPENDED' | 'RETIRED';
  definition: Record<string, any>;
  effective_at?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface RemediationAction {
  id: number;
  remediation_id: string;
  action_type: string;
  target_resource_type: string;
  target_resource_id: string;
  requires_dual_approval: boolean;
  first_approver?: string | null;
  second_approver?: string | null;
  status: 'PENDING_APPROVAL' | 'APPROVED' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'REJECTED';
  execution_result?: Record<string, any> | null;
  created_at: string;
  executed_at?: string | null;
}

export interface RestorePreview {
  workload_id: string;
  source_recovery_point_id: string;
  target_destination: string;
  estimated_size_bytes: number;
  overwrite_conflicts: string[];
  required_dependencies: string[];
  consistency_status: string;
  validation_plan: string[];
  is_safe_to_proceed: boolean;
  blockers: string[];
}

export interface RestoreExecution {
  success: boolean;
  current_phase: string;
  phases_completed: string[];
  restored_bytes: number;
  artifacts_restored: number;
  verification_passed: boolean;
  validation_passed: boolean;
  details: Record<string, any>;
}

export const v11Api = {
  // --- Workloads ---
  getWorkloads: async (clientId?: string, workloadType?: string): Promise<Workload[]> => {
    const params: Record<string, string> = {};
    if (clientId) params.client_id = clientId;
    if (workloadType) params.workload_type = workloadType;
    const res = await apiClient.get<Workload[]>('/api/v1/workloads', { params });
    return res.data;
  },

  getWorkload: async (workloadId: string): Promise<Workload> => {
    const res = await apiClient.get<Workload>(`/api/v1/workloads/${workloadId}`);
    return res.data;
  },

  discoverWorkloads: async (clientId: string, providerType?: string): Promise<Workload[]> => {
    const res = await apiClient.post<Workload[]>(`/api/v1/workloads/${clientId}/discover`, {
      provider_type: providerType
    });
    return res.data;
  },

  protectWorkload: async (workloadId: string, backupType: string = 'FULL'): Promise<any> => {
    const res = await apiClient.post(`/api/v1/workloads/${workloadId}/protect`, {
      backup_type: backupType
    });
    return res.data;
  },

  previewRestore: async (
    workloadId: string,
    recoveryPointId: string,
    targetDestination: string,
    recoveryMode: string = 'APPLICATION_RESTORE'
  ): Promise<RestorePreview> => {
    const res = await apiClient.post<RestorePreview>(`/api/v1/workloads/${workloadId}/restore-preview`, {
      recovery_point_id: recoveryPointId,
      target_destination: targetDestination,
      recovery_mode: recoveryMode
    });
    return res.data;
  },

  executeRestore: async (
    workloadId: string,
    recoveryPointId: string,
    targetDestination: string,
    recoveryMode: string = 'APPLICATION_RESTORE'
  ): Promise<RestoreExecution> => {
    const res = await apiClient.post<RestoreExecution>(`/api/v1/workloads/${workloadId}/restore`, {
      recovery_point_id: recoveryPointId,
      target_destination: targetDestination,
      recovery_mode: recoveryMode
    });
    return res.data;
  },

  // --- Recovery Verification ---
  getRecoveryVerifications: async (workloadId?: string): Promise<RecoveryVerification[]> => {
    const params: Record<string, string> = {};
    if (workloadId) params.workload_id = workloadId;
    const res = await apiClient.get<RecoveryVerification[]>('/api/v1/recovery-verification', { params });
    return res.data;
  },

  triggerVerification: async (
    recoveryPointId: string,
    workloadId: string,
    verificationType: string = 'CHECKSUM'
  ): Promise<RecoveryVerification> => {
    const res = await apiClient.post<RecoveryVerification>('/api/v1/recovery-verification', {
      recovery_point_id: recoveryPointId,
      workload_id: workloadId,
      verification_type: verificationType
    });
    return res.data;
  },

  retryVerification: async (verificationId: string): Promise<RecoveryVerification> => {
    const res = await apiClient.post<RecoveryVerification>(`/api/v1/recovery-verification/${verificationId}/retry`);
    return res.data;
  },

  // --- Recovery Readiness ---
  getAllReadiness: async (): Promise<RecoveryReadiness[]> => {
    const res = await apiClient.get<RecoveryReadiness[]>('/api/v1/recovery-readiness');
    return res.data;
  },

  getWorkloadReadiness: async (workloadId: string): Promise<RecoveryReadiness> => {
    const res = await apiClient.get<RecoveryReadiness>(`/api/v1/recovery-readiness/${workloadId}`);
    return res.data;
  },

  // --- Backup Chains ---
  getBackupChains: async (workloadId?: string): Promise<BackupChain[]> => {
    const params: Record<string, string> = {};
    if (workloadId) params.workload_id = workloadId;
    const res = await apiClient.get<BackupChain[]>('/api/v1/backup-chains', { params });
    return res.data;
  },

  validateBackupChain: async (chainId: string): Promise<any> => {
    const res = await apiClient.post(`/api/v1/backup-chains/${chainId}/validate`);
    return res.data;
  },

  // --- Policy Orchestration ---
  getPolicyLifecycles: async (policyId?: string): Promise<PolicyLifecycle[]> => {
    const params: Record<string, string> = {};
    if (policyId) params.policy_id = policyId;
    const res = await apiClient.get<PolicyLifecycle[]>('/api/v1/policy-orchestration', { params });
    return res.data;
  },

  createPolicyVersion: async (policyId: string, definition: Record<string, any>): Promise<PolicyLifecycle> => {
    const res = await apiClient.post<PolicyLifecycle>('/api/v1/policy-orchestration', {
      policy_id: policyId,
      definition
    });
    return res.data;
  },

  approvePolicyVersion: async (lifecycleId: number, notes?: string): Promise<PolicyLifecycle> => {
    const res = await apiClient.post<PolicyLifecycle>(`/api/v1/policy-orchestration/${lifecycleId}/approve`, {
      notes
    });
    return res.data;
  },

  activatePolicyVersion: async (lifecycleId: number): Promise<PolicyLifecycle> => {
    const res = await apiClient.post<PolicyLifecycle>(`/api/v1/policy-orchestration/${lifecycleId}/activate`);
    return res.data;
  },

  rollbackPolicy: async (policyId: string, targetVersion: number): Promise<PolicyLifecycle> => {
    const res = await apiClient.post<PolicyLifecycle>(`/api/v1/policy-orchestration/${policyId}/rollback`, {
      target_version: targetVersion
    });
    return res.data;
  },

  // --- Remediations ---
  getRemediations: async (): Promise<RemediationAction[]> => {
    const res = await apiClient.get<RemediationAction[]>('/api/v1/remediations');
    return res.data;
  },

  proposeRemediation: async (
    actionType: string,
    targetResourceType: string,
    targetResourceId: string,
    requiresDualApproval: boolean = false
  ): Promise<RemediationAction> => {
    const res = await apiClient.post<RemediationAction>('/api/v1/remediations', {
      action_type: actionType,
      target_resource_type: targetResourceType,
      target_resource_id: targetResourceId,
      requires_dual_approval: requiresDualApproval
    });
    return res.data;
  },

  approveRemediation: async (remediationId: string): Promise<RemediationAction> => {
    const res = await apiClient.post<RemediationAction>(`/api/v1/remediations/${remediationId}/approve`);
    return res.data;
  },

  executeRemediation: async (remediationId: string): Promise<any> => {
    const res = await apiClient.post(`/api/v1/remediations/${remediationId}/execute`);
    return res.data;
  }
};
