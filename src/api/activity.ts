import apiClient from './client';

export interface AuditLogApiData {
  id: number;
  user_id?: number;
  username?: string;
  client_id?: number;
  client_identifier?: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  ip_address?: string;
  details?: string;
  created_at: string;
  severity: string;
}

export const activityApi = {
  list: async (params?: {
    client?: string;
    severity?: string;
    action?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
  }) => {
    const res = await apiClient.get('/activity', { params });
    return res.data;
  }
};
