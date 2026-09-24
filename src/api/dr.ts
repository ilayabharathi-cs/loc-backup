/**
 * RetroVault Disaster Recovery & Verification API Client
 */

import apiClient from './client';

export interface DrTestRequest {
  recovery_point_id?: number | null;
}

export interface DrTestResponse {
  test_id: string;
  recovery_point_id: number;
  result: 'PASSED' | 'FAILED' | 'PARTIAL';
  files_tested: number;
  bytes_tested: number;
  files_verified: number;
  failures: number;
  duration_seconds: number;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
}

export interface DrReadinessResponse {
  status: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  rpo_compliance: {
    status: 'MEETING' | 'WARNING' | 'MISSED' | 'UNKNOWN';
    target_hours: number;
    observed_rpo_hours: number;
  };
  latest_recovery_point?: {
    id: number;
    timestamp: string;
    total_size_bytes: number;
    files_count: number;
  } | null;
  latest_replication?: {
    job_id: string;
    completed_at: string;
    status: string;
  } | null;
  latest_dr_test?: {
    test_id: string;
    result: string;
    started_at: string;
    failures: number;
  } | null;
  health_indicators: Record<string, any>;
}

export const runAutomatedDrTest = async (recoveryPointId?: number | null): Promise<{ success: boolean; data: DrTestResponse; message?: string }> => {
  const res = await apiClient.post('/dr/tests', { recovery_point_id: recoveryPointId });
  return res.data;
};

export const listDrTests = async (limit = 50): Promise<{ success: boolean; data: DrTestResponse[]; message?: string }> => {
  const res = await apiClient.get('/dr/tests', { params: { limit } });
  return res.data;
};

export const getDrReadiness = async (): Promise<{ success: boolean; data: DrReadinessResponse; message?: string }> => {
  const res = await apiClient.get('/dr/readiness');
  return res.data;
};
