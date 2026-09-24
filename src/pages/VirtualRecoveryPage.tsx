import React, { useState, useEffect } from 'react';
import { WinPanel } from '../components/win95/WinPanel';
import { WinButton } from '../components/win95/WinButton';
import { WinTable, type Column } from '../components/win95/WinTable';
import { WinBadge } from '../components/win95/WinBadge';
import { WinProgressBar } from '../components/win95/WinProgressBar';
import { WinDialog } from '../components/win95/WinDialog';
import { WinInput, WinSelect } from '../components/win95/WinFormControls';
import { RestoreArrowIcon, HardDriveIcon, ShieldCheckIcon } from '../components/win95/WinIcons';
import { useApp } from '../context/AppContext';
import {
  listVirtualRecoverySessions,
  createVirtualRecoverySession,
  prepareVirtualRecoverySession,
  mountVirtualRecoverySession,
  hydrateVirtualRecoverySession,
  pauseVirtualRecoverySession,
  resumeVirtualRecoverySession,
  validateVirtualRecoverySession,
  unmountVirtualRecoverySession,
  cancelVirtualRecoverySession,
  readLogicalPath,
  prefetchVirtualRecoverySession,
  getVirtualRecoveryMetrics,
  type VirtualRecoverySessionResponse,
  type VirtualRecoverySessionCreate,
  type VirtualRecoveryMetricsResponse,
  type VirtualRecoveryState
} from '../api/virtualRecovery';
import { getStorageTiers, type StorageTierResponse } from '../api/cloud';

export const VirtualRecoveryPage: React.FC = () => {
  const { addToast, playWin95Sound } = useApp();

  const [sessions, setSessions] = useState<VirtualRecoverySessionResponse[]>([]);
  const [selectedSession, setSelectedSession] = useState<VirtualRecoverySessionResponse | null>(null);
  const [metrics, setMetrics] = useState<VirtualRecoveryMetricsResponse | null>(null);
  const [cloudTiers, setCloudTiers] = useState<StorageTierResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [showCreateSession, setShowCreateSession] = useState<boolean>(false);
  const [showReadTester, setShowReadTester] = useState<boolean>(false);
  const [showPrefetchModal, setShowPrefetchModal] = useState<boolean>(false);
  const [showConfirmUnmount, setShowConfirmUnmount] = useState<boolean>(false);
  const [showConfirmCancel, setShowConfirmCancel] = useState<boolean>(false);

  // Form states
  const [createForm, setCreateForm] = useState<VirtualRecoverySessionCreate>({
    recovery_point_id: 1,
    target_path: 'C:\\RetroVault_VirtualMount',
    client_id: undefined,
    workload_id: '',
    cloud_tier_id: undefined,
    provider_type: 'LOCAL_VIRTUAL'
  });

  const [readPath, setReadPath] = useState<string>('boot/kernel.bin');
  const [readResult, setReadResult] = useState<string | null>(null);
  const [prefetchPathsText, setPrefetchPathsText] = useState<string>('boot/kernel.bin\napp/config.json');

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sessionsRes, tiersRes] = await Promise.all([
        listVirtualRecoverySessions(),
        getStorageTiers().catch(() => ({ success: false, data: [] }))
      ]);

      if (sessionsRes.success) {
        const list = sessionsRes.data || [];
        setSessions(list);
        if (selectedSession) {
          const updated = list.find(s => s.session_id === selectedSession.session_id);
          if (updated) setSelectedSession(updated);
        } else if (list.length > 0) {
          setSelectedSession(list[0]);
        }
      }
      if (tiersRes.success) {
        setCloudTiers(tiersRes.data || []);
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Failed to load virtual recovery sessions';
      setError(msg);
      addToast('Virtual Recovery Error', msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Poll metrics for selected session if active
  useEffect(() => {
    if (!selectedSession) return;
    const fetchMetrics = async () => {
      try {
        const res = await getVirtualRecoveryMetrics(selectedSession.session_id);
        if (res.success) setMetrics(res.data);
      } catch {
        // Silently catch polling error
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 4000);
    return () => clearInterval(interval);
  }, [selectedSession]);

  const handleCreateSession = async () => {
    if (!createForm.recovery_point_id || !createForm.target_path.trim()) {
      addToast('Validation', 'Recovery Point ID and Target Path are required', 'warning');
      return;
    }

    try {
      playWin95Sound('click');
      const res = await createVirtualRecoverySession({
        ...createForm,
        recovery_point_id: Number(createForm.recovery_point_id),
        client_id: createForm.client_id ? Number(createForm.client_id) : undefined,
        cloud_tier_id: createForm.cloud_tier_id ? Number(createForm.cloud_tier_id) : undefined,
        workload_id: createForm.workload_id?.trim() || undefined
      });

      if (res.success) {
        addToast('IVR Session Created', `Session '${res.data.session_id}' created in state CREATED`, 'info');
        setShowCreateSession(false);
        loadData();
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Failed to create session';
      addToast('Create Failed', msg, 'error');
    }
  };

  const handlePrepare = async (sessionId: string) => {
    setActionLoading(true);
    try {
      playWin95Sound('click');
      await prepareVirtualRecoverySession(sessionId);
      addToast('Session Prepared', 'Manifest scanned and hydration tracking items initialized', 'info');
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Prepare failed';
      addToast('Prepare Failed', msg, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleMount = async (sessionId: string) => {
    setActionLoading(true);
    try {
      playWin95Sound('click');
      await mountVirtualRecoverySession(sessionId);
      addToast('Session Mounted', 'Filesystem stubs exposed; dataset is now INSTANTLY readable on target', 'info');
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Mount failed';
      addToast('Mount Failed', msg, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleHydrate = async (sessionId: string) => {
    setActionLoading(true);
    try {
      playWin95Sound('click');
      const res = await hydrateVirtualRecoverySession(sessionId, 5);
      if (res.success) {
        addToast('Hydration Batch Processed', `Hydrated next batch: ${res.data?.hydrated_files || 0} files written`, 'info');
        loadData();
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Hydration failed';
      addToast('Hydration Error', msg, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handlePause = async (sessionId: string) => {
    setActionLoading(true);
    try {
      playWin95Sound('click');
      await pauseVirtualRecoverySession(sessionId);
      addToast('Hydration Paused', 'Background hydration suspended', 'info');
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Pause failed';
      addToast('Pause Error', msg, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async (sessionId: string) => {
    setActionLoading(true);
    try {
      playWin95Sound('click');
      await resumeVirtualRecoverySession(sessionId);
      addToast('Hydration Resumed', 'Resumed background hydration', 'info');
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Resume failed';
      addToast('Resume Error', msg, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleValidate = async (sessionId: string) => {
    setActionLoading(true);
    try {
      playWin95Sound('click');
      const res = await validateVirtualRecoverySession(sessionId);
      if (res.success && res.data?.valid) {
        addToast('Workload Validated', `Application health check PASSED (latency: ${res.data?.latency_ms?.toFixed(1) || 0}ms)`, 'info');
      } else {
        addToast('Validation Warning', res.data?.error || 'Validation did not pass completely', 'warning');
      }
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Validation failed';
      addToast('Validation Error', msg, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleUnmount = async () => {
    if (!selectedSession) return;
    setActionLoading(true);
    try {
      playWin95Sound('click');
      await unmountVirtualRecoverySession(selectedSession.session_id);
      addToast('Session Unmounted', 'Virtual recovery session unmounted and RP protection safely released', 'info');
      setShowConfirmUnmount(false);
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Unmount failed';
      addToast('Unmount Error', msg, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!selectedSession) return;
    setActionLoading(true);
    try {
      playWin95Sound('click');
      await cancelVirtualRecoverySession(selectedSession.session_id);
      addToast('Session Cancelled', 'Session aborted and temporary resources cleaned', 'info');
      setShowConfirmCancel(false);
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Cancel failed';
      addToast('Cancel Error', msg, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleExecuteReadTest = async () => {
    if (!selectedSession || !readPath.trim()) return;
    try {
      playWin95Sound('click');
      const res = await readLogicalPath(selectedSession.session_id, readPath.trim());
      if (res.success) {
        setReadResult(
          `SUCCESS: Read ${res.data.bytes_returned} bytes from source [${res.data.source}] (SHA-256 Verified: ${res.data.checksum_verified})`
        );
        addToast('Read-on-Demand Verified', `Fetched '${readPath}' from ${res.data.source}`, 'info');
        loadData();
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Read failed';
      setReadResult(`ERROR: ${msg}`);
      addToast('Read Failed', msg, 'error');
    }
  };

  const handleExecutePrefetch = async () => {
    if (!selectedSession) return;
    const paths = prefetchPathsText
      .split(/[\n,]+/)
      .map(p => p.trim())
      .filter(p => p.length > 0);

    if (paths.length === 0) {
      addToast('Prefetch Validation', 'Provide at least one relative file path to prefetch', 'warning');
      return;
    }

    try {
      playWin95Sound('click');
      const res = await prefetchVirtualRecoverySession(selectedSession.session_id, paths);
      if (res.success) {
        addToast(
          'Prefetch Complete',
          `Pre-cached: ${res.data.prefetched_count}, Failed: ${res.data.failed_count}`,
          res.data.failed_count === 0 ? 'info' : 'warning'
        );
        setShowPrefetchModal(false);
        loadData();
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Prefetch failed';
      addToast('Prefetch Error', msg, 'error');
    }
  };

  const getStatusBadge = (state: VirtualRecoveryState) => {
    switch (state) {
      case 'READY':
      case 'COMPLETED':
        return <WinBadge type="job" status="SUCCESS" label={state} />;
      case 'MOUNTING':
      case 'PREPARING':
      case 'HYDRATING':
      case 'COMPLETING':
        return <WinBadge type="job" status="RUNNING" label={state} />;
      case 'PAUSED':
      case 'DEGRADED':
        return <WinBadge type="job" status="PAUSED" label={state} />;
      case 'FAILED':
      case 'CANCELLED':
        return <WinBadge type="job" status="FAILED" label={state} />;
      default:
        return <WinBadge type="custom" label={state} />;
    }
  };

  const sessionColumns: Column<VirtualRecoverySessionResponse>[] = [
    {
      key: 'session_id',
      header: 'Session ID',
      width: '130px',
      sortable: true,
      render: (s) => (
        <span className="font-mono font-bold text-black flex items-center gap-1">
          <RestoreArrowIcon size={13} />
          <span>{s.session_id}</span>
        </span>
      )
    },
    {
      key: 'recovery_point_id',
      header: 'Target RP / Client',
      width: '130px',
      render: (s) => (
        <div className="text-[10px]">
          <span className="font-mono font-bold text-[#000080]">RP-{s.recovery_point_id}</span>
          <div className="text-[#666]">Client: #{s.client_id}</div>
        </div>
      )
    },
    {
      key: 'target_path',
      header: 'Virtual Mount Path',
      render: (s) => (
        <div className="font-mono text-[11px] truncate max-w-[200px]" title={s.target_path}>
          {s.target_path}
        </div>
      )
    },
    {
      key: 'state',
      header: 'Lifecycle State',
      width: '110px',
      sortable: true,
      render: (s) => getStatusBadge(s.state)
    },
    {
      key: 'hydration_status',
      header: 'Hydration',
      width: '130px',
      render: (s) => {
        const pct = s.total_bytes > 0 ? Math.round((s.hydrated_bytes / s.total_bytes) * 100) : 0;
        return (
          <div className="flex flex-col gap-0.5">
            <div className="flex justify-between text-[9px] font-mono">
              <span>{s.hydration_status}</span>
              <span>{pct}%</span>
            </div>
            <WinProgressBar percent={pct} />
          </div>
        );
      }
    },
    {
      key: 'time_to_first_access_ms',
      header: 'TTFA (Observed)',
      width: '110px',
      render: (s) => (
        <span className="font-mono text-[10px] text-[#008800] font-bold">
          {s.time_to_first_access_ms ? `${s.time_to_first_access_ms.toFixed(1)} ms` : '--'}
        </span>
      )
    },
    {
      key: 'session_id',
      header: 'Actions',
      width: '90px',
      render: (s) => (
        <WinButton
          onClick={() => setSelectedSession(s)}
          className={`text-[10px] py-0.5 px-2 ${selectedSession?.session_id === s.session_id ? 'win-inset font-bold' : ''}`}
        >
          Inspect
        </WinButton>
      )
    }
  ];

  const currentProgressPct = selectedSession && selectedSession.total_bytes > 0
    ? Math.round((selectedSession.hydrated_bytes / selectedSession.total_bytes) * 100)
    : 0;

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-y-auto">
      {/* Top Action Toolbar */}
      <div className="win-outset px-3 py-1.5 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-2">
          <RestoreArrowIcon size={18} />
          <div>
            <h1 className="text-[13px] font-bold text-black m-0 leading-tight">
              RetroVault V12 — Instant Virtual Recovery (IVR) Console
            </h1>
            <p className="text-[10px] text-[#505050] m-0">
              Immediate read-on-demand mounts with asynchronous background hydration
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <WinButton onClick={() => setShowCreateSession(true)} isDefault className="text-[11px] font-bold">
            + New Virtual Recovery Session
          </WinButton>
          <WinButton onClick={loadData} className="text-[11px]">
            Refresh
          </WinButton>
        </div>
      </div>

      {error && (
        <div className="win-inset bg-[#ffeeee] p-2 text-[#aa0000] text-[11px] font-mono flex items-center justify-between">
          <span>Error: {error}</span>
          <WinButton onClick={loadData} className="text-[10px]">Retry</WinButton>
        </div>
      )}

      {/* Sessions Table Panel */}
      <WinPanel title="Active Virtual Recovery Sessions">
        <div className="text-[11px] text-[#333] mb-2 leading-relaxed">
          Instant Virtual Recovery allows an immutable Recovery Point to become immediately readable on a recovery target without waiting for the full dataset to be copied first. Read requests lazily resolve to Local CAS or Cloud Storage Tiers with SHA-256 verification while background hydration restores data in parallel.
        </div>

        <div className="min-h-[180px]">
          {loading ? (
            <div className="win-inset bg-white p-4 text-center text-[11px] text-[#666]">
              Loading virtual recovery sessions from control plane...
            </div>
          ) : (
            <WinTable<VirtualRecoverySessionResponse>
              columns={sessionColumns}
              data={sessions}
              keyExtractor={(s) => s.session_id}
              emptyText="No virtual recovery sessions found. Click '+ New Virtual Recovery Session' to mount a Recovery Point."
            />
          )}
        </div>
      </WinPanel>

      {/* Selected Session Inspector */}
      {selectedSession ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
          {/* Column 1: Controls & Lifecycle */}
          <WinPanel title={`Session Controls [${selectedSession.session_id}]`}>
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-[#444]">Current State:</span>
                {getStatusBadge(selectedSession.state)}
              </div>

              <div className="text-[11px] font-mono bg-white win-inset p-1.5 flex flex-col gap-0.5">
                <div><span className="font-bold text-[#555]">Target Path:</span> {selectedSession.target_path}</div>
                <div><span className="font-bold text-[#555]">Recovery Point:</span> #{selectedSession.recovery_point_id}</div>
                <div><span className="font-bold text-[#555]">Client ID:</span> #{selectedSession.client_id}</div>
                {selectedSession.workload_id && (
                  <div><span className="font-bold text-[#555]">Workload:</span> {selectedSession.workload_id}</div>
                )}
                {selectedSession.cloud_tier_id && (
                  <div><span className="font-bold text-[#555]">Cloud Fallback Tier:</span> #{selectedSession.cloud_tier_id}</div>
                )}
              </div>

              {/* State-Aware Action Toolbar */}
              <div className="font-bold text-[10px] text-black uppercase mt-1">Lifecycle Operations:</div>
              <div className="grid grid-cols-2 gap-1.5">
                {selectedSession.state === 'CREATED' && (
                  <WinButton
                    onClick={() => handlePrepare(selectedSession.session_id)}
                    disabled={actionLoading}
                    isDefault
                    className="text-[11px] font-bold"
                  >
                    Prepare Manifest
                  </WinButton>
                )}

                {(selectedSession.state === 'CREATED' || selectedSession.state === 'PREPARING') && (
                  <WinButton
                    onClick={() => handleMount(selectedSession.session_id)}
                    disabled={actionLoading}
                    className="text-[11px] font-bold"
                  >
                    Mount Target
                  </WinButton>
                )}

                {(selectedSession.state === 'READY' || selectedSession.state === 'PAUSED') && (
                  <WinButton
                    onClick={() => handleHydrate(selectedSession.session_id)}
                    disabled={actionLoading}
                    className="text-[11px] font-bold text-[#008000]"
                  >
                    Hydrate Batch
                  </WinButton>
                )}

                {selectedSession.state === 'HYDRATING' && (
                  <WinButton
                    onClick={() => handlePause(selectedSession.session_id)}
                    disabled={actionLoading}
                    className="text-[11px] font-bold text-[#800080]"
                  >
                    Pause Hydration
                  </WinButton>
                )}

                {selectedSession.state === 'PAUSED' && (
                  <WinButton
                    onClick={() => handleResume(selectedSession.session_id)}
                    disabled={actionLoading}
                    className="text-[11px] font-bold text-[#000080]"
                  >
                    Resume Hydration
                  </WinButton>
                )}

                {(selectedSession.state === 'READY' || selectedSession.state === 'HYDRATING') && (
                  <WinButton
                    onClick={() => handleValidate(selectedSession.session_id)}
                    disabled={actionLoading}
                    className="text-[11px]"
                  >
                    Validate App
                  </WinButton>
                )}

                {(selectedSession.state === 'READY' || selectedSession.state === 'HYDRATING') && (
                  <WinButton
                    onClick={() => setShowPrefetchModal(true)}
                    className="text-[11px]"
                  >
                    Prefetch...
                  </WinButton>
                )}

                {(selectedSession.state === 'READY' || selectedSession.state === 'HYDRATING') && (
                  <WinButton
                    onClick={() => setShowReadTester(true)}
                    className="text-[11px]"
                  >
                    Read Tester
                  </WinButton>
                )}

                <WinButton
                  onClick={() => setShowConfirmUnmount(true)}
                  disabled={actionLoading || selectedSession.state === 'COMPLETED'}
                  className="text-[11px] text-[#aa0000]"
                >
                  Unmount...
                </WinButton>

                {selectedSession.state !== 'COMPLETED' && selectedSession.state !== 'CANCELLED' && (
                  <WinButton
                    onClick={() => setShowConfirmCancel(true)}
                    disabled={actionLoading}
                    className="text-[11px] text-[#800000]"
                  >
                    Cancel Session
                  </WinButton>
                )}
              </div>
            </div>
          </WinPanel>

          {/* Column 2: Hydration Progress */}
          <WinPanel title="Background Resumable Hydration">
            <div className="flex flex-col gap-2.5">
              <div>
                <div className="flex justify-between text-[11px] font-mono mb-1 font-bold">
                  <span>Progress ({selectedSession.hydration_status})</span>
                  <span>{currentProgressPct}%</span>
                </div>
                <WinProgressBar percent={currentProgressPct} />
              </div>

              <div className="win-inset bg-white p-2 text-[11px] font-mono flex flex-col gap-1">
                <div className="flex justify-between">
                  <span>Hydrated Files:</span>
                  <span className="font-bold">{selectedSession.hydrated_files} / {selectedSession.total_files}</span>
                </div>
                <div className="flex justify-between">
                  <span>Hydrated Bytes:</span>
                  <span className="font-bold">
                    {(selectedSession.hydrated_bytes / (1024 * 1024)).toFixed(2)} MB / {(selectedSession.total_bytes / (1024 * 1024)).toFixed(2)} MB
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Transfer Speed:</span>
                  <span className="font-bold text-[#006600]">
                    {(selectedSession.hydration_speed_bps / (1024 * 1024)).toFixed(2)} MB/s
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Estimated ETA:</span>
                  <span className="font-bold">
                    {selectedSession.hydration_eta_seconds != null ? `${selectedSession.hydration_eta_seconds.toFixed(0)} seconds` : 'Calculating...'}
                  </span>
                </div>
              </div>

              <div className="text-[10px] text-[#555] italic">
                Hydration restores dataset files to the physical target in the background without locking user reads.
              </div>
            </div>
          </WinPanel>

          {/* Column 3: Telemetry & RTO Metrics */}
          <WinPanel title="RTO & Telemetry (Observed)">
            <div className="flex flex-col gap-2">
              <div className="win-inset bg-white p-2 text-[11px] font-mono flex flex-col gap-1">
                <div className="flex justify-between">
                  <span>Time to First Access:</span>
                  <span className="font-bold text-[#008800]">
                    {selectedSession.time_to_first_access_ms ? `${selectedSession.time_to_first_access_ms.toFixed(2)} ms` : '--'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Time to App Ready:</span>
                  <span className="font-bold text-[#000080]">
                    {selectedSession.time_to_app_ready_ms ? `${selectedSession.time_to_app_ready_ms.toFixed(2)} ms` : '--'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Time to Full Hydration:</span>
                  <span className="font-bold text-[#800080]">
                    {selectedSession.time_to_full_hydration_ms ? `${(selectedSession.time_to_full_hydration_ms / 1000).toFixed(2)} s` : '--'}
                  </span>
                </div>
                <div className="flex justify-between pt-1 border-t border-[#dfdfdf]">
                  <span>Cache Hits / Misses:</span>
                  <span className="font-bold">{metrics?.cache_hits || selectedSession.cache_hits} / {metrics?.cache_misses || selectedSession.cache_misses}</span>
                </div>
                <div className="flex justify-between">
                  <span>Cache Hit Ratio:</span>
                  <span className="font-bold text-[#008800]">
                    {metrics ? `${(metrics.cache_hit_ratio * 100).toFixed(1)}%` : '--'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Total Read Requests:</span>
                  <span className="font-bold">{selectedSession.read_requests_count}</span>
                </div>
              </div>

              <div className="text-[9px] text-[#777] bg-[#efefef] p-1.5 win-inset">
                * Note: Telemetry reflects measured values from the active virtual recovery engine and in-memory bounded LRU block cache.
              </div>
            </div>
          </WinPanel>
        </div>
      ) : (
        <div className="win-inset bg-white p-4 text-center text-[11px] text-[#777]">
          Select a virtual recovery session above to view live telemetry and lifecycle controls.
        </div>
      )}

      {/* Dialog: Create Session */}
      <WinDialog
        isOpen={showCreateSession}
        onClose={() => setShowCreateSession(false)}
        title="Initialize Virtual Recovery Session"
        icon={<RestoreArrowIcon size={16} />}
        width={500}
        onOk={handleCreateSession}
        okText="Create Session"
      >
        <div className="flex flex-col gap-2.5">
          <WinInput
            label="Recovery Point ID *"
            type="number"
            min="1"
            value={createForm.recovery_point_id}
            onChange={(e) => setCreateForm({ ...createForm, recovery_point_id: parseInt(e.target.value) || 1 })}
          />

          <WinInput
            label="Target Mount Directory Path *"
            value={createForm.target_path}
            onChange={(e) => setCreateForm({ ...createForm, target_path: e.target.value })}
            placeholder="C:\RetroVault_VirtualMount or /mnt/recovery"
          />

          <WinSelect
            label="Cloud Fallback Storage Tier (optional)"
            value={createForm.cloud_tier_id || ''}
            onChange={(e) => setCreateForm({ ...createForm, cloud_tier_id: e.target.value ? parseInt(e.target.value) : undefined })}
          >
            <option value="">-- No Cloud Fallback (Local CAS Only) --</option>
            {cloudTiers.map(t => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.bucket})
              </option>
            ))}
          </WinSelect>

          <WinInput
            label="Workload Application Identifier (optional)"
            value={createForm.workload_id || ''}
            onChange={(e) => setCreateForm({ ...createForm, workload_id: e.target.value })}
            placeholder="e.g. mssql-instance-01"
          />

          <WinSelect
            label="Virtual Recovery Provider"
            value={createForm.provider_type}
            onChange={(e) => setCreateForm({ ...createForm, provider_type: e.target.value })}
          >
            <option value="LOCAL_VIRTUAL">LOCAL_VIRTUAL (Filesystem Stubs)</option>
            <option value="MOCK">MOCK (Deterministic Test Harness)</option>
          </WinSelect>

          <div className="text-[10px] text-[#444] bg-[#fdfdfd] win-inset p-2">
            <strong>Active Recovery Protection:</strong> The selected Recovery Point and its dependent CAS objects will be automatically locked against GC and retention pruning until the session is unmounted.
          </div>
        </div>
      </WinDialog>

      {/* Dialog: On-Demand Read File Tester */}
      <WinDialog
        isOpen={showReadTester}
        onClose={() => {
          setShowReadTester(false);
          setReadResult(null);
        }}
        title={`Read-on-Demand Tester [${selectedSession?.session_id || ''}]`}
        icon={<RestoreArrowIcon size={16} />}
        width={480}
        onOk={handleExecuteReadTest}
        okText="Read File"
      >
        <div className="flex flex-col gap-2">
          <div className="text-[11px] text-[#444]">
            Test on-demand block resolution through the CAS / Cloud Tier fallback pipeline:
          </div>

          <WinInput
            label="Relative File Path"
            value={readPath}
            onChange={(e) => setReadPath(e.target.value)}
            placeholder="boot/kernel.bin"
          />

          {readResult && (
            <div className="win-inset bg-white p-2 font-mono text-[10px] whitespace-pre-wrap break-all max-h-[140px] overflow-y-auto">
              {readResult}
            </div>
          )}
        </div>
      </WinDialog>

      {/* Dialog: Controlled Prefetch */}
      <WinDialog
        isOpen={showPrefetchModal}
        onClose={() => setShowPrefetchModal(false)}
        title="Controlled File Prefetch"
        icon={<HardDriveIcon size={16} />}
        width={480}
        onOk={handleExecutePrefetch}
        okText="Prefetch into Cache"
      >
        <div className="flex flex-col gap-2">
          <div className="text-[11px] text-[#444]">
            Pre-cache critical startup files (e.g. boot files, configuration, or database headers) to minimize latency on first application start:
          </div>

          <textarea
            className="win-inset p-2 font-mono text-[11px] bg-white h-24 focus:outline-none"
            value={prefetchPathsText}
            onChange={(e) => setPrefetchPathsText(e.target.value)}
          />

          <div className="text-[10px] text-[#666] italic">
            Enter relative file paths, one per line.
          </div>
        </div>
      </WinDialog>

      {/* Dialog: Confirm Unmount */}
      <WinDialog
        isOpen={showConfirmUnmount}
        onClose={() => setShowConfirmUnmount(false)}
        title="Confirm Session Unmount"
        icon={<ShieldCheckIcon size={16} />}
        width={420}
        onOk={handleUnmount}
        okText="Unmount & Release Protection"
      >
        <div className="text-[11px] text-[#aa0000] font-bold mb-2">
          Warning: Unmounting will terminate virtual access to this dataset!
        </div>
        <div className="text-[11px] text-[#333]">
          Active recovery protection on Recovery Point #{selectedSession?.recovery_point_id} will be safely released. Are you sure you wish to proceed?
        </div>
      </WinDialog>

      {/* Dialog: Confirm Cancel */}
      <WinDialog
        isOpen={showConfirmCancel}
        onClose={() => setShowConfirmCancel(false)}
        title="Confirm Session Cancellation"
        icon={<ShieldCheckIcon size={16} />}
        width={420}
        onOk={handleCancel}
        okText="Cancel Session"
      >
        <div className="text-[11px] text-[#aa0000] font-bold mb-2">
          Warning: Cancelling will abort any in-progress hydration!
        </div>
        <div className="text-[11px] text-[#333]">
          Incomplete files on the target directory will be purged and session state will transition to CANCELLED.
        </div>
      </WinDialog>
    </div>
  );
};

export default VirtualRecoveryPage;
