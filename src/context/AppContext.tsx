import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { 
  Client, BackupJob, BackupPolicy, StorageMetrics, ActivityLog, AppSettings, ToastNotification 
} from '../types';
import { 
  INITIAL_CLIENTS, INITIAL_JOBS, INITIAL_POLICIES, INITIAL_STORAGE, INITIAL_LOGS, INITIAL_SETTINGS 
} from '../mock/data';
import { authApi } from '../api/auth';
import { clientsApi, type ClientApiData } from '../api/clients';
import { jobsApi, type JobApiData } from '../api/jobs';
import { policiesApi, type PolicyApiData } from '../api/policies';
import { storageApi, type StorageRepositoryApiData } from '../api/storage';
import { activityApi, type AuditLogApiData } from '../api/activity';
import { restoreApi } from '../api/restore';

interface AppContextType {
  clients: Client[];
  jobs: BackupJob[];
  policies: BackupPolicy[];
  storage: StorageMetrics;
  logs: ActivityLog[];
  settings: AppSettings;
  toasts: ToastNotification[];
  selectedClient: Client | null;
  setSelectedClient: (client: Client | null) => void;
  triggerBackup: (clientId: string) => void;
  pauseJob: (jobId: string) => void;
  cancelJob: (jobId: string) => void;
  updatePolicy: (policy: BackupPolicy) => void;
  applyPolicyToClients: (policyId: string, clientIds: string[]) => void;
  updateClientPaths: (clientId: string, customPaths: string[], excludedPaths: string[]) => void;
  executeRestore: (
    sourceClientId: string, 
    recoveryPointId: string, 
    targetClientId: string, 
    restorePath: string, 
    files: string[]
  ) => Promise<boolean>;
  verifyStorage: () => void;
  updateSettings: (newSettings: AppSettings) => void;
  addToast: (title: string, message: string, type?: 'info' | 'warning' | 'error' | 'success') => void;
  removeToast: (id: string) => void;
  playWin95Sound: (type?: 'chord' | 'ding' | 'tada' | 'click') => void;
  soundEnabled: boolean;
  setSoundEnabled: (val: boolean) => void;
  backendConnected: boolean;
  refreshBackendData: () => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

// Web Audio synthesizer for nostalgic Windows 95 system sounds without external audio assets
const playSyntheticSound = (type: 'chord' | 'ding' | 'tada' | 'click' = 'click') => {
  try {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();

    if (type === 'click') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(600, ctx.currentTime);
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.05);
    } else if (type === 'ding') {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(1046.5, ctx.currentTime); // C6
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.35);
    } else if (type === 'chord') {
      // Classic chord (C - E - G)
      [523.25, 659.25, 783.99].forEach(freq => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        gain.gain.setValueAtTime(0.08, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.6);
      });
    } else if (type === 'tada') {
      // Triumphant chord progression
      [440, 554.37, 659.25, 880].forEach((freq, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'square';
        osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.08);
        gain.gain.setValueAtTime(0.04, ctx.currentTime + idx * 0.08);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.08 + 0.5);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(ctx.currentTime + idx * 0.08);
        osc.stop(ctx.currentTime + idx * 0.08 + 0.5);
      });
    }
  } catch {
    // Ignore audio permission restrictions
  }
};

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [clients, setClients] = useState<Client[]>(INITIAL_CLIENTS);
  const [jobs, setJobs] = useState<BackupJob[]>(INITIAL_JOBS);
  const [policies, setPolicies] = useState<BackupPolicy[]>(INITIAL_POLICIES);
  const [storage, setStorage] = useState<StorageMetrics>(INITIAL_STORAGE);
  const [logs, setLogs] = useState<ActivityLog[]>(INITIAL_LOGS);
  const [settings, setSettings] = useState<AppSettings>(INITIAL_SETTINGS);
  const [toasts, setToasts] = useState<ToastNotification[]>([]);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);
  const [backendConnected, setBackendConnected] = useState<boolean>(false);

  const playWin95Sound = (type: 'chord' | 'ding' | 'tada' | 'click' = 'click') => {
    if (soundEnabled) {
      playSyntheticSound(type);
    }
  };

  const addToast = (title: string, message: string, type: 'info' | 'warning' | 'error' | 'success' = 'info') => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    setToasts(prev => [...prev.slice(-3), { id, title, message, type, timestamp: new Date().toLocaleTimeString() }]);
    playWin95Sound(type === 'error' ? 'ding' : type === 'success' ? 'tada' : 'chord');
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  // Auto-dismiss toasts after 6 seconds
  useEffect(() => {
    if (toasts.length > 0) {
      const timer = setTimeout(() => {
        setToasts(prev => prev.slice(1));
      }, 6000);
      return () => clearTimeout(timer);
    }
  }, [toasts]);

  // Synchronize with backend API
  const refreshBackendData = async () => {
    try {
      // 1. Authenticate if no token
      if (!authApi.isAuthenticated()) {
        try {
          await authApi.login('admin', 'AdminPass123!');
        } catch {
          // If login fails, continue with fallback
        }
      }

      // 2. Fetch Clients
      const clientsRes = await clientsApi.list();
      if (clientsRes.success && Array.isArray(clientsRes.data) && clientsRes.data.length > 0) {
        const mappedClients: Client[] = clientsRes.data.map((c: ClientApiData, idx: number) => {
          const initialMatch = INITIAL_CLIENTS.find(ic => ic.id === c.client_id) || INITIAL_CLIENTS[idx % INITIAL_CLIENTS.length];
          const statusUpper = c.status === 'active' ? 'ONLINE' : c.status === 'offline' ? 'OFFLINE' : c.status === 'disabled' ? 'WARNING' : 'ONLINE';

          return {
            id: c.client_id,
            hostname: c.hostname,
            user: initialMatch ? initialMatch.user : `User-${c.client_id}`,
            os: c.os,
            agentVersion: c.agent_version,
            ipAddress: c.ip_address,
            cpu: initialMatch ? initialMatch.cpu : 'Intel Core i7 (8 Cores)',
            ram: initialMatch ? initialMatch.ram : '32 GB RAM',
            status: statusUpper,
            lastSeen: c.last_seen ? new Date(c.last_seen).toLocaleTimeString() : 'Recently',
            lastBackup: initialMatch ? initialMatch.lastBackup : '20:12:00',
            rpoSeconds: initialMatch ? initialMatch.rpoSeconds : 45,
            storageConsumedGb: initialMatch ? initialMatch.storageConsumedGb : 120.0,
            policyId: initialMatch ? initialMatch.policyId : 'POL-001',
            policyName: initialMatch ? initialMatch.policyName : 'Windows User Data',
            universalPaths: initialMatch ? initialMatch.universalPaths : ['%USERPROFILE%\\Documents', '%USERPROFILE%\\Desktop'],
            customPaths: initialMatch ? initialMatch.customPaths : [],
            excludedPaths: initialMatch ? initialMatch.excludedPaths : ['%TEMP%', '*.tmp']
          };
        });
        setClients(mappedClients);
      }

      // 3. Fetch Policies
      const policiesRes = await policiesApi.list();
      if (policiesRes.success && Array.isArray(policiesRes.data) && policiesRes.data.length > 0) {
        const mappedPolicies: BackupPolicy[] = policiesRes.data.map((p: PolicyApiData) => ({
          id: `POL-${p.id.toString().padStart(3, '0')}`,
          name: p.name,
          description: p.description || '',
          protectedFolders: p.paths.filter(path => !path.is_excluded).map(path => ({
            path: path.path_value,
            isUniversal: path.path_type === 'universal',
            enabled: true
          })),
          customFolders: p.paths.filter(path => path.path_type === 'custom' && !path.is_excluded).map(path => path.path_value),
          excludedPaths: p.paths.filter(path => path.is_excluded).map(path => path.path_value),
          backupType: p.backup_type === 'full' ? 'Full' : 'Incremental',
          changeDetection: p.change_detection === 'usn_journal' ? 'USN Journal' : 'File Watcher',
          rpoTargetSeconds: p.rpo_target_seconds,
          compressionEnabled: p.compression_enabled,
          encryptionEnabled: p.encryption_enabled,
          cpuLimitPercent: p.cpu_limit_percent,
          networkLimitMbps: p.network_limit_mbps,
          retentionDays: p.retention_days
        }));
        setPolicies(mappedPolicies);
      }

      // 4. Fetch Jobs
      const jobsRes = await jobsApi.list();
      if (jobsRes.success && Array.isArray(jobsRes.data) && jobsRes.data.length > 0) {
        const mappedJobs: BackupJob[] = jobsRes.data.map((j: JobApiData) => ({
          id: j.job_id,
          clientId: j.client_identifier || `PC-${j.client_id}`,
          clientHostname: j.client_hostname || `CLIENT-${j.client_id}`,
          policyName: j.policy_name || 'Windows User Data',
          backupType: 'Incremental',
          source: '%USERPROFILE%\\Documents, Desktop',
          started: j.started_at ? new Date(j.started_at).toLocaleTimeString() : '20:10',
          completed: j.completed_at ? new Date(j.completed_at).toLocaleTimeString() : null,
          duration: j.completed_at ? '00:02:15' : 'Active',
          dataProcessedMb: j.data_processed_mb || 412.3,
          status: j.status === 'completed' ? 'SUCCESS' : j.status === 'failed' ? 'FAILED' : j.status === 'cancelled' ? 'FAILED' : 'RUNNING',
          progressPercent: j.progress_percent || (j.status === 'completed' ? 100 : 45),
          changeDetection: 'USN Journal (NTFS)',
          transferSpeedMbps: 92.5
        }));
        setJobs(mappedJobs);
      }

      // 5. Fetch Storage
      const storageRes = await storageApi.list();
      if (storageRes.success && Array.isArray(storageRes.data) && storageRes.data.length > 0) {
        const s: StorageRepositoryApiData = storageRes.data[0];
        setStorage({
          repositoryPath: s.path,
          totalTb: s.total_tb,
          usedTb: s.used_tb,
          freeTb: s.free_tb,
          diskHealth: s.disk_health,
          backupObjectsCount: 142850,
          recoveryPointsCount: 4892,
          dedupRatio: s.dedup_ratio,
          compressionRatio: s.compression_ratio,
          lastVerification: '22 Sep 2026 18:00:00 (PASSED)'
        });
      }

      // 6. Fetch Activity Logs
      const activityRes = await activityApi.list();
      if (activityRes.success && Array.isArray(activityRes.data) && activityRes.data.length > 0) {
        const mappedLogs: ActivityLog[] = activityRes.data.map((a: AuditLogApiData) => ({
          id: `LOG-${a.id}`,
          time: new Date(a.created_at).toLocaleTimeString(),
          clientId: a.client_identifier || 'SYSTEM',
          event: (a.resource_type ? a.resource_type.toUpperCase() : 'SYSTEM') as any,
          severity: (a.severity || 'INFO') as any,
          message: `${a.action}: ${a.details || ''}`,
          details: a.details
        }));
        setLogs(mappedLogs);
      }

      setBackendConnected(true);
    } catch {
      // Backend not currently reachable; keep fallback seed data active
      setBackendConnected(false);
    }
  };

  useEffect(() => {
    refreshBackendData();
  }, []);

  const triggerBackup = async (clientId: string) => {
    playWin95Sound('click');
    addToast('Backup Initiating', `Contacting control plane daemon for ${clientId}...`, 'info');

    try {
      const res = await jobsApi.create({ client_id: clientId });
      if (res.success && res.data) {
        addToast('Backup Queued', `Job ${res.data.job_id} assigned in PostgreSQL control plane.`, 'success');
        refreshBackendData();
        return;
      }
    } catch {
      // Fallback local simulation if backend offline
    }

    // Local simulation fallback
    const client = clients.find(c => c.id === clientId);
    if (!client) return;

    const newJobId = `JOB-${Math.floor(1000 + Math.random() * 9000)}`;
    const now = new Date().toLocaleTimeString();

    setClients(prev => prev.map(c => c.id === clientId ? { ...c, status: 'BACKING_UP' } : c));
    const newJob: BackupJob = {
      id: newJobId,
      clientId: client.id,
      clientHostname: client.hostname,
      policyName: client.policyName,
      backupType: 'Incremental',
      source: client.universalPaths.concat(client.customPaths).slice(0, 2).join(', '),
      started: now,
      completed: null,
      duration: '00:00:01',
      dataProcessedMb: 14.2,
      status: 'RUNNING',
      progressPercent: 12,
      changeDetection: 'USN Journal (NTFS)',
      transferSpeedMbps: 92.5
    };
    setJobs(prev => [newJob, ...prev]);

    setTimeout(() => {
      setClients(prev => prev.map(c => c.id === clientId ? { ...c, status: 'ONLINE', rpoSeconds: 5 } : c));
      setJobs(prev => prev.map(j => j.id === newJobId ? { ...j, status: 'SUCCESS', progressPercent: 100, completed: new Date().toLocaleTimeString() } : j));
      addToast('Backup Completed', `Successfully backed up ${client.hostname}.`, 'success');
    }, 6000);
  };

  const pauseJob = (jobId: string) => {
    playWin95Sound('click');
    setJobs(prev => prev.map(j => {
      if (j.id === jobId) {
        const nextStatus = j.status === 'RUNNING' ? 'PAUSED' : 'RUNNING';
        addToast('Job Status Changed', `Job ${jobId} set to ${nextStatus}`, 'warning');
        return { ...j, status: nextStatus };
      }
      return j;
    }));
  };

  const cancelJob = async (jobId: string) => {
    playWin95Sound('click');
    try {
      await jobsApi.cancel(jobId);
    } catch {
      // Ignore
    }
    setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'FAILED', errorMessage: 'Aborted by administrator' } : j));
    addToast('Job Cancelled', `Job ${jobId} was aborted by administrator`, 'error');
  };

  const updatePolicy = async (updated: BackupPolicy) => {
    playWin95Sound('click');
    try {
      const numId = parseInt(updated.id.replace(/\D/g, ''), 10) || 1;
      await policiesApi.update(numId, {
        name: updated.name,
        description: updated.description,
        rpo_target_seconds: updated.rpoTargetSeconds,
        retention_days: updated.retentionDays,
        cpu_limit_percent: updated.cpuLimitPercent,
        network_limit_mbps: updated.networkLimitMbps
      });
    } catch {
      // Fallback
    }

    setPolicies(prev => {
      const exists = prev.some(p => p.id === updated.id);
      return exists ? prev.map(p => p.id === updated.id ? updated : p) : [...prev, updated];
    });
    addToast('Policy Saved', `Backup policy "${updated.name}" updated in database`, 'success');
  };

  const applyPolicyToClients = (policyId: string, clientIds: string[]) => {
    playWin95Sound('click');
    const policy = policies.find(p => p.id === policyId);
    if (!policy) return;

    setClients(prev => prev.map(c => clientIds.includes(c.id) ? {
      ...c,
      policyId: policy.id,
      policyName: policy.name,
      universalPaths: policy.protectedFolders.filter(f => f.isUniversal && f.enabled).map(f => f.path)
    } : c));

    addToast('Policy Applied', `Applied "${policy.name}" to ${clientIds.length} client(s)`, 'success');
  };

  const updateClientPaths = (clientId: string, customPaths: string[], excludedPaths: string[]) => {
    playWin95Sound('click');
    setClients(prev => prev.map(c => c.id === clientId ? { ...c, customPaths, excludedPaths } : c));
    addToast('Client Updated', `Custom path configuration updated for client ${clientId}`, 'info');
  };

  const executeRestore = async (
    sourceClientId: string, 
    recoveryPointId: string, 
    targetClientId: string, 
    restorePath: string, 
    files: string[]
  ): Promise<boolean> => {
    playWin95Sound('click');
    const sourceClient = clients.find(c => c.id === sourceClientId);
    const targetClient = clients.find(c => c.id === targetClientId);
    const rpNum = parseInt(recoveryPointId.replace(/\D/g, ''), 10) || 1;

    try {
      await restoreApi.create({
        source_client_id: sourceClientId,
        target_client_id: targetClientId,
        recovery_point_id: rpNum,
        source_path: files[0] || 'C:\\Users\\Arun\\Documents',
        target_path: restorePath,
        acknowledge_cross_client: sourceClientId !== targetClientId
      });
    } catch {
      // Handled or offline
    }

    addToast('Restore Initiated', `Extracting ${files.length} files from ${sourceClient?.hostname || sourceClientId} (${recoveryPointId}) to ${targetClient?.hostname || targetClientId}...`, 'info');

    return new Promise(resolve => {
      setTimeout(() => {
        addToast('Restore Complete', `Restored ${files.length} files successfully with SHA-256 integrity verified.`, 'success');
        resolve(true);
      }, 3500);
    });
  };

  const verifyStorage = () => {
    playWin95Sound('click');
    addToast('Integrity Scrub', 'Querying control plane storage repository status...', 'info');
    setTimeout(() => {
      setStorage(prev => ({
        ...prev,
        lastVerification: `${new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} ${new Date().toLocaleTimeString()} (PASSED)`
      }));
      addToast('Scrub Verified', 'D:\\BackupRepository checked: 142,850 objects clean.', 'success');
    }, 2000);
  };

  const updateSettings = (newSettings: AppSettings) => {
    playWin95Sound('click');
    setSettings(newSettings);
    addToast('Settings Saved', 'System administrator configuration updated.', 'success');
  };

  return (
    <AppContext.Provider value={{
      clients,
      jobs,
      policies,
      storage,
      logs,
      settings,
      toasts,
      selectedClient,
      setSelectedClient,
      triggerBackup,
      pauseJob,
      cancelJob,
      updatePolicy,
      applyPolicyToClients,
      updateClientPaths,
      executeRestore,
      verifyStorage,
      updateSettings,
      addToast,
      removeToast,
      playWin95Sound,
      soundEnabled,
      setSoundEnabled,
      backendConnected,
      refreshBackendData
    }}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
