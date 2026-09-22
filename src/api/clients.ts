import apiClient from './client';

export interface ClientApiData {
  id: number;
  client_id: string;
  hostname: string;
  device_id: string;
  os: string;
  os_version?: string;
  ip_address: string;
  agent_version: string;
  status: string;
  last_seen?: string;
  created_at: string;
  updated_at: string;
}

export const clientsApi = {
  list: async (params?: { status?: string; search?: string }) => {
    const res = await apiClient.get('/clients', { params });
    return res.data;
  },

  get: async (clientId: string) => {
    const res = await apiClient.get(`/clients/${clientId}`);
    return res.data;
  },

  create: async (data: Partial<ClientApiData>) => {
    const res = await apiClient.post('/clients', data);
    return res.data;
  },

  update: async (clientId: string, data: Partial<ClientApiData>) => {
    const res = await apiClient.patch(`/clients/${clientId}`, data);
    return res.data;
  },

  delete: async (clientId: string) => {
    const res = await apiClient.delete(`/clients/${clientId}`);
    return res.data;
  },

  approve: async (clientId: string) => {
    const res = await apiClient.post(`/clients/${clientId}/approve`);
    return res.data;
  },

  disable: async (clientId: string) => {
    const res = await apiClient.post(`/clients/${clientId}/disable`);
    return res.data;
  },

  triggerBackup: async (clientId: string) => {
    const res = await apiClient.post(`/clients/${clientId}/backup`);
    return res.data;
  }
};
