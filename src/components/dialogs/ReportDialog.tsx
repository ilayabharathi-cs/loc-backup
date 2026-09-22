import React from 'react';
import { WinDialog } from '../win95/WinDialog';
import { ActivityLogIcon } from '../win95/WinIcons';
import { WinButton } from '../win95/WinButton';
import { useApp } from '../../context/AppContext';

interface ReportDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ReportDialog: React.FC<ReportDialogProps> = ({ isOpen, onClose }) => {
  const { clients, storage, addToast } = useApp();

  const compliantClients = clients.filter(c => c.rpoSeconds <= 120);
  const breachedClients = clients.filter(c => c.rpoSeconds > 120);

  const handlePrint = () => {
    addToast('Report Export', 'Enterprise Compliance Report sent to Default Printer / LPT1.', 'info');
  };

  const handleSaveText = () => {
    addToast('Report Saved', 'Report written to D:\\RetroVault-SLA-Audit.log', 'success');
  };

  return (
    <WinDialog
      isOpen={isOpen}
      onClose={onClose}
      title="Enterprise Backup SLA & RPO Compliance Audit"
      icon={<ActivityLogIcon size={16} />}
      width={560}
      okText="Close"
      onOk={onClose}
      extraFooterButtons={
        <>
          <WinButton onClick={handlePrint}>Print Report...</WinButton>
          <WinButton onClick={handleSaveText}>Save to Disk...</WinButton>
        </>
      }
    >
      <div className="flex flex-col gap-2">
        <div className="win-inset bg-white p-3 font-mono text-[10px] text-black h-80 overflow-y-auto leading-relaxed whitespace-pre font-normal select-text">
{`================================================================================
RETROVAULT ENTERPRISE BACKUP MANAGEMENT SYSTEM
EXECUTIVE COMPLIANCE AUDIT & RPO SLA VERIFICATION REPORT
Generated: ${new Date().toLocaleString()}
Server: RETROVAULT-PRIMARY-01 (192.168.1.10)
================================================================================

1. EXECUTIVE SUMMARY
--------------------------------------------------------------------------------
Total Enrolled Workstations:  ${clients.length}
SLA Compliant (RPO <= 2 min): ${compliantClients.length} (${Math.round((compliantClients.length / clients.length) * 100)}%)
SLA Breached (RPO > 2 min):   ${breachedClients.length} (${Math.round((breachedClients.length / clients.length) * 100)}%)
Backup Repository Capacity:   ${storage.totalTb} TB Total, ${storage.usedTb} TB Used, ${storage.freeTb} TB Free (${Math.round((storage.freeTb / storage.totalTb) * 100)}% Available)
Data Deduplication Factor:    ${storage.dedupRatio}:1 (Effective data storage ~${(storage.usedTb * storage.dedupRatio).toFixed(1)} TB)
Hardware Block Integrity:     ${storage.diskHealth}

2. NON-COMPLIANT WORKSTATION AUDIT
--------------------------------------------------------------------------------
${breachedClients.map(c => `[!] ${c.id.padEnd(8)} ${c.hostname.padEnd(18)} User: ${c.user.padEnd(16)} RPO: ${Math.round(c.rpoSeconds / 60)} min (Policy: ${c.policyName}) Status: ${c.status}`).join('\n')}

3. REPOSITORY INTEGRITY STATUS
--------------------------------------------------------------------------------
Repository Path:           ${storage.repositoryPath}
Total Backup Objects:      ${storage.backupObjectsCount.toLocaleString()}
Total Recovery Points:     ${storage.recoveryPointsCount.toLocaleString()}
Last Verification Scrub:   ${storage.lastVerification}

4. CERTIFICATION & SIGN-OFF
--------------------------------------------------------------------------------
Auditor Signature: __________________________________  Date: _______________
System Admin UID:  ADMIN_ROOT_95 (Zero-Trust Verified)
================================================================================
END OF AUDIT REPORT
`}
        </div>
      </div>
    </WinDialog>
  );
};
