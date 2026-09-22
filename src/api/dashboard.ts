import apiClient from './client';

export interface DashboardSummaryData {
  total_clients: number;
  online_clients: number;
  offline_clients: number;
  pending_clients: number;
  successful_backups: number;
  failed_backups: number;
  running_backups: number;
  storage_total: number;
  storage_used: number;
  storage_available: number;
  average_rpo_seconds: number;
  failed_jobs_last_24h: number;
  recent_jobs: any[];
  recent_activity: any[];
}

export const dashboardApi = {
  getSummary: async () => {
    const res = await apiClient.get('/dashboard/summary');
    return res.data;
  }
};
