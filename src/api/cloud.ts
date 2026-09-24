/**
 * RetroVault V12 Cloud & Hybrid Storage Tiering API Client
 */

import apiClient from './client';

export interface CloudCredentialCreate {
  name: string;
  provider: string; // 's3' | 'minio' | 'wasabi' | 'mock'
  access_key: string;
  secret_key: string;
  endpoint?: string;
  region?: string;
  prefix?: string;
  use_tls?: boolean;
  verify_ssl?: boolean;
}

export interface CloudCredentialResponse {
  id: number;
  credential_id: string;
  name: string;
  provider: string;
  endpoint?: string | null;
  region?: string | null;
  prefix?: string | null;
  use_tls: boolean;
  verify_ssl: boolean;
  access_key_masked: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface StorageTierCreate {
  name: string;
  tier_type: string; // 'CLOUD_S3' | 'HOT' | 'WARM' | 'COLD' | 'ARCHIVE'
  provider: string; // 's3' | 'minio' | 'wasabi' | 'mock'
  credential_id?: string;
  bucket: string;
  prefix?: string;
  object_lock_enabled?: boolean;
  retention_period_days?: number;
  immutability_mode?: string; // 'NONE' | 'GOVERNANCE' | 'COMPLIANCE'
  is_default?: boolean;
}

export interface StorageTierUpdate {
  name?: string;
  bucket?: string;
  prefix?: string;
  object_lock_enabled?: boolean;
  retention_period_days?: number;
  immutability_mode?: string;
  is_enabled?: boolean;
}

export interface StorageTierResponse {
  id: number;
  tier_id: string;
  name: string;
  tier_type: string;
  provider: string;
  credential_id?: number | null;
  bucket: string;
  prefix?: string | null;
  state: 'CREATED' | 'VALIDATING' | 'READY' | 'DEGRADED' | 'ERROR' | 'DISABLED';
  object_lock_enabled: boolean;
  retention_period_days: number;
  immutability_mode: string;
  is_default: boolean;
  is_enabled: boolean;
  last_validated_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface StorageTierValidateResponse {
  tier_id: string;
  state: string;
  valid: boolean;
  latency_ms?: number | null;
  details?: Record<string, any> | null;
  error?: string | null;
}

export interface OffloadItemResponse {
  object_id: string;
  offload_id?: string | null;
  size?: number | null;
  status: string;
  error?: string | null;
}

export interface OffloadResponse {
  total: number;
  offloaded_count: number;
  failed_count: number;
  items: OffloadItemResponse[];
}

export interface RemoteVerificationResponse {
  object_id: string;
  tier_id: string;
  remote_key: string;
  exists: boolean;
  remote_size?: number | null;
  expected_size?: number | null;
  checksum_verified?: boolean | null;
  verification_status: string;
  error?: string | null;
}

// Credentials API
export const getCloudCredentials = async (): Promise<{ success: boolean; data: CloudCredentialResponse[]; message?: string }> => {
  const res = await apiClient.get('/cloud/credentials');
  return res.data;
};

export const createCloudCredential = async (data: CloudCredentialCreate): Promise<{ success: boolean; data: CloudCredentialResponse; message?: string }> => {
  const res = await apiClient.post('/cloud/credentials', data);
  return res.data;
};

export const deleteCloudCredential = async (id: string | number): Promise<{ success: boolean; message?: string }> => {
  const res = await apiClient.delete(`/cloud/credentials/${id}`);
  return res.data;
};

// Storage Tiers API
export const getStorageTiers = async (): Promise<{ success: boolean; data: StorageTierResponse[]; message?: string }> => {
  const res = await apiClient.get('/cloud/tiers');
  return res.data;
};

export const getStorageTier = async (id: string | number): Promise<{ success: boolean; data: StorageTierResponse; message?: string }> => {
  const res = await apiClient.get(`/cloud/tiers/${id}`);
  return res.data;
};

export const createStorageTier = async (data: StorageTierCreate): Promise<{ success: boolean; data: StorageTierResponse; message?: string }> => {
  const res = await apiClient.post('/cloud/tiers', data);
  return res.data;
};

export const updateStorageTier = async (id: string | number, data: StorageTierUpdate): Promise<{ success: boolean; data: StorageTierResponse; message?: string }> => {
  const res = await apiClient.put(`/cloud/tiers/${id}`, data);
  return res.data;
};

export const deleteStorageTier = async (id: string | number): Promise<{ success: boolean; message?: string }> => {
  const res = await apiClient.delete(`/cloud/tiers/${id}`);
  return res.data;
};

export const validateStorageTier = async (id: string | number): Promise<{ success: boolean; data: StorageTierValidateResponse; message?: string }> => {
  const res = await apiClient.post(`/cloud/tiers/${id}/validate`);
  return res.data;
};

export const testStorageTierConnection = async (id: string | number): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/cloud/tiers/${id}/test-connection`);
  return res.data;
};

export const offloadObjects = async (id: string | number, storageObjectIds: string[]): Promise<{ success: boolean; data: OffloadResponse; message?: string }> => {
  const res = await apiClient.post(`/cloud/tiers/${id}/offload`, { storage_object_ids: storageObjectIds });
  return res.data;
};

export const verifyRemoteObject = async (id: string | number, objectId: string): Promise<{ success: boolean; data: RemoteVerificationResponse; message?: string }> => {
  const res = await apiClient.post(`/cloud/tiers/${id}/verify/${objectId}`);
  return res.data;
};

export const restoreFromTier = async (id: string | number, objectId: string): Promise<{ success: boolean; data: Record<string, any>; message?: string }> => {
  const res = await apiClient.post(`/cloud/tiers/${id}/restore/${objectId}`);
  return res.data;
};
