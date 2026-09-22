import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { 
  ComputerIcon, 
  BackupTapeIcon, 
  RestoreArrowIcon, 
  HardDriveIcon, 
  ShieldCheckIcon, 
  ActivityLogIcon, 
  SettingsWrenchIcon, 
  ServerIcon 
} from './WinIcons';
import { useApp } from '../../context/AppContext';

interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: React.ReactNode;
  badge?: number | string;
  badgeColor?: string;
}

export const WinSidebar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { clients, jobs, playWin95Sound } = useApp();

  const runningJobsCount = jobs.filter(j => j.status === 'RUNNING').length;
  const offlineClientsCount = clients.filter(c => c.status === 'OFFLINE').length;

  const navItems: NavItem[] = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      path: '/dashboard',
      icon: <ServerIcon size={18} />
    },
    {
      id: 'clients',
      label: 'Clients',
      path: '/clients',
      icon: <ComputerIcon size={18} />,
      badge: `${clients.length}`,
      badgeColor: offlineClientsCount > 0 ? '#aa0000' : '#000080'
    },
    {
      id: 'jobs',
      label: 'Backup Jobs',
      path: '/jobs',
      icon: <BackupTapeIcon size={18} />,
      badge: runningJobsCount > 0 ? `${runningJobsCount} active` : undefined,
      badgeColor: '#0055ff'
    },
    {
      id: 'restore',
      label: 'Recovery',
      path: '/restore',
      icon: <RestoreArrowIcon size={18} />
    },
    {
      id: 'storage',
      label: 'Storage',
      path: '/storage',
      icon: <HardDriveIcon size={18} />,
      badge: '2.4 TB'
    },
    {
      id: 'policies',
      label: 'Policies',
      path: '/policies',
      icon: <ShieldCheckIcon size={18} />
    },
    {
      id: 'activity',
      label: 'Activity Log',
      path: '/activity',
      icon: <ActivityLogIcon size={18} />
    },
    {
      id: 'settings',
      label: 'Settings',
      path: '/settings',
      icon: <SettingsWrenchIcon size={18} />
    }
  ];

  return (
    <aside className="w-48 bg-[#c0c0c0] win-outset-thin p-1.5 flex flex-col gap-1 select-none shrink-0 border-r border-[#808080]">
      <div className="px-2 py-1 bg-[#808080] text-white font-bold text-[10px] tracking-wider uppercase mb-1 shadow-inner flex items-center justify-between">
        <span>Navigation</span>
        <span className="text-[9px] font-mono text-[#dfdfdf]">v4.2</span>
      </div>

      <nav className="flex flex-col gap-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path || 
            (item.path === '/dashboard' && location.pathname === '/') ||
            (item.path === '/clients' && location.pathname.startsWith('/clients/'));

          return (
            <button
              key={item.id}
              type="button"
              className={`w-full flex items-center justify-between px-2.5 py-1.5 text-[11px] font-medium transition-none text-left ${
                isActive
                  ? 'win-inset bg-[#dfdfdf] text-[#000000] font-bold ring-1 ring-black/20'
                  : 'win-btn hover:bg-[#d4d4d4] text-[#000000]'
              }`}
              onClick={() => {
                playWin95Sound('click');
                navigate(item.path);
              }}
            >
              <div className="flex items-center gap-2 truncate">
                <span className="shrink-0">{item.icon}</span>
                <span className="truncate">{item.label}</span>
              </div>
              {item.badge && (
                <span 
                  className="text-[9px] font-mono font-bold px-1 py-0.2 rounded-xs text-white shrink-0 ml-1 shadow-xs"
                  style={{ backgroundColor: item.badgeColor || '#000080' }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Mini System Health Sunken Box */}
      <div className="mt-auto pt-2">
        <div className="win-inset-gray p-2 text-[10px] flex flex-col gap-1 bg-[#dfdfdf]">
          <div className="font-bold flex items-center justify-between border-b border-[#808080] pb-0.5">
            <span>Daemon Status</span>
            <span className="text-[#008800] font-extrabold">● LIVE</span>
          </div>
          <div className="flex justify-between text-[#404040]">
            <span>USN Engine:</span>
            <span className="font-mono text-black font-semibold">Active</span>
          </div>
          <div className="flex justify-between text-[#404040]">
            <span>VSS Provider:</span>
            <span className="font-mono text-black font-semibold">Ready</span>
          </div>
          <div className="flex justify-between text-[#404040]">
            <span>AES-256:</span>
            <span className="font-mono text-black font-semibold">Locked</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
