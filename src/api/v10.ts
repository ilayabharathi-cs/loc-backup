/**
 * RetroVault V10 Operational Intelligence, Observability, Capacity & Compliance API Client
 */

import apiClient from './client';

export interface ComponentHealth {
  component: string;
  status: 'HEALTHY' | 'DEGRADED' | 'WARNING' | 'CRITICAL' | 'UNKNOWN';
  latency_ms: number;
  last_success: string | null;
  last_failure: string | null;
  reason: string | null;
  details: Record<string, any> | null;
}

export interface SystemHealth {
  overall_status: 'HEALTHY' | 'DEGRADED' | 'WARNING' | 'CRITICAL' | 'UNKNOWN';
  overall_reason: string;
  check_type: string;
  evaluated_at: string;
  components: Record<string, ComponentHealth>;
}

export interface OperationalAlert {
  id: number;
  alert_id: string;
  alert_type: string;
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  status: 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED' | 'SUPPRESSED';
  source: string;
  resource_id: string;
  title: string;
  message: string;
  occurrence_count: number;
  first_seen_at: string;
  last_seen_at: string;
  incident_id?: string | null;
}

export interface OperationalIncident {
  incident_id: string;
  title: string;
  status: 'DETECTED' | 'ACKNOWLEDGED' | 'INVESTIGATING' | 'MITIGATING' | 'MONITORING' | 'RESOLVED' | 'CLOSED';
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  root_event: string;
  relationship_type: string;
  affected_resources: string[];
  child_alerts: string[];
  timeline: Array<{ timestamp: string; event: string; user?: string; note?: string; message?: string }>;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface Recommendation {
  id: string;
  severity: string;
  affected_resource: string;
  reason: string;
  evidence: Record<string, any>;
  recommended_action: string;
  generated_at: string;
  is_automated_execution_allowed: boolean;
}

export interface CapacityOverview {
  total_repositories: number;
  total_capacity_bytes: number;
  total_used_bytes: number;
  total_free_bytes: number;
  overall_utilization_pct: number;
  repositories: Array<{
    repository_id: number;
    name: string;
    path: string;
    status: string;
    capacity_bytes: number;
    used_bytes: number;
    free_bytes: number;
    utilization_pct: number;
    dedup_ratio: number;
    compression_ratio: number;
    physical_savings_bytes: number;
  }>;
}

export interface CapacityForecast {
  repository_id: number;
  repository_name?: string;
  status: 'PROJECTED' | 'INSUFFICIENT_DATA' | 'ERROR';
  is_projection: boolean;
  method_used: string;
  sample_count: number;
  data_window_days: number;
  current_used_bytes?: number;
  total_capacity_bytes?: number;
  free_bytes?: number;
  daily_burn_rate_bytes: number;
  days_to_depletion?: number | null;
  estimated_depletion_date?: string | null;
  forecast_7d_bytes?: number | null;
  forecast_30d_bytes?: number | null;
  forecast_90d_bytes?: number | null;
  confidence_r_squared?: number | null;
  disclaimer?: string;
  message?: string;
}

export interface ObservabilityOverview {
  window: string;
  backup_performance: Record<string, any>;
  restore_performance: Record<string, any>;
  cas_storage_efficiency: Record<string, any>;
  database_latency: Record<string, any>;
  system_resources: {
    cpu_utilization_pct: number;
    memory_utilization_pct: number;
    disk_io_read_mbs: number;
    disk_io_write_mbs: number;
    network_throughput_mbs: number;
    worker_utilization_pct: number;
  };
}

export interface ComplianceSummary {
  framework: string;
  legal_claim_disclaimer: string;
  domains_total: number;
  status_distribution: Record<string, number>;
  domains: Record<string, {
    evidence_id: string;
    status: string;
    summary: string;
    verification_hash: string;
    evaluated_at: string;
  }>;
}

export interface ComplianceReport {
  report_id: string;
  report_type: string;
  title: string;
  period_start: string;
  period_end: string;
  scope: string;
  system_version: string;
  generated_by: string;
  generated_at: string;
  evidence_summary: Record<string, any>;
}

export interface ReportExecution {
  execution_id: string;
  report_id: string;
  format: string;
  status: string;
  file_path?: string | null;
  file_size_bytes: number;
  checksum_sha256?: string | null;
  created_at: string;
}

// --- Operations API Calls ---
export const getSystemHealth = async (checkType: string = 'deep_health'): Promise<SystemHealth> => {
  const res = await apiClient.get<SystemHealth>(`/operations/health?check_type=${checkType}`);
  return res.data;
};

export const getOperationalAlerts = async (status?: string): Promise<OperationalAlert[]> => {
  const url = status ? `/operations/alerts?status=${status}` : `/operations/alerts`;
  const res = await apiClient.get<OperationalAlert[]>(url);
  return res.data;
};

export const acknowledgeAlert = async (alertId: string): Promise<OperationalAlert> => {
  const res = await apiClient.post<OperationalAlert>(`/operations/alerts/${alertId}/acknowledge`, {});
  return res.data;
};

export const resolveAlert = async (alertId: string): Promise<OperationalAlert> => {
  const res = await apiClient.post<OperationalAlert>(`/operations/alerts/${alertId}/resolve`, {});
  return res.data;
};

export const getOperationalIncidents = async (): Promise<OperationalIncident[]> => {
  const res = await apiClient.get<OperationalIncident[]>(`/operations/incidents`);
  return res.data;
};

export const updateIncidentStatus = async (incidentId: string, status: string, note?: string): Promise<OperationalIncident> => {
  const res = await apiClient.put<OperationalIncident>(`/operations/incidents/${incidentId}`, { status, note });
  return res.data;
};

export const getRecommendations = async (): Promise<Recommendation[]> => {
  const res = await apiClient.get<Recommendation[]>(`/operations/recommendations`);
  return res.data;
};

// --- Capacity API Calls ---
export const getCapacityOverview = async (): Promise<CapacityOverview> => {
  const res = await apiClient.get<CapacityOverview>(`/capacity/`);
  return res.data;
};

export const takeCapacitySnapshot = async (repoId: number): Promise<any> => {
  const res = await apiClient.post(`/capacity/snapshots/${repoId}`);
  return res.data;
};

export const getCapacityForecast = async (repoId: number, windowDays: number = 30): Promise<CapacityForecast> => {
  const res = await apiClient.get<CapacityForecast>(`/capacity/forecast?repository_id=${repoId}&window_days=${windowDays}`);
  return res.data;
};

// --- Observability API Calls ---
export const getObservabilityOverview = async (window: string = '24h'): Promise<ObservabilityOverview> => {
  const res = await apiClient.get<ObservabilityOverview>(`/observability/?window=${window}`);
  return res.data;
};

// --- Compliance & Reports API Calls ---
export const getComplianceSummary = async (): Promise<ComplianceSummary> => {
  const res = await apiClient.get<ComplianceSummary>(`/compliance/`);
  return res.data;
};

export const getReports = async (): Promise<ComplianceReport[]> => {
  const res = await apiClient.get<ComplianceReport[]>(`/reports/`);
  return res.data;
};

export const generateReport = async (reportType: string, title?: string): Promise<ComplianceReport> => {
  const res = await apiClient.post<ComplianceReport>(`/reports/`, { report_type: reportType, title });
  return res.data;
};

export const exportReport = async (reportId: string, format: string): Promise<ReportExecution> => {
  const res = await apiClient.post<ReportExecution>(`/reports/${reportId}/export`, { format });
  return res.data;
};

export const getReportDownloadUrl = (reportId: string, format: string = 'JSON'): string => {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
  return `${base}/reports/${reportId}/download?format=${format}`;
};
