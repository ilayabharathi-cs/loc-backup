import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { WinTitleBar } from '../win95/WinTitleBar';
import { WinSidebar } from '../win95/WinSidebar';
import { WinStatusBar } from '../win95/WinStatusBar';
import { WinToastContainer } from '../win95/WinToast';
import { AboutDialog } from '../dialogs/AboutDialog';
import { ReportDialog } from '../dialogs/ReportDialog';
import { BackupTapeIcon } from '../win95/WinIcons';
import { useApp } from '../../context/AppContext';

export const AppLayout: React.FC = () => {
  const [showAbout, setShowAbout] = useState<boolean>(false);
  const [showReport, setShowReport] = useState<boolean>(false);
  const [isMaximized, setIsMaximized] = useState<boolean>(true);
  const { addToast } = useApp();

  return (
    <div className="w-screen h-screen bg-[#008080] p-1 flex items-center justify-center overflow-hidden font-sans">
      {/* Main RetroVault Desktop Window */}
      <div 
        className={`win-outset bg-[#c0c0c0] flex flex-col overflow-hidden shadow-2xl transition-all duration-75 ${
          isMaximized ? 'w-full h-full' : 'w-[1240px] h-[780px] max-w-full max-h-full'
        }`}
      >
        {/* Title Bar */}
        <WinTitleBar
          title="RetroVault Backup — [RETROVAULT-PRIMARY-01\Administrator]"
          icon={<BackupTapeIcon size={16} />}
          onMinimize={() => addToast('Window State', 'Console minimized to system tray.', 'info')}
          onMaximize={() => setIsMaximized(!isMaximized)}
          onClose={() => addToast('Console Security', 'Console exit restricted by administrator policy.', 'warning')}
          active={true}
        />

        {/* Mid Container: Sidebar + Content */}
        <div className="flex-1 flex min-h-0 overflow-hidden">
          <WinSidebar />

          <main className="flex-1 flex flex-col min-w-0 min-h-0 overflow-hidden bg-[#c0c0c0]">
            <Outlet />
          </main>
        </div>

        {/* Sunken Bottom Status Bar */}
        <WinStatusBar />
      </div>

      {/* Floating System Balloon / Toasts */}
      <WinToastContainer />

      {/* Global Dialogs */}
      <AboutDialog
        isOpen={showAbout}
        onClose={() => setShowAbout(false)}
      />

      <ReportDialog
        isOpen={showReport}
        onClose={() => setShowReport(false)}
      />
    </div>
  );
};
