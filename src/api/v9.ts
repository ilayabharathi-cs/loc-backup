/**
 * RetroVault V9 High Availability & Distributed Cluster API Client
 */

import axios from 'axios';

const API_BASE = '/api/v1';

export interface ClusterNode {
  node_id: string;
  hostname: string;
  ip_address: string;
  port: number;
  roles: string[];
  status: string;
  current_load: number;
  active_jobs_count: number;
  max_concurrent_jobs: number;
  last_heartbeat_at: string | null;
  registered_at: string;
  is_draining: boolean;
}

export interface LeaderStatus {
  leader_node_id: string | null;
  is_active: boolean;
  lease_expires_at: string | null;
  last_leader?: string | null;
}

export interface ClusterStatus {
  cluster_status: string;
  total_nodes: number;
  active_nodes: number;
  leader: LeaderStatus;
  database: {
    status: string;
    is_connected: boolean;
    latency_ms: number;
    dialect: string;
    ha_mode: string;
  };
  backpressure: {
    backpressure_level: string;
    queued_jobs: number;
    active_nodes: number;
    should_throttle_new_jobs: boolean;
  };
  categories: Record<string, {
    running: number;
    queued: number;
    max_concurrency: number;
    utilization_pct: number;
    is_saturated: boolean;
  }>;
  active_locks_count: number;
  queued_jobs_count: number;
  running_jobs_count: number;
}

export interface ClusterEvent {
  id: number;
  event_type: string;
  severity: string;
  node_id: string | null;
  details: Record<string, any>;
  created_at: string;
}

export interface DistributedJob {
  id: number;
  job_type: string;
  priority: string;
  priority_weight: number;
  status: string;
  client_id: string | null;
  backup_job_id: number | null;
  repository_id: number | null;
  owner_node_id: string | null;
  attempt_count: number;
  max_attempts: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  payload: Record<string, any> | null;
}

export interface BulkOperation {
  operation_id: string;
  operation_type: string;
  status: string;
  target_count: number;
  success_count: number;
  failure_count: number;
  skipped_count: number;
  started_at: string | null;
  completed_at: string | null;
  created_by: string | null;
  details: Record<string, any>;
}

export const v9Api = {
  // Cluster endpoints
  getClusterStatus: async (): Promise<ClusterStatus> => {
    const res = await axios.get(`${API_BASE}/cluster/status`);
    return res.data;
  },

  listNodes: async (activeOnly = false): Promise<ClusterNode[]> => {
    const res = await axios.get(`${API_BASE}/cluster/nodes`, { params: { active_only: activeOnly } });
    return res.data;
  },

  registerNode: async (payload: {
    node_id: string;
    hostname: string;
    ip_address: string;
    port?: number;
    roles?: string[];
    max_concurrent_jobs?: number;
  }): Promise<ClusterNode> => {
    const res = await axios.post(`${API_BASE}/cluster/nodes/register`, payload);
    return res.data;
  },

  drainNode: async (nodeId: string): Promise<any> => {
    const res = await axios.post(`${API_BASE}/cluster/nodes/${encodeURIComponent(nodeId)}/drain`);
    return res.data;
  },

  resumeNode: async (nodeId: string): Promise<any> => {
    const res = await axios.post(`${API_BASE}/cluster/nodes/${encodeURIComponent(nodeId)}/resume`);
    return res.data;
  },

  deregisterNode: async (nodeId: string): Promise<any> => {
    const res = await axios.post(`${API_BASE}/cluster/nodes/${encodeURIComponent(nodeId)}/deregister`);
    return res.data;
  },

  getLeader: async (): Promise<LeaderStatus> => {
    const res = await axios.get(`${API_BASE}/cluster/leader`);
    return res.data;
  },

  electLeader: async (nodeId: string, ttlSeconds = 15): Promise<any> => {
    const res = await axios.post(`${API_BASE}/cluster/leader/elect`, { node_id: nodeId, ttl_seconds: ttlSeconds });
    return res.data;
  },

  resignLeader: async (nodeId: string): Promise<any> => {
    const res = await axios.post(`${API_BASE}/cluster/leader/resign`, { node_id: nodeId });
    return res.data;
  },

  reconcileCluster: async (leaderNodeId: string, force = false): Promise<any> => {
    const res = await axios.post(`${API_BASE}/cluster/reconcile`, null, {
      params: { leader_node_id: leaderNodeId, force },
    });
    return res.data;
  },

  listEvents: async (limit = 50): Promise<ClusterEvent[]> => {
    const res = await axios.get(`${API_BASE}/cluster/events`, { params: { limit } });
    return res.data;
  },

  // Distributed Scheduler endpoints
  listJobs: async (params?: { status?: string; job_type?: string; limit?: number }): Promise<DistributedJob[]> => {
    const res = await axios.get(`${API_BASE}/scheduler/jobs`, { params });
    return res.data;
  },

  enqueueJob: async (payload: {
    job_type: string;
    priority?: string;
    client_id?: string;
    backup_job_id?: number;
    repository_id?: number;
    payload?: Record<string, any>;
  }): Promise<DistributedJob> => {
    const res = await axios.post(`${API_BASE}/scheduler/jobs`, payload);
    return res.data;
  },

  getWorkerPools: async (): Promise<any> => {
    const res = await axios.get(`${API_BASE}/scheduler/pools`);
    return res.data;
  },

  // Fleet Bulk Operations endpoints
  triggerBulkBackup: async (payload: {
    client_ids?: string[];
    job_type?: string;
    priority?: string;
    created_by?: string;
  }): Promise<any> => {
    const res = await axios.post(`${API_BASE}/fleet/bulk/backup`, payload);
    return res.data;
  },

  listBulkOperations: async (limit = 50): Promise<BulkOperation[]> => {
    const res = await axios.get(`${API_BASE}/fleet/bulk/operations`, { params: { limit } });
    return res.data;
  },
};
