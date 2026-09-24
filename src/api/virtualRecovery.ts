/**
 * RetroVault V12 Instant Virtual Recovery (IVR) API Client
 */

import apiClient from './client';

export type VirtualRecoveryState = 
  | 'CREATED'
  | 'PREPARING'
  | 'MOUNTING'
  | 'READY'
  | 'DEGRADED'
  | 'PAUSED'
  | 'HYDRATING'
  | 'COMPLETING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'UNMOUNTING';

export interface VirtualRecoverySessionCreate {
  recovery_point_id: number;
  target_path: string;
  client_id?: number;
  workload_id?: string;
  cloud_tier_id?: number;
  provider_type?: string;
}

export interface VirtualRecoverySessionResponse {
  id: number;
  session_id: string;
  recovery_point_id: number;
  client_id: number;
  workload_id?: string | null;
  target_path: string;
  mount_point?: string | null;
  provider_type: string;
  cloud_tier_id?: number | null;
  state: VirtualRecoveryState;
  hydration_status: string;
  total_files: number;
  total_bytes: number;
  hydrated_files: number;
  hydrated_bytes: number;
  hydration_speed_bps: number;
  hydration_eta_seconds?: number | null;
  read_requests_count: number;
  bytes_read: number;
  cache_hits: number;
  cache_misses: number;
  cache_bytes: number;
  time_to_first_access_ms?: number | null;
  time_to_app_ready_ms?: number | null;
  time_to_full_hydration_ms?: number | null;
  error_message?: string | null;
  created_at: string;
  mounted_at?: string | null;
  completed_at?: string | null;
}

export interface VirtualRecoveryMetricsResponse {
  session_id: string;
  state: VirtualRecoveryState;
  hydration_status: string;
  total_files: number;
  total_bytes: number;
  hydrated_files: number;
  hydrated_bytes: number;
  hydration_speed_bps: number;
  hydration_eta_seconds?: number | null;
  read_requests_count: number;
  bytes_read: number;
  cache_hits: number;
  cache_misses: number;
  cache_hit_ratio: number;
  cache_bytes: number;
  time_to_first_access_ms?: number | null;
  time_to_app_ready_ms?: number | null;
  time_to_full_hydration_ms?: number | null;
}

export const listVirtualRecoverySessions = async (): Promise<{ success: boolean; data: VirtualRecoverySessionResponse[]; message?: string }> => {
  const res = await apiClient.get('/virtual-recovery/sessions');
  return res.data;
};

export const getVirtualRecoverySession = async (id: string): Promise<{ success: boolean; data: VirtualRecoverySessionResponse; message?: string }> => {
  const res = await apiClient.get(`/virtual-recovery/sessions/${id}`);
  return res.data;
};

export const createVirtualRecoverySession = async (data: VirtualRecoverySessionCreate): Promise<{ success: boolean; data: VirtualRecoverySessionResponse; message?: string }> => {
  const res = await apiClient.post('/virtual-recovery/sessions', data);
  return res.data;
};

export const prepareVirtualRecoverySession = async (id: string): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/prepare`);
  return res.data;
};

export const mountVirtualRecoverySession = async (id: string): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/mount`);
  return res.data;
};

export const readLogicalPath = async (id: string, path: string, offset = 0, length = 0): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/read`, null, {
    params: { path, offset, length }
  });
  return res.data;
};

export const prefetchVirtualRecoverySession = async (id: string, paths: string[]): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/prefetch`, { paths });
  return res.data;
};

export const hydrateVirtualRecoverySession = async (id: string, maxFiles?: number): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/hydrate`, { max_files: maxFiles });
  return res.data;
};

export const pauseVirtualRecoverySession = async (id: string): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/pause`);
  return res.data;
};

export const resumeVirtualRecoverySession = async (id: string): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/resume`);
  return res.data;
};

export const validateVirtualRecoverySession = async (id: string): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/validate`);
  return res.data;
};

export const unmountVirtualRecoverySession = async (id: string): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/unmount`);
  return res.data;
};

export const cancelVirtualRecoverySession = async (id: string): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/virtual-recovery/sessions/${id}/cancel`);
  return res.data;
};

export const getVirtualRecoveryMetrics = async (id: string): Promise<{ success: boolean; data: VirtualRecoveryMetricsResponse; message?: string }> => {
  const res = await apiClient.get(`/virtual-recovery/sessions/${id}/metrics`);
  return res.data;
};
