import apiClient from './client';

export interface StorageRepositoryApiData {
  id: number;
  name: string;
  repository_type: string;
  path: string;
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
  status: string;
  total_tb: number;
  used_tb: number;
  free_tb: number;
  dedup_ratio: number;
  compression_ratio: number;
  disk_health: string;
}

export interface StorageMetricsApiData {
  total_logical_bytes: number;
  total_stored_bytes: number;
  unique_original_bytes: number;
  bytes_saved: number;
  savings_percent: number;
  deduplication_ratio: number;
  compression_ratio: number;
  overall_efficiency_ratio: number;
  total_files_referenced: number;
  unique_storage_objects: number;
  repository_health: {
    status: string;
    repository_root: string;
    writable: boolean;
    total_bytes: number;
    used_bytes: number;
    free_bytes: number;
    free_percent: number;
  };
}

export const storageApi = {
  list: async () => {
    const res = await apiClient.get('/storage');
    return res.data;
  },

  get: async (repositoryId: number) => {
    const res = await apiClient.get(`/storage/${repositoryId}`);
    return res.data;
  },

  getMetrics: async () => {
    const res = await apiClient.get('/storage/metrics');
    return res.data;
  },

  listObjects: async (limit = 50, offset = 0) => {
    const res = await apiClient.get('/storage/objects', { params: { limit, offset } });
    return res.data;
  },

  verifyIntegrity: async (batchSize = 100, verifyContent = true) => {
    const res = await apiClient.post('/storage/verify', {
      batch_size: batchSize,
      verify_content: verifyContent,
    });
    return res.data;
  },

  triggerGc: async (dryRun = false) => {
    const res = await apiClient.post('/storage/gc', { dry_run: dryRun });
    return res.data;
  },

  listGcJobs: async (limit = 20) => {
    const res = await apiClient.get('/storage/gc/jobs', { params: { limit } });
    return res.data;
  },

  evaluateRetention: async (policyId?: number) => {
    const res = await apiClient.post('/retention/evaluate', {
      retention_policy_id: policyId,
    });
    return res.data;
  },

  toggleProtection: async (pointId: number, protect = true) => {
    const res = await apiClient.post(`/recovery-points/${pointId}/protect`, {
      protect,
    });
    return res.data;
  },
};
