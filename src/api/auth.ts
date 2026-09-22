import apiClient from './client';

export interface LoginResponseData {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: number;
  username: string;
  role: string;
}

export const authApi = {
  login: async (username: string, password: string) => {
    const res = await apiClient.post('/auth/login', { username, password });
    if (res.data?.success && res.data?.data?.access_token) {
      localStorage.setItem('retrovault_access_token', res.data.data.access_token);
      localStorage.setItem('retrovault_user_role', res.data.data.role);
      localStorage.setItem('retrovault_username', res.data.data.username);
    }
    return res.data;
  },

  getMe: async () => {
    const res = await apiClient.get('/auth/me');
    return res.data;
  },

  logout: () => {
    localStorage.removeItem('retrovault_access_token');
    localStorage.removeItem('retrovault_user_role');
    localStorage.removeItem('retrovault_username');
  },

  isAuthenticated: (): boolean => {
    return Boolean(localStorage.getItem('retrovault_access_token'));
  },

  getUserRole: (): string => {
    return localStorage.getItem('retrovault_user_role') || 'viewer';
  }
};
