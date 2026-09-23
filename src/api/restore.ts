import apiClient from './client';

export interface RestoreItemApiData {
  id: number;
  restore_job_id: number;
  backup_file_id?: number;
  relative_path: string;
  destination_path: string;
  source_size: number;
  restored_size: number;
  source_sha256?: string;
  restored_sha256?: string;
  status: string;
  retry_count: number;
  error_code?: string;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  verified_at?: string;
}

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
  restore_mode?: string;
  conflict_mode?: string;
  metadata_mode?: string;
  total_files?: number;
  completed_files?: number;
  failed_files?: number;
  skipped_files?: number;
  total_bytes?: number;
  restored_bytes?: number;
  verified_bytes?: number;
  progress_percent?: number;
  started_at?: string;
  completed_at?: string;
  cancelled_at?: string;
  restore_requested_at?: string;
  first_byte_restored_at?: string;
  error_message?: string;
  rto_metrics?: {
    queue_time: string;
    startup_time: string;
    restore_duration: string;
    total_restore_time: string;
    transfer_speed_mb_s: number;
  };
  created_at: string;
}

export interface RestorePreviewData {
  recovery_point_id: number;
  source_client_id: string;
  destination_root: string;
  restore_mode: string;
  conflict_mode: string;
  total_files: number;
  logical_bytes: number;
  estimated_stored_read_bytes: number;
  actions: {
    CREATE: number;
    OVERWRITE: number;
    SKIP: number;
    CONFLICT: number;
    RENAME: number;
  };
  items: Array<{
    backup_file_id: number;
    file_name: string;
    relative_path: string;
    destination_path: string;
    size_bytes: number;
    stored_size_bytes: number;
    sha256?: string;
    predicted_action: string;
    destination_exists: boolean;
  }>;
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
    restore_mode?: string;
    conflict_mode?: string;
    metadata_mode?: string;
    selected_paths?: string[];
    acknowledge_cross_client?: boolean;
  }) => {
    const res = await apiClient.post('/restore/jobs', data);
    return res.data;
  },

  preview: async (data: {
    recovery_point_id: number;
    restore_mode: string;
    destination_root: string;
    conflict_mode: string;
    selected_paths?: string[];
  }) => {
    const res = await apiClient.post('/restore/preview', data);
    return res.data;
  },

  browseFiles: async (pointId: number) => {
    const res = await apiClient.get(`/restore/recovery-points/${pointId}/files`);
    return res.data;
  },

  searchFiles: async (pointId: number, params?: { q?: string; ext?: string }) => {
    const res = await apiClient.get(`/restore/recovery-points/${pointId}/files/search`, { params });
    return res.data;
  },

  start: async (restoreId: string) => {
    const res = await apiClient.post(`/restore/jobs/${restoreId}/start`);
    return res.data;
  },

  pause: async (restoreId: string) => {
    const res = await apiClient.post(`/restore/jobs/${restoreId}/pause`);
    return res.data;
  },

  resume: async (restoreId: string) => {
    const res = await apiClient.post(`/restore/jobs/${restoreId}/resume`);
    return res.data;
  },

  cancel: async (restoreId: string) => {
    const res = await apiClient.post(`/restore/jobs/${restoreId}/cancel`);
    return res.data;
  },

  getItems: async (restoreId: string) => {
    const res = await apiClient.get(`/restore/jobs/${restoreId}/items`);
    return res.data;
  },

  getLogs: async (restoreId: string) => {
    const res = await apiClient.get(`/restore/jobs/${restoreId}/logs`);
    return res.data;
  }
};
