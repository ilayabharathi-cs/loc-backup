import React, { useState, useEffect } from 'react';
import { v12Api, parseApiError } from '../api/v12';
import type { InstantMountSession, InstantMountCreateRequest, MountMode } from '../api/v12';
import { RecoveryPointSelector, type RecoveryPointItem } from '../components/v12/RecoveryPointSelector';
import { MountStatusPanel } from '../components/v12/MountStatusPanel';
import { WinDialog } from '../components/win95/WinDialog';
import { InstantMountIcon, RefreshIcon, HardDriveIcon, WarningIcon } from '../components/win95/WinIcons';

export const InstantRecoveryPage: React.FC = () => {
  const [sessions, setSessions] = useState<InstantMountSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<InstantMountSession | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // New Mount Wizard State
  const [showMountWizard, setShowMountWizard] = useState<boolean>(false);
  const [chosenRp, setChosenRp] = useState<RecoveryPointItem | null>(null);
  const [mountMode, setMountMode] = useState<MountMode>('READ_WRITE_COW');
  const [driveLetter, setDriveLetter] = useState<string>('Z');
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Dismount Modal State
  const [dismountTarget, setDismountTarget] = useState<InstantMountSession | null>(null);
  const [forceDismount, setForceDismount] = useState<boolean>(false);

  const loadSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await v12Api.getInstantMounts();
      setSessions(data);
      if (data.length > 0 && !selectedSession) {
        setSelectedSession(data[0]);
      }
    } catch (err: unknown) {
      setError(parseApiError(err, 'Failed to retrieve instant mount sessions'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleCreateMount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chosenRp) return;

    setSubmitting(true);
    try {
      const payload: InstantMountCreateRequest = {
        recovery_point_id: chosenRp.id,
        target_client_id: chosenRp.client_id,
        mount_mode: mountMode,
        preferred_drive_letter: driveLetter
      };

      const session = await v12Api.createInstantMount(payload);
      setActionMessage(`Instant Mount session created! Virtual volume mapped to ${session.mount_point}`);
      setShowMountWizard(false);
      setChosenRp(null);
      await loadSessions();
      setSelectedSession(session);
    } catch (err: unknown) {
      setActionMessage(parseApiError(err, 'Instant mount failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDismountConfirm = async () => {
    if (!dismountTarget) return;

    try {
      await v12Api.dismountInstantMount(dismountTarget.mount_id, forceDismount);
      setActionMessage(`Virtual volume "${dismountTarget.mount_point}" safely dismounted.`);
      setDismountTarget(null);
      await loadSessions();
    } catch (err: unknown) {
      setActionMessage(parseApiError(err, 'Dismount failed'));
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Title Bar */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span className="bg-[#000080] text-white px-1.5 py-0.5 rounded text-[10px]">V12</span>
            Zero-Copy Instant Recovery & Live Virtual Mount Console
          </h2>
          <p className="text-[11px] text-gray-700">
            Near-zero RTO instant workload mounting from deduplicated CAS storage blocks without data movement
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={() => setShowMountWizard(true)}
            className="win-btn px-3 py-1 font-bold bg-[#dcdcdc] flex items-center gap-1.5"
          >
            <InstantMountIcon size={14} /> Mount Recovery Point...
          </button>
          <button onClick={loadSessions} className="win-btn px-3 py-1 flex items-center gap-1">
            <RefreshIcon size={12} /> Refresh
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-xs font-semibold flex justify-between items-center">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="win-btn text-[10px] px-1.5 py-0.5">
            Dismiss
          </button>
        </div>
      )}

      {/* Main Grid: Active Mount Sessions + Status Panel */}
      {loading ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3">
          <div className="text-xs font-bold text-gray-700">Enumerating virtual block device mount points...</div>
          <div className="w-64 h-4 win-inset-gray bg-[#dfdfdf] relative overflow-hidden">
            <div className="h-full bg-[#000080] animate-pulse w-3/4" />
          </div>
        </div>
      ) : error ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3 text-center">
          <div className="text-[#cc0000] font-bold text-sm">Failed to Load Mount Sessions</div>
          <div className="text-xs text-gray-700 max-w-md">{error}</div>
          <button onClick={loadSessions} className="win-btn px-4 py-1.5 font-bold">
            Retry Connection
          </button>
        </div>
      ) : sessions.length === 0 ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3 text-center">
          <HardDriveIcon size={32} />
          <div className="font-bold text-sm">No Active Instant Mount Sessions</div>
          <div className="text-xs text-gray-600 max-w-sm">
            Instantly mount any SQL database or filesystem recovery point as a live drive without waiting for file copies.
          </div>
          <button onClick={() => setShowMountWizard(true)} className="win-btn px-4 py-1.5 font-bold">
            Mount First Recovery Point
          </button>
        </div>
      ) : (
        <div className="flex-1 flex gap-2 min-h-0">
          {/* Table of Active Sessions */}
          <div className="flex-1 win-inset bg-white overflow-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="bg-[#e0e0e0] sticky top-0 border-b border-[#808080]">
                <tr>
                  <th className="p-1.5 border-r border-[#808080]">Virtual Mount Point</th>
                  <th className="p-1.5 border-r border-[#808080]">Target Host</th>
                  <th className="p-1.5 border-r border-[#808080]">Workload</th>
                  <th className="p-1.5 border-r border-[#808080]">Mode</th>
                  <th className="p-1.5 border-r border-[#808080]">Status</th>
                  <th className="p-1.5 border-r border-[#808080]">Mounted At</th>
                  <th className="p-1.5">Action</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => {
                  const isSelected = selectedSession?.mount_id === s.mount_id;
                  const isActive = s.status === 'ACTIVE';

                  return (
                    <tr
                      key={s.mount_id}
                      onClick={() => setSelectedSession(s)}
                      className={`cursor-pointer border-b border-gray-200 select-none ${
                        isSelected ? 'bg-[#000080] text-white' : 'hover:bg-[#f0f0f0]'
                      }`}
                    >
                      <td className="p-1.5 font-mono font-bold">{s.mount_point}</td>
                      <td className="p-1.5">{s.target_hostname}</td>
                      <td className="p-1.5 font-semibold">{s.workload_name || s.recovery_point_id}</td>
                      <td className="p-1.5 font-mono text-[10px]">
                        {s.mount_mode === 'READ_WRITE_COW' ? 'READ/WRITE COW' : 'READ-ONLY'}
                      </td>
                      <td className="p-1.5">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            s.status === 'ACTIVE'
                              ? isSelected
                                ? 'bg-green-300 text-black'
                                : 'bg-green-100 text-green-800'
                              : s.status === 'MOUNTING'
                              ? isSelected
                                ? 'bg-blue-300 text-black'
                                : 'bg-blue-100 text-blue-800'
                              : 'bg-gray-200 text-gray-700'
                          }`}
                        >
                          {s.status}
                        </span>
                      </td>
                      <td className="p-1.5 text-[10px]">
                        {s.mounted_at ? new Date(s.mounted_at).toLocaleTimeString() : 'N/A'}
                      </td>
                      <td className="p-1.5">
                        {isActive && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDismountTarget(s);
                            }}
                            className={`win-btn text-[10px] px-2 py-0.5 text-[#cc0000] font-bold ${
                              isSelected ? 'bg-[#c0c0c0]' : ''
                            }`}
                          >
                            Dismount
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Right Status Panel */}
          <div className="w-80 overflow-auto">
            {selectedSession ? (
              <MountStatusPanel
                session={selectedSession}
                onDismount={(s) => setDismountTarget(s)}
              />
            ) : (
              <div className="win-outset p-6 text-center text-gray-500 bg-[#dcdcdc]">
                Select an active mount session to inspect status.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Mount Recovery Point Wizard Dialog */}
      <WinDialog
        isOpen={showMountWizard}
        title="Instant Recovery Wizard — [Step-by-Step]"
        icon={<InstantMountIcon size={16} />}
        onClose={() => setShowMountWizard(false)}
        width="620px"
      >
        <form onSubmit={handleCreateMount} className="flex flex-col gap-3 p-1 font-sans text-xs">
          <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-[11px]">
            <strong>Zero-Copy Mount:</strong> Present recovery point blocks virtually as a physical volume. Changes are redirected to an isolated copy-on-write delta file without altering base backup archives.
          </div>

          {/* Step 1: Select RP */}
          <div className="flex flex-col gap-1">
            <span className="font-bold text-[11px]">1. Select Source Recovery Point:</span>
            <RecoveryPointSelector
              onSelect={(rp) => setChosenRp(rp)}
              selectedRpId={chosenRp?.id}
            />
          </div>

          {/* Step 2: Mount Parameters */}
          {chosenRp && (
            <div className="win-inset p-2.5 bg-gray-50 flex flex-col gap-2">
              <span className="font-bold text-[11px] text-[#000080]">
                2. Configure Target Volume Parameters for: {chosenRp.workload_name}
              </span>

              <div className="grid grid-cols-2 gap-2">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-bold">Mount Mode:</label>
                  <select
                    className="win-inset px-2 py-1 bg-white text-xs"
                    value={mountMode}
                    onChange={(e) => setMountMode(e.target.value as MountMode)}
                  >
                    <option value="READ_WRITE_COW">Read/Write (Isolated COW Snapshot)</option>
                    <option value="READ_ONLY">Read-Only (Audit / File Extraction)</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-bold">Drive Letter:</label>
                  <select
                    className="win-inset px-2 py-1 bg-white text-xs font-mono font-bold"
                    value={driveLetter}
                    onChange={(e) => setDriveLetter(e.target.value)}
                  >
                    {['Z', 'Y', 'X', 'W', 'V', 'U', 'T'].map((letter) => (
                      <option key={letter} value={letter}>
                        {letter}:\ (Virtual Block Device)
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-[#808080]">
            <button
              type="button"
              onClick={() => setShowMountWizard(false)}
              className="win-btn px-3 py-1"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="win-btn px-4 py-1 font-bold bg-[#dcdcdc]"
              disabled={submitting || !chosenRp}
            >
              {submitting ? 'Mounting Volume...' : 'Mount Virtual Volume Now'}
            </button>
          </div>
        </form>
      </WinDialog>

      {/* Safe Dismount Confirmation Dialog */}
      <WinDialog
        isOpen={Boolean(dismountTarget)}
        title="Confirm Safe Dismount — [Data Protection Guard]"
        icon={<InstantMountIcon size={16} />}
        onClose={() => setDismountTarget(null)}
        width="440px"
      >
        <div className="flex flex-col gap-3 p-1 font-sans text-xs">
          <div className="win-inset p-2.5 bg-[#ffebee] border-l-4 border-[#cc0000]">
            <div className="font-bold text-[#cc0000] flex items-center gap-1">
              <WarningIcon size={14} /> Dismounting Live Virtual Volume
            </div>
            <p className="text-[11px] text-gray-800 mt-1">
              Are you sure you want to dismount <strong>{dismountTarget?.mount_point}</strong>? Active database connections or open files will be forcibly closed.
            </p>
          </div>

          <label className="flex items-center gap-2 font-bold cursor-pointer text-[11px] text-gray-700">
            <input
              type="checkbox"
              checked={forceDismount}
              onChange={(e) => setForceDismount(e.target.checked)}
            />
            <span>Force dismount if volume is locked by active host handles</span>
          </label>

          <div className="flex justify-end gap-2 pt-2 border-t border-[#808080]">
            <button onClick={() => setDismountTarget(null)} className="win-btn px-3 py-1">
              Cancel
            </button>
            <button onClick={handleDismountConfirm} className="win-btn px-4 py-1 font-bold bg-[#ffebee] text-[#cc0000]">
              Confirm Safe Dismount
            </button>
          </div>
        </div>
      </WinDialog>
    </div>
  );
};

export default InstantRecoveryPage;
