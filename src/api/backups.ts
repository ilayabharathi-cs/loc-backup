import apiClient from './client';

export interface BackupRunApiData {
  id: number;
  job_id: number;
  client_id: number;
  client_identifier?: string;
  backup_type: string;
  started_at: string;
  completed_at?: string;
  status: string;
  files_processed: number;
  bytes_processed: number;
  bytes_uploaded: number;
  error_count: number;
  error_message?: string;
}

export interface RecoveryPointApiData {
  id: number;
  client_id: number;
  client_identifier?: string;
  client_hostname?: string;
  backup_run_id: number;
  timestamp: string;
  files_count: number;
  total_size_bytes: number;
  status: string;
  created_at: string;
}

export const backupsApi = {
  getRuns: async (params?: { client_id?: string; limit?: number }) => {
    const res = await apiClient.get('/backups/runs', { params });
    return res.data;
  },

  getRun: async (runId: number) => {
    const res = await apiClient.get(`/backups/runs/${runId}`);
    return res.data;
  },

  getRecoveryPoints: async (params?: { client_id?: string }) => {
    const res = await apiClient.get('/backups/recovery-points', { params });
    return res.data;
  },

  getRecoveryPoint: async (recoveryPointId: number) => {
    const res = await apiClient.get(`/backups/recovery-points/${recoveryPointId}`);
    return res.data;
  },

  getFiles: async (params?: { run_id?: number; client_id?: string }) => {
    const res = await apiClient.get('/backups/files', { params });
    return res.data;
  }
};
