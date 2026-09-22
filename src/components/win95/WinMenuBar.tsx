import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';

interface MenuItem {
  label: string;
  shortcut?: string;
  action?: () => void;
  divider?: boolean;
  disabled?: boolean;
}

interface MenuCategory {
  title: string;
  accessKey: string;
  items: MenuItem[];
}

interface WinMenuBarProps {
  onOpenAbout?: () => void;
  onOpenReport?: () => void;
}

export const WinMenuBar: React.FC<WinMenuBarProps> = ({ onOpenAbout, onOpenReport }) => {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { 
    addToast, 
    verifyStorage, 
    soundEnabled, 
    setSoundEnabled, 
    playWin95Sound,
    clients,
    triggerBackup
  } = useApp();

  // Close menus on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenIndex(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const menus: MenuCategory[] = [
    {
      title: 'File',
      accessKey: 'F',
      items: [
        { label: 'Connect to Management Server...', shortcut: 'Ctrl+N', action: () => addToast('Server Connect', 'Already connected to RETROVAULT-PRIMARY-01', 'info') },
        { label: 'Disconnect Console', action: () => addToast('Session Alert', 'Administrative session locked. Reconnected.', 'warning') },
        { divider: true, label: '' },
        { label: 'Export System Configuration...', shortcut: 'Ctrl+S', action: () => addToast('Export Success', 'System configuration exported to D:\\RetroVault-Config.json', 'success') },
        { label: 'Repository Properties...', action: () => navigate('/storage') },
        { divider: true, label: '' },
        { label: 'Exit Console', shortcut: 'Alt+F4', action: () => addToast('Console Lock', 'Console exit cancelled by system administrator policy.', 'info') }
      ]
    },
    {
      title: 'View',
      accessKey: 'V',
      items: [
        { label: 'Dashboard', shortcut: 'Ctrl+1', action: () => navigate('/dashboard') },
        { label: 'Clients Explorer', shortcut: 'Ctrl+2', action: () => navigate('/clients') },
        { label: 'Backup Jobs Monitor', shortcut: 'Ctrl+3', action: () => navigate('/jobs') },
        { label: 'Activity Event Log', shortcut: 'Ctrl+4', action: () => navigate('/activity') },
        { divider: true, label: '' },
        { label: 'Refresh All Statuses', shortcut: 'F5', action: () => { playWin95Sound('ding'); addToast('Refreshed', 'Client statuses and job telemetry updated.', 'info'); } },
        { label: soundEnabled ? 'Mute System Sounds [✓]' : 'Enable System Sounds [ ]', action: () => { setSoundEnabled(!soundEnabled); addToast('Sound Setting', `PC Audio ${!soundEnabled ? 'Enabled' : 'Muted'}`, 'info'); } }
      ]
    },
    {
      title: 'Backup',
      accessKey: 'B',
      items: [
        { 
          label: 'Run Backup on All Online Clients', 
          shortcut: 'F9', 
          action: () => {
            const online = clients.filter(c => c.status === 'ONLINE').slice(0, 3);
            online.forEach(c => triggerBackup(c.id));
            addToast('Batch Backup', `Triggered backup for ${online.length} workstations.`, 'info');
          } 
        },
        { label: 'Active Jobs Queue', action: () => navigate('/jobs') },
        { label: 'Backup Policy Manager', action: () => navigate('/policies') },
        { divider: true, label: '' },
        { label: 'Pause All Scheduled Operations', action: () => addToast('Scheduler', 'All scheduled backups temporarily suspended.', 'warning') },
        { label: 'Resume Operations Scheduler', action: () => addToast('Scheduler', 'Operations scheduler resumed.', 'success') }
      ]
    },
    {
      title: 'Restore',
      accessKey: 'R',
      items: [
        { label: 'Launch Recovery Wizard...', shortcut: 'Ctrl+R', action: () => navigate('/restore') },
        { label: 'Browse Repository File Catalog...', action: () => navigate('/restore') },
        { divider: true, label: '' },
        { label: 'Verify Recovery Point Hashes', action: () => addToast('Integrity Audit', 'All recovery points validated with SHA-256 signatures.', 'success') }
      ]
    },
    {
      title: 'Clients',
      accessKey: 'C',
      items: [
        { label: 'Client Workstation List', action: () => navigate('/clients') },
        { label: 'Push Agent Update to Clients...', action: () => addToast('Agent Deployment', 'Agent v1.4.2 broadcast queued for 20 clients.', 'info') },
        { label: 'Heartbeat Health Ping', action: () => addToast('Network Ping', '18/20 clients responded within 20ms.', 'success') },
        { divider: true, label: '' },
        { label: 'Assign Universal Policy...', action: () => navigate('/policies') }
      ]
    },
    {
      title: 'Storage',
      accessKey: 'S',
      items: [
        { label: 'Repository Disk Management', action: () => navigate('/storage') },
        { label: 'Run S.M.A.R.T. Integrity Scrub', action: () => verifyStorage() },
        { label: 'Compact & Reclaim Deduplication Space', action: () => addToast('Compaction', 'Deduplication compaction scheduled in background.', 'info') },
        { divider: true, label: '' },
        { label: 'Retention Policy Cleanup', action: () => addToast('Retention', 'Pruned 12 expired recovery points past 7-day threshold.', 'info') }
      ]
    },
    {
      title: 'Reports',
      accessKey: 'P',
      items: [
        { label: 'Generate Enterprise RPO SLA Audit Report', action: () => onOpenReport ? onOpenReport() : addToast('Report Generated', 'RPO Audit exported to D:\\Audit_Report.txt', 'success') },
        { label: 'Storage Growth Forecast (30-Day)', action: () => addToast('Report', 'Storage forecast: Projected usage +420 GB by next month.', 'info') },
        { label: 'Client Compliance Summary', action: () => addToast('Compliance', '90% of workstations compliant with backup frequency.', 'info') }
      ]
    },
    {
      title: 'Help',
      accessKey: 'H',
      items: [
        { label: 'Console Operator Manual (WinHelp)...', shortcut: 'F1', action: () => addToast('WinHelp32', 'Opened RETROVAULT.HLP system documentation.', 'info') },
        { label: 'Run Diagnostic Self-Test', action: () => addToast('Self-Test', 'Subsystems passed: VSS, Dedup, AES-256, TCP/IP listener.', 'success') },
        { divider: true, label: '' },
        { label: 'About RetroVault Backup...', action: () => onOpenAbout ? onOpenAbout() : addToast('RetroVault', 'RetroVault Enterprise Backup v4.2 (Build 1995)', 'info') }
      ]
    }
  ];

  return (
    <div ref={menuRef} className="flex items-center bg-[#c0c0c0] border-b border-[#808080] px-1 select-none text-[11px] relative z-40">
      {menus.map((menu, idx) => {
        const isOpen = openIndex === idx;

        return (
          <div key={menu.title} className="relative">
            <button
              type="button"
              className={`px-2 py-0.5 tracking-wide text-black focus:outline-none ${
                isOpen ? 'win-inset-gray bg-[#000080] text-white' : 'hover:bg-[#000080] hover:text-white'
              }`}
              onClick={() => {
                playWin95Sound('click');
                setOpenIndex(isOpen ? null : idx);
              }}
              onMouseEnter={() => {
                if (openIndex !== null) {
                  setOpenIndex(idx);
                }
              }}
            >
              <u>{menu.accessKey}</u>
              {menu.title.slice(1)}
            </button>

            {/* Dropdown Menu */}
            {isOpen && (
              <div 
                className="absolute left-0 top-full mt-0.5 bg-[#c0c0c0] win-outset py-1 min-w-[230px] shadow-md z-50 flex flex-col"
              >
                {menu.items.map((item, itemIdx) => {
                  if (item.divider) {
                    return (
                      <div key={itemIdx} className="my-1 border-t border-[#808080] border-b border-white" />
                    );
                  }

                  return (
                    <button
                      key={itemIdx}
                      type="button"
                      disabled={item.disabled}
                      className={`w-full text-left px-3 py-1 text-[11px] flex items-center justify-between hover:bg-[#000080] hover:text-white group select-none ${
                        item.disabled ? 'text-[#808080] cursor-not-allowed hover:bg-transparent hover:text-[#808080]' : 'text-black'
                      }`}
                      onClick={() => {
                        playWin95Sound('click');
                        setOpenIndex(null);
                        if (item.action) item.action();
                      }}
                    >
                      <span className="truncate">{item.label}</span>
                      {item.shortcut && (
                        <span className="text-[10px] text-[#404040] group-hover:text-white ml-4 font-mono">
                          {item.shortcut}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
