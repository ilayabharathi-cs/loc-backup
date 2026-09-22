import apiClient from './client';

export interface RestoreJobApiData {
  id: number;
  restore_id: string;
  source_client_id: number;
  source_client_identifier?: string;
  target_client_id: number;
  target_client_identifier?: string;
  recovery_point_id: number;
  source_path: string;
  target_path: string;
  status: string;
  requested_by: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export const restoreApi = {
  list: async (params?: { status?: string }) => {
    const res = await apiClient.get('/restore/jobs', { params });
    return res.data;
  },

  get: async (restoreId: string) => {
    const res = await apiClient.get(`/restore/jobs/${restoreId}`);
    return res.data;
  },

  create: async (data: {
    source_client_id: string;
    target_client_id?: string;
    recovery_point_id: number;
    source_path: string;
    target_path: string;
    acknowledge_cross_client?: boolean;
  }) => {
    const res = await apiClient.post('/restore/jobs', data);
    return res.data;
  },

  cancel: async (restoreId: string) => {
    const res = await apiClient.post(`/restore/jobs/${restoreId}/cancel`);
    return res.data;
  }
};
