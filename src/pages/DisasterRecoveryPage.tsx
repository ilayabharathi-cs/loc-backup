import React, { useState, useEffect } from 'react';
import { WinPanel } from '../components/win95/WinPanel';
import { WinButton } from '../components/win95/WinButton';
import { WinTable, type Column } from '../components/win95/WinTable';
import { WinBadge } from '../components/win95/WinBadge';
import { WinDialog } from '../components/win95/WinDialog';
import { WinInput } from '../components/win95/WinFormControls';
import { ShieldCheckIcon, RestoreArrowIcon } from '../components/win95/WinIcons';
import { useApp } from '../context/AppContext';
import {
  getDrReadiness,
  listDrTests,
  runAutomatedDrTest,
  type DrReadinessResponse,
  type DrTestResponse
} from '../api/dr';

export const DisasterRecoveryPage: React.FC = () => {
  const { addToast, playWin95Sound } = useApp();

  const [readiness, setReadiness] = useState<DrReadinessResponse | null>(null);
  const [tests, setTests] = useState<DrTestResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [drillLoading, setDrillLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [showRunDrillModal, setShowRunDrillModal] = useState<boolean>(false);
  const [selectedRpId, setSelectedRpId] = useState<string>('');

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [readinessRes, testsRes] = await Promise.all([
        getDrReadiness(),
        listDrTests(50)
      ]);
      if (readinessRes.success) setReadiness(readinessRes.data);
      if (testsRes.success) setTests(testsRes.data || []);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Failed to load disaster recovery data';
      setError(msg);
      addToast('Disaster Recovery Error', msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleExecuteDrill = async () => {
    setDrillLoading(true);
    try {
      playWin95Sound('click');
      const rpId = selectedRpId.trim() ? parseInt(selectedRpId.trim()) : null;
      const res = await runAutomatedDrTest(rpId);
      if (res.success) {
        addToast(
          'DR Drill Completed',
          `Drill ${res.data.test_id}: Result=${res.data.result} (${res.data.files_verified}/${res.data.files_tested} verified in ${res.data.duration_seconds.toFixed(2)}s)`,
          res.data.result === 'PASSED' ? 'info' : 'warning'
        );
        setShowRunDrillModal(false);
        setSelectedRpId('');
        loadData();
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'DR drill failed';
      addToast('Drill Error', msg, 'error');
    } finally {
      setDrillLoading(false);
    }
  };

  const getResultBadge = (result: string) => {
    if (result === 'PASSED') return <WinBadge type="job" status="SUCCESS" label="PASSED" />;
    if (result === 'PARTIAL') return <WinBadge type="job" status="PAUSED" label="PARTIAL" />;
    if (result === 'FAILED') return <WinBadge type="job" status="FAILED" label="FAILED" />;
    return <WinBadge type="custom" label={result} />;
  };

  const testColumns: Column<DrTestResponse>[] = [
    {
      key: 'test_id',
      header: 'Drill ID',
      width: '130px',
      sortable: true,
      render: (t) => (
        <span className="font-mono font-bold text-black flex items-center gap-1">
          <ShieldCheckIcon size={13} />
          <span>{t.test_id}</span>
        </span>
      )
    },
    {
      key: 'recovery_point_id',
      header: 'Recovery Point',
      width: '120px',
      render: (t) => (
        <span className="font-mono font-bold text-[#000080]">RP-{t.recovery_point_id}</span>
      )
    },
    {
      key: 'result',
      header: 'Result',
      width: '100px',
      sortable: true,
      render: (t) => getResultBadge(t.result)
    },
    {
      key: 'files_verified',
      header: 'Verified / Tested',
      width: '140px',
      render: (t) => (
        <div className="font-mono text-[11px]">
          <span className="font-bold text-[#006600]">{t.files_verified}</span> / <span>{t.files_tested} files</span>
          {t.failures > 0 && <span className="text-[#aa0000] ml-1">({t.failures} fail)</span>}
        </div>
      )
    },
    {
      key: 'bytes_tested',
      header: 'Bytes Checked',
      width: '120px',
      render: (t) => (
        <span className="font-mono text-[11px] text-[#555]">
          {(t.bytes_tested / (1024 * 1024)).toFixed(2)} MB
        </span>
      )
    },
    {
      key: 'duration_seconds',
      header: 'Duration',
      width: '90px',
      render: (t) => (
        <span className="font-mono text-[11px] text-black">
          {t.duration_seconds.toFixed(2)}s
        </span>
      )
    },
    {
      key: 'started_at',
      header: 'Executed At',
      render: (t) => (
        <span className="text-[10px] font-mono text-[#555]">
          {new Date(t.started_at).toLocaleString()}
        </span>
      )
    }
  ];

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-y-auto">
      {/* Top Action Toolbar */}
      <div className="win-outset px-3 py-1.5 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-2">
          <ShieldCheckIcon size={18} />
          <div>
            <h1 className="text-[13px] font-bold text-black m-0 leading-tight">
              RetroVault — Disaster Recovery & Sandbox Verification
            </h1>
            <p className="text-[10px] text-[#505050] m-0">
              Automated non-destructive sandbox restoration drills and RPO compliance validation
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <WinButton onClick={() => setShowRunDrillModal(true)} isDefault className="text-[11px] font-bold">
            + Execute Automated DR Drill
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

      {/* Main DR Panel */}
      <WinPanel title="Disaster Recovery Readiness & History">
        <div className="text-[11px] text-[#333] mb-2 leading-relaxed">
          RetroVault DR Verification performs automated, non-destructive restore drills in temporary sandboxes. Every file in the target Recovery Point is decompressed from CAS, verified for SHA-256 integrity against the manifest, and cleaned up with zero disk leakage.
        </div>

        {/* Readiness Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
          <div className="win-inset p-2 bg-white flex flex-col gap-1">
            <span className="text-[10px] text-[#666] font-bold uppercase">Overall DR Status</span>
            <div className="text-base font-bold flex items-center gap-1">
              <span className={`w-2.5 h-2.5 rounded-full ${readiness?.status === 'HEALTHY' ? 'bg-[#00aa00]' : 'bg-[#aa0000]'}`} />
              <span className="font-mono">{readiness?.status || 'UNKNOWN'}</span>
            </div>
          </div>

          <div className="win-inset p-2 bg-white flex flex-col gap-1">
            <span className="text-[10px] text-[#666] font-bold uppercase">RPO Adherence</span>
            <div className="text-base font-bold font-mono text-[#000080]">
              {readiness?.rpo_compliance?.status || 'N/A'}{' '}
              <span className="text-[10px] text-[#555] font-normal">
                ({readiness?.rpo_compliance?.observed_rpo_hours?.toFixed(1) || 0}h / {readiness?.rpo_compliance?.target_hours || 24}h target)
              </span>
            </div>
          </div>

          <div className="win-inset p-2 bg-white flex flex-col gap-1">
            <span className="text-[10px] text-[#666] font-bold uppercase">Latest Tested RP</span>
            <div className="text-base font-bold font-mono text-[#006600]">
              {readiness?.latest_recovery_point ? `#${readiness.latest_recovery_point.id}` : 'None'}
            </div>
          </div>

          <div className="win-inset p-2 bg-white flex flex-col gap-1">
            <span className="text-[10px] text-[#666] font-bold uppercase">Total Drills</span>
            <div className="text-base font-bold font-mono text-black">
              {tests.length} recorded
            </div>
          </div>
        </div>

        {/* DR Drill History Table */}
        <div className="min-h-[200px]">
          {loading ? (
            <div className="win-inset bg-white p-4 text-center text-[11px] text-[#666]">
              Loading disaster recovery drills from audit repository...
            </div>
          ) : (
            <WinTable<DrTestResponse>
              columns={testColumns}
              data={tests}
              keyExtractor={(t) => t.test_id}
              emptyText="No disaster recovery drill records found. Click '+ Execute Automated DR Drill' to verify an active Recovery Point."
            />
          )}
        </div>
      </WinPanel>

      {/* Architecture Information Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <WinPanel title="Non-Destructive Sandbox Engine">
          <div className="text-[11px] text-[#444] leading-relaxed">
            Automated DR drills extract synthetic blocks to an isolated temporary directory, evaluate cryptographic integrity against the immutable CAS database, verify reference integrity, and immediately purge the sandbox. Target disks and live workloads are never touched.
          </div>
        </WinPanel>

        <WinPanel title="Runbook & Failover Orchestration">
          <div className="text-[11px] text-[#444] leading-relaxed">
            Multi-tier failover and instant access recovery are driven through the <span className="font-bold text-[#000080]">Instant Virtual Recovery</span> subsystem. Virtual recovery sessions bypass full restores by exposing datasets on-demand via local CAS or S3 tiers.
          </div>
        </WinPanel>
      </div>

      {/* Dialog: Run Automated DR Drill */}
      <WinDialog
        isOpen={showRunDrillModal}
        onClose={() => setShowRunDrillModal(false)}
        title="Execute Disaster Recovery Drill"
        icon={<RestoreArrowIcon size={16} />}
        width={460}
        onOk={handleExecuteDrill}
        okText={drillLoading ? 'Executing Drill...' : 'Run Drill'}
        okDisabled={drillLoading}
      >
        <div className="flex flex-col gap-2.5">
          <div className="text-[11px] text-[#333]">
            This will launch a real-time, non-destructive restoration drill in an isolated sandbox to verify file checksums and logical manifest consistency.
          </div>

          <WinInput
            label="Recovery Point ID (leave empty for latest)"
            value={selectedRpId}
            onChange={(e) => setSelectedRpId(e.target.value)}
            placeholder="e.g. 1"
          />

          <div className="text-[10px] text-[#666] italic bg-[#efefef] p-2 win-inset">
            Sandbox directory will be created, verified, and completely removed upon completion. Results will be persisted to the DR drill audit log.
          </div>
        </div>
      </WinDialog>
    </div>
  );
};

export default DisasterRecoveryPage;
