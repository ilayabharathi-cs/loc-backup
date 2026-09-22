import React from 'react';
import { WinDialog } from '../win95/WinDialog';
import { BackupTapeIcon } from '../win95/WinIcons';

interface AboutDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AboutDialog: React.FC<AboutDialogProps> = ({ isOpen, onClose }) => {
  return (
    <WinDialog
      isOpen={isOpen}
      onClose={onClose}
      title="About RetroVault Backup"
      icon={<BackupTapeIcon size={16} />}
      width={440}
      okText="OK"
      onOk={onClose}
    >
      <div className="flex gap-4 p-2">
        <div className="win-inset-gray p-3 flex flex-col items-center justify-center shrink-0 w-24 h-24 bg-[#dfdfdf]">
          <BackupTapeIcon size={48} />
          <span className="font-mono text-[9px] text-[#404040] mt-1">BUILD 1995</span>
        </div>

        <div className="flex flex-col gap-1 text-[11px] font-sans">
          <h2 className="text-[14px] font-bold text-black m-0">RetroVault Enterprise Backup</h2>
          <p className="font-semibold text-[#000080]">Version 4.2.0 (Service Release 3)</p>
          <p className="text-[#303030]">Copyright © 1995-2026 RetroVault Systems Corp.</p>
          <div className="border-t border-[#808080] my-1" />
          <p className="text-[10px] text-[#404040]">
            Licensed to: <b>GLOBAL ENTERPRISE IT OPERATIONS</b><br />
            License key: <b>RV-95E-4819-2049-X99</b><br />
            Workstation client quota: <b>20 / 50 Agents</b>
          </p>
          <div className="win-inset bg-white p-1 text-[9px] font-mono text-[#505050] mt-1 max-h-16 overflow-y-auto">
            NTFS USN Journal Engine v4.2; VSS Provider 2.1; Hardware SHA-256 Accelerated; Zero-Trust Endpoint Protection.
          </div>
        </div>
      </div>
    </WinDialog>
  );
};
