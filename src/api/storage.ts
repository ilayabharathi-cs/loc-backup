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

export const storageApi = {
  list: async () => {
    const res = await apiClient.get('/storage');
    return res.data;
  },

  get: async (repositoryId: number) => {
    const res = await apiClient.get(`/storage/${repositoryId}`);
    return res.data;
  }
};
