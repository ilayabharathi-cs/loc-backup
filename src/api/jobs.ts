import apiClient from './client';

export interface JobApiData {
  id: number;
  job_id: string;
  client_id: number;
  client_identifier?: string;
  client_hostname?: string;
  policy_id?: number;
  policy_name?: string;
  status: string;
  scheduled_at?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  data_processed_mb?: number;
  progress_percent?: number;
}

export const jobsApi = {
  list: async (params?: { status?: string; client_id?: string }) => {
    const res = await apiClient.get('/jobs', { params });
    return res.data;
  },

  get: async (jobId: string) => {
    const res = await apiClient.get(`/jobs/${jobId}`);
    return res.data;
  },

  create: async (data: { client_id: string; policy_id?: number }) => {
    const res = await apiClient.post('/jobs', data);
    return res.data;
  },

  cancel: async (jobId: string) => {
    const res = await apiClient.post(`/jobs/${jobId}/cancel`);
    return res.data;
  },

  retry: async (jobId: string) => {
    const res = await apiClient.post(`/jobs/${jobId}/retry`);
    return res.data;
  }
};
