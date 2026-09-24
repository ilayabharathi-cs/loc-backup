/**
 * RetroVault V8 Enterprise Security, Ransomware Resilience & Fleet API Client
 */

import { apiClient as api } from './client';

export interface SecurityEvent {
  id: number;
  event_type: string;
  severity: string;
  client_id?: number;
  repository_id?: number;
  run_id?: number;
  recovery_point_id?: number;
  score: number;
  description: string;
  evidence_json?: string;
  status: string;
  created_at: string;
  acknowledged_at?: string;
  resolved_at?: string;
  resolved_by?: string;
}

export interface SecurityIncident {
  id: number;
  incident_number: string;
  title: string;
  severity: string;
  status: string;
  client_id?: number;
  candidate_recovery_point_id?: number;
  restore_test_id?: string;
  containment_notes?: string;
  created_at: string;
  updated_at: string;
  closed_at?: string;
  closed_by?: string;
}

export interface SecurityProfile {
  id: number;
  name: string;
  description?: string;
  anomaly_threshold: number;
  max_deletion_count: number;
  max_deletion_pct: number;
  require_mfa_for_deletion: boolean;
  entropy_threshold: number;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClientGroup {
  id: number;
  name: string;
  description?: string;
  policy_id?: number;
  security_profile_id?: number;
  repository_id?: number;
  created_at: string;
  updated_at: string;
}

export interface ConfigurationDrift {
  id: number;
  client_id: number;
  drift_type: string;
  expected_value: string;
  actual_value: string;
  severity: string;
  status: string;
  detected_at: string;
  resolved_at?: string;
}

export interface IntegrityScan {
  id: number;
  scan_id: string;
  repository_id: number;
  scan_type: string;
  total_objects: number;
  valid_objects: number;
  corrupted_objects: number;
  missing_objects: number;
  duration_seconds: number;
  status: string;
  details_json?: string;
  created_at: string;
}

export interface DeletionGuardRequest {
  id: number;
  request_type: string;
  requester_username: string;
  target_resource_type: string;
  target_resource_id: string;
  payload_json: string;
  status: string;
  risk_score: number;
  approved_by?: string;
  approved_at?: string;
  expires_at: string;
  created_at: string;
}

export interface SecuritySimulation {
  id: number;
  simulation_id: string;
  scenario_type: string;
  status: string;
  sandbox_path: string;
  parameters_json?: string;
  results_json?: string;
  started_at: string;
  completed_at?: string;
}

export const v8Api = {
  // Security Events
  getSecurityEvents: (params?: { status?: string; severity?: string; client_id?: number }) =>
    api.get<SecurityEvent[]>('/security/events', { params }),

  acknowledgeEvent: (eventId: number) =>
    api.post(`/security/events/${eventId}/acknowledge`),

  resolveEvent: (eventId: number, statusChoice: string = 'RESOLVED') =>
    api.post(`/security/events/${eventId}/resolve`, null, { params: { status_choice: statusChoice } }),

  evaluateRunAnomalies: (runId: number) =>
    api.post(`/security/runs/${runId}/evaluate-anomalies`),

  getCleanRecoveryPoints: (clientId: number, before?: string) =>
    api.get<{ client_id: number; clean_candidates: any[] }>(`/security/clean-recovery/${clientId}`, {
      params: before ? { before } : undefined,
    }),

  getSecurityProfiles: () =>
    api.get<SecurityProfile[]>('/security/profiles'),

  createSecurityProfile: (data: Partial<SecurityProfile>) =>
    api.post<SecurityProfile>('/security/profiles', data),

  protectRecoveryPoint: (rpId: number, data: { protection_state: string; hold_days?: number; reason?: string }) =>
    api.post(`/security/recovery-points/${rpId}/protect`, data),

  releaseRecoveryPointProtection: (rpId: number) =>
    api.post(`/security/recovery-points/${rpId}/release-protection`),

  // Fleet & Groups
  getClientGroups: () =>
    api.get<ClientGroup[]>('/fleet/groups'),

  createClientGroup: (data: Partial<ClientGroup>) =>
    api.post<ClientGroup>('/fleet/groups', data),

  assignClientGroup: (clientId: number, groupId?: number) =>
    api.post(`/fleet/clients/${clientId}/assign-group`, null, { params: { group_id: groupId } }),

  getClientEffectivePolicy: (clientId: number) =>
    api.get<any>(`/fleet/clients/${clientId}/effective-policy`),

  simulatePolicyDryRun: (clientId: number, policyId: number) =>
    api.post<any>(`/fleet/clients/${clientId}/simulate-policy/${policyId}`),

  getConfigurationDrifts: (params?: { client_id?: number; status?: string }) =>
    api.get<ConfigurationDrift[]>('/fleet/drifts', { params }),

  detectClientDrift: (clientId: number, agentConfig: Record<string, any>) =>
    api.post(`/fleet/clients/${clientId}/detect-drift`, agentConfig),

  // Security Incidents
  getIncidents: (params?: { status?: string; client_id?: number }) =>
    api.get<SecurityIncident[]>('/incidents', { params }),

  getIncident: (incidentId: number) =>
    api.get<SecurityIncident>(`/incidents/${incidentId}`),

  createIncident: (data: { title: string; severity?: string; client_id?: number; candidate_recovery_point_id?: number; containment_notes?: string }) =>
    api.post<SecurityIncident>('/incidents', data),

  transitionIncident: (incidentId: number, data: { status: string; notes?: string; candidate_rp_id?: number }) =>
    api.post(`/incidents/${incidentId}/transition`, data),

  // Integrity & Deletion Guard
  getIntegrityScans: (repositoryId?: number) =>
    api.get<IntegrityScan[]>('/security-ops/integrity/scans', { params: repositoryId ? { repository_id: repositoryId } : undefined }),

  triggerIntegrityScan: (data: { repository_id: number; scan_type?: string; sample_limit?: number }) =>
    api.post<any>('/security-ops/integrity/scan', data),

  getDeletionGuardRequests: (status?: string) =>
    api.get<DeletionGuardRequest[]>('/security-ops/deletion-guard/requests', { params: status ? { status } : undefined }),

  submitDeletionRequest: (data: { request_type: string; target_resource_type: string; target_resource_id: string; payload: Record<string, any> }) =>
    api.post<any>('/security-ops/deletion-guard/request', data),

  approveDeletionRequest: (guardId: number, mfaCode?: string) =>
    api.post(`/security-ops/deletion-guard/requests/${guardId}/approve`, { mfa_code: mfaCode }),

  rejectDeletionRequest: (guardId: number, reason?: string) =>
    api.post(`/security-ops/deletion-guard/requests/${guardId}/reject`, null, { params: { reason } }),

  getRepositoryImmutabilityCapabilities: (repoId: number) =>
    api.get<any>(`/security-ops/repositories/${repoId}/capabilities`),

  setRepositoryImmutability: (repoId: number, data: { immutability_state: string; retention_days?: number; provider_mode?: string }) =>
    api.post(`/security-ops/repositories/${repoId}/set-immutability`, null, {
      params: {
        immutability_state: data.immutability_state,
        retention_days: data.retention_days || 30,
        provider_mode: data.provider_mode || 'COMPLIANCE',
      },
    }),

  // Simulations
  getSimulations: () =>
    api.get<SecuritySimulation[]>('/simulations'),

  runSimulation: (data?: { scenario_type?: string; file_count?: number; encryption_ratio?: number }) =>
    api.post<any>('/simulations/run', data || {}),
};
