import React, { useState, useEffect } from 'react';
import { useApp } from '../../context/AppContext';

export const WinStatusBar: React.FC = () => {
  const { clients, jobs, storage, soundEnabled, setSoundEnabled } = useApp();
  const [timeStr, setTimeStr] = useState<string>('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString());
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  const onlineCount = clients.filter(c => c.status === 'ONLINE' || c.status === 'BACKING_UP').length;
  const offlineCount = clients.filter(c => c.status === 'OFFLINE').length;
  const runningJobs = jobs.filter(j => j.status === 'RUNNING').length;

  return (
    <footer className="bg-[#c0c0c0] border-t border-[#ffffff] p-1 flex items-center gap-1 select-none text-[11px] shrink-0">
      {/* Panel 1: Server Status */}
      <div className="win-inset-thin px-2 py-0.5 flex items-center gap-1.5 min-w-[160px] text-black bg-[#c0c0c0]">
        <span className="w-2 h-2 rounded-full bg-[#00dd00] border border-black inline-block animate-pulse" />
        <span>Status: <b>Server Online</b></span>
      </div>

      {/* Panel 2: Client breakdown */}
      <div className="win-inset-thin px-2 py-0.5 flex items-center gap-2 min-w-[200px] text-black bg-[#c0c0c0]">
        <span>Clients: <b>{clients.length} Total</b></span>
        <span className="text-[#808080]">|</span>
        <span className="text-[#006600]"><b>{onlineCount}</b> Online</span>
        {offlineCount > 0 && (
          <>
            <span className="text-[#808080]">|</span>
            <span className="text-[#cc0000]"><b>{offlineCount}</b> Offline</span>
          </>
        )}
      </div>

      {/* Panel 3: Active Backup Job Telemetry */}
      <div className="win-inset-thin px-2 py-0.5 flex-1 flex items-center gap-2 overflow-hidden text-black bg-[#c0c0c0]">
        {runningJobs > 0 ? (
          <div className="flex items-center gap-1.5 text-[#000080]">
            <span className="w-2 h-2 rounded-full bg-[#0055ff] inline-block animate-ping" />
            <span className="font-semibold truncate">Active Backup Operations: {runningJobs} running</span>
          </div>
        ) : (
          <span className="text-[#404040] truncate">Repository Ready (D:\BackupRepository) — {storage.freeTb} TB Free</span>
        )}
      </div>

      {/* Panel 4: Sound Toggle */}
      <button
        type="button"
        title="Toggle Win95 System Audio"
        onClick={() => setSoundEnabled(!soundEnabled)}
        className="win-inset-thin px-2 py-0.5 flex items-center gap-1 text-[10px] hover:bg-[#dfdfdf] cursor-pointer bg-[#c0c0c0]"
      >
        <span>🔊</span>
        <span>{soundEnabled ? 'Audio ON' : 'Muted'}</span>
      </button>

      {/* Panel 5: Sync Time / Digital Clock */}
      <div className="win-inset-thin px-2.5 py-0.5 flex items-center gap-1 min-w-[130px] justify-center text-black font-mono text-[10px] bg-[#c0c0c0]">
        <span className="text-[#404040]">Last sync:</span>
        <span className="font-bold">{timeStr || '20:14:32'}</span>
      </div>
    </footer>
  );
};
