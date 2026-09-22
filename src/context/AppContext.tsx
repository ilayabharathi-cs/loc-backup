import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { 
  Client, BackupJob, BackupPolicy, StorageMetrics, ActivityLog, AppSettings, ToastNotification 
} from '../types';
import { 
  INITIAL_CLIENTS, INITIAL_JOBS, INITIAL_POLICIES, INITIAL_STORAGE, INITIAL_LOGS, INITIAL_SETTINGS 
} from '../mock/data';

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
    // Ignore audio permission or autoplay restrictions
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

  // Simulate active running job progress
  useEffect(() => {
    const interval = setInterval(() => {
      setJobs(prevJobs => 
        prevJobs.map(job => {
          if (job.status === 'RUNNING') {
            const currentProg = job.progressPercent || 50;
            if (currentProg >= 98) {
              // Complete job
              const now = new Date().toLocaleTimeString();
              return {
                ...job,
                status: 'SUCCESS',
                progressPercent: 100,
                completed: now,
                duration: '00:02:18'
              };
            }
            return {
              ...job,
              progressPercent: Math.min(100, currentProg + Math.floor(Math.random() * 8) + 4),
              dataProcessedMb: +(job.dataProcessedMb + (Math.random() * 25)).toFixed(1)
            };
          }
          return job;
        })
      );
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const triggerBackup = (clientId: string) => {
    const client = clients.find(c => c.id === clientId);
    if (!client) return;

    playWin95Sound('click');
    const newJobId = `JOB-${Math.floor(1000 + Math.random() * 9000)}`;
    const now = new Date().toLocaleTimeString();

    // Update client status
    setClients(prev => prev.map(c => c.id === clientId ? { ...c, status: 'BACKING_UP' } : c));

    // Create job
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

    // Add log
    const newLog: ActivityLog = {
      id: `LOG-${Date.now()}`,
      time: now,
      clientId: client.id,
      event: 'BACKUP',
      severity: 'INFO',
      message: `Manual backup initiated for ${client.hostname} (${client.id})`,
      details: `Policy: ${client.policyName}. USN journal change tracking active.`
    };
    setLogs(prev => [newLog, ...prev]);

    addToast('Backup Started', `Initiated incremental backup for ${client.hostname} (${client.id})`, 'info');

    // Simulate completion after 8 seconds
    setTimeout(() => {
      setClients(prev => prev.map(c => c.id === clientId ? { 
        ...c, 
        status: 'ONLINE', 
        lastBackup: new Date().toLocaleTimeString(),
        rpoSeconds: 5,
        storageConsumedGb: +(c.storageConsumedGb + 0.35).toFixed(1)
      } : c));
      
      setJobs(prev => prev.map(j => j.id === newJobId ? {
        ...j,
        status: 'SUCCESS',
        progressPercent: 100,
        completed: new Date().toLocaleTimeString(),
        duration: '00:01:08'
      } : j));

      addToast('Backup Completed', `Successfully backed up ${client.hostname}. 0 errors, 42 files protected.`, 'success');
    }, 8000);
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

  const cancelJob = (jobId: string) => {
    playWin95Sound('click');
    setJobs(prev => prev.map(j => {
      if (j.id === jobId) {
        addToast('Job Cancelled', `Job ${jobId} was aborted by administrator`, 'error');
        return { ...j, status: 'FAILED', errorMessage: 'Aborted by administrator' };
      }
      return j;
    }));
  };

  const updatePolicy = (updated: BackupPolicy) => {
    playWin95Sound('click');
    setPolicies(prev => {
      const exists = prev.some(p => p.id === updated.id);
      if (exists) {
        return prev.map(p => p.id === updated.id ? updated : p);
      }
      return [...prev, updated];
    });

    const now = new Date().toLocaleTimeString();
    setLogs(prev => [
      {
        id: `LOG-${Date.now()}`,
        time: now,
        clientId: 'SYSTEM',
        event: 'POLICY',
        severity: 'INFO',
        message: `Policy "${updated.name}" updated`,
        details: `RPO target: ${updated.rpoTargetSeconds}s, Retention: ${updated.retentionDays}d, Compression: ${updated.compressionEnabled}`
      },
      ...prev
    ]);

    addToast('Policy Saved', `Backup policy "${updated.name}" has been updated`, 'success');
  };

  const applyPolicyToClients = (policyId: string, clientIds: string[]) => {
    playWin95Sound('click');
    const policy = policies.find(p => p.id === policyId);
    if (!policy) return;

    setClients(prev => prev.map(c => {
      if (clientIds.includes(c.id)) {
        return {
          ...c,
          policyId: policy.id,
          policyName: policy.name,
          universalPaths: policy.protectedFolders.filter(f => f.isUniversal && f.enabled).map(f => f.path)
        };
      }
      return c;
    }));

    addToast('Policy Applied', `Applied "${policy.name}" to ${clientIds.length} client(s)`, 'success');
  };

  const updateClientPaths = (clientId: string, customPaths: string[], excludedPaths: string[]) => {
    playWin95Sound('click');
    setClients(prev => prev.map(c => {
      if (c.id === clientId) {
        return { ...c, customPaths, excludedPaths };
      }
      return c;
    }));
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
    const now = new Date().toLocaleTimeString();
    const sourceClient = clients.find(c => c.id === sourceClientId);
    const targetClient = clients.find(c => c.id === targetClientId);

    const log: ActivityLog = {
      id: `LOG-${Date.now()}`,
      time: now,
      clientId: targetClientId,
      event: 'RESTORE',
      severity: 'INFO',
      message: `Restore started: ${files.length} items from ${sourceClient?.hostname || sourceClientId} (${recoveryPointId}) to ${targetClient?.hostname || targetClientId}`,
      details: `Destination: ${restorePath}`
    };
    setLogs(prev => [log, ...prev]);

    addToast('Restore Initiated', `Extracting ${files.length} files to ${targetClient?.hostname}...`, 'info');

    // Simulate completion
    return new Promise(resolve => {
      setTimeout(() => {
        addToast('Restore Complete', `Restored ${files.length} files successfully with SHA-256 integrity verified.`, 'success');
        resolve(true);
      }, 4000);
    });
  };

  const verifyStorage = () => {
    playWin95Sound('click');
    addToast('Integrity Scrub', 'Verifying repository block hashes against catalog...', 'info');
    setTimeout(() => {
      setStorage(prev => ({
        ...prev,
        lastVerification: `${new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} ${new Date().toLocaleTimeString()} (PASSED)`
      }));
      addToast('Scrub Verified', 'D:\\BackupRepository checked: 142,850 objects clean.', 'success');
    }, 2500);
  };

  const updateSettings = (newSettings: AppSettings) => {
    playWin95Sound('click');
    setSettings(newSettings);
    addToast('Settings Saved', 'System administrator configuration saved to local storage.', 'success');
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
      setSoundEnabled
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
