import apiClient from './client';

export interface PolicyPathApiData {
  id?: number;
  path_type: string;
  path_value: string;
  is_excluded: boolean;
}

export interface PolicyApiData {
  id: number;
  name: string;
  description?: string;
  backup_type: string;
  change_detection: string;
  rpo_target_seconds: number;
  compression_enabled: boolean;
  encryption_enabled: boolean;
  cpu_limit_percent: number;
  network_limit_mbps: number;
  retention_days: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  paths: PolicyPathApiData[];
}

export const policiesApi = {
  list: async () => {
    const res = await apiClient.get('/policies');
    return res.data;
  },

  get: async (policyId: number) => {
    const res = await apiClient.get(`/policies/${policyId}`);
    return res.data;
  },

  create: async (data: Partial<PolicyApiData>) => {
    const res = await apiClient.post('/policies', data);
    return res.data;
  },

  update: async (policyId: number, data: Partial<PolicyApiData>) => {
    const res = await apiClient.patch(`/policies/${policyId}`, data);
    return res.data;
  },

  delete: async (policyId: number) => {
    const res = await apiClient.delete(`/policies/${policyId}`);
    return res.data;
  }
};
