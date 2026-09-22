import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { WinButton } from '../components/win95/WinButton';
import { WinFileBrowser } from '../components/win95/WinFileBrowser';
import { WinProgressBar } from '../components/win95/WinProgressBar';
import { WinDialog } from '../components/win95/WinDialog';
import { MOCK_RECOVERY_POINTS, MOCK_FILE_TREE } from '../mock/data';
import type { RecoveryPoint } from '../types';
import { 
  RestoreArrowIcon, 
  WarningIcon 
} from '../components/win95/WinIcons';

export const RestorePage: React.FC = () => {
  const { clients, executeRestore, playWin95Sound } = useApp();

  // Wizard state: 1 to 5
  const [currentStep, setCurrentStep] = useState<number>(1);

  // Step 1: Source client
  const [selectedSourceClientId, setSelectedSourceClientId] = useState<string>('PC-001');

  // Step 2: Recovery point
  const availableRecoveryPoints: RecoveryPoint[] = 
    MOCK_RECOVERY_POINTS[selectedSourceClientId] || [
      { id: 'RP-GEN-01', clientId: selectedSourceClientId, timestamp: '22 Sep 2026 20:12:00', type: 'Incremental', sizeMb: 240.5, fileCount: 28, rootPath: 'C:\\' },
      { id: 'RP-GEN-02', clientId: selectedSourceClientId, timestamp: '22 Sep 2026 18:00:00', type: 'Incremental', sizeMb: 110.0, fileCount: 15, rootPath: 'C:\\' },
      { id: 'RP-GEN-03', clientId: selectedSourceClientId, timestamp: '22 Sep 2026 12:00:00', type: 'Full', sizeMb: 95400.0, fileCount: 24100, rootPath: 'C:\\' },
    ];
  const [selectedPointId, setSelectedPointId] = useState<string>(availableRecoveryPoints[0].id);

  // Step 3: Files selected
  const [selectedFilePaths, setSelectedFilePaths] = useState<string[]>([
    'C:\\Users\\Arun\\Documents\\Q3_Enterprise_Architecture.docx',
    'C:\\Users\\Arun\\Documents\\Vendor_Contracts_Master.xlsx'
  ]);

  // Step 4: Restore Location & Target Client
  const [restoreLocationType, setRestoreLocationType] = useState<'ORIGINAL' | 'CUSTOM'>('ORIGINAL');
  const [customPath, setCustomPath] = useState<string>('C:\\Restored_Files_2026');
  const [selectedTargetClientId, setSelectedTargetClientId] = useState<string>('PC-001');

  // Cross-client warning confirmation modal
  const [showCrossClientWarning, setShowCrossClientWarning] = useState<boolean>(false);
  const [hasAcknowledgedCrossClient, setHasAcknowledgedCrossClient] = useState<boolean>(false);

  // Execution state (Step 5)
  const [isRestoring, setIsRestoring] = useState<boolean>(false);
  const [restoreProgress, setRestoreProgress] = useState<number>(0);
  const [restoreCompleted, setRestoreCompleted] = useState<boolean>(false);

  const sourceClient = clients.find(c => c.id === selectedSourceClientId);
  const targetClient = clients.find(c => c.id === selectedTargetClientId);
  const selectedRecoveryPoint = availableRecoveryPoints.find(p => p.id === selectedPointId) || availableRecoveryPoints[0];

  const effectiveTargetPath = restoreLocationType === 'ORIGINAL' ? 'Original Location' : customPath;
  const isCrossClient = selectedSourceClientId !== selectedTargetClientId;

  const handleTogglePath = (path: string) => {
    setSelectedFilePaths(prev => 
      prev.includes(path) ? prev.filter(p => p !== path) : [...prev, path]
    );
  };

  const handleTargetClientChange = (newTargetId: string) => {
    setSelectedTargetClientId(newTargetId);
    if (newTargetId !== selectedSourceClientId) {
      setHasAcknowledgedCrossClient(false);
      setShowCrossClientWarning(true);
    }
  };

  const handleNext = () => {
    playWin95Sound('click');
    if (currentStep === 4 && isCrossClient && !hasAcknowledgedCrossClient) {
      setShowCrossClientWarning(true);
      return;
    }
    setCurrentStep(prev => Math.min(5, prev + 1));
  };

  const handleBack = () => {
    playWin95Sound('click');
    setCurrentStep(prev => Math.max(1, prev - 1));
  };

  const handleStartRestore = async () => {
    playWin95Sound('chord');
    setIsRestoring(true);
    setRestoreProgress(5);

    // Simulate progress ticks
    const interval = setInterval(() => {
      setRestoreProgress(prev => {
        if (prev >= 95) {
          clearInterval(interval);
          return 100;
        }
        return prev + 20;
      });
    }, 600);

    await executeRestore(
      selectedSourceClientId,
      selectedPointId,
      selectedTargetClientId,
      effectiveTargetPath,
      selectedFilePaths
    );

    clearInterval(interval);
    setRestoreProgress(100);
    setIsRestoring(false);
    setRestoreCompleted(true);
  };

  const handleReset = () => {
    setCurrentStep(1);
    setRestoreCompleted(false);
    setRestoreProgress(0);
    setHasAcknowledgedCrossClient(false);
  };

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-hidden bg-[#c0c0c0]">
      {/* Wizard Header */}
      <div className="win-outset px-3 py-2 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-2">
          <RestoreArrowIcon size={22} />
          <div>
            <h1 className="text-[13px] font-bold text-black m-0 leading-tight">
              Enterprise Recovery & Disaster Restore Wizard
            </h1>
            <p className="text-[10px] text-[#505050] m-0">
              Granular file, folder, and volume restoration with cryptographic integrity verification
            </p>
          </div>
        </div>

        {/* Step Indicator */}
        <div className="flex items-center gap-1">
          {[1, 2, 3, 4, 5].map((step) => {
            const isCurrent = currentStep === step;
            const isDone = currentStep > step;

            return (
              <div
                key={step}
                className={`win-inset-thin px-2 py-0.5 text-[10px] font-bold select-none ${
                  isCurrent
                    ? 'bg-[#000080] text-white'
                    : isDone
                    ? 'bg-[#dfdfdf] text-[#008000]'
                    : 'bg-[#c0c0c0] text-[#707070]'
                }`}
              >
                Step {step}
              </div>
            );
          })}
        </div>
      </div>

      {/* Wizard Step Body */}
      <div className="win-outset p-3 flex-1 flex flex-col min-h-0 bg-[#c0c0c0] overflow-y-auto">
        {/* STEP 1: Select Source Client */}
        {currentStep === 1 && (
          <div className="flex flex-col gap-3">
            <div className="bg-[#000080] text-white p-2 font-bold text-[12px] flex items-center gap-1.5">
              <span>Step 1: Select Source Client Workstation</span>
            </div>
            <p className="text-[11px] text-black">
              Select the client workstation whose backed-up files and snapshots you want to recover.
            </p>

            <div className="win-inset bg-white p-1 max-h-72 overflow-y-auto">
              <table className="w-full text-[11px] border-collapse font-sans">
                <thead className="sticky top-0 bg-[#c0c0c0] win-outset">
                  <tr>
                    <th className="px-2 py-1 text-left">Client ID</th>
                    <th className="px-2 py-1 text-left">Hostname</th>
                    <th className="px-2 py-1 text-left">User</th>
                    <th className="px-2 py-1 text-left">Operating System</th>
                    <th className="px-2 py-1 text-left">Policy</th>
                    <th className="px-2 py-1 text-right">Data Stored</th>
                  </tr>
                </thead>
                <tbody>
                  {clients.map((c) => {
                    const isSelected = selectedSourceClientId === c.id;
                    return (
                      <tr
                        key={c.id}
                        className={`h-6 cursor-pointer select-none ${
                          isSelected ? 'bg-[#000080] text-white' : 'hover:bg-[#f0f0f0] text-black'
                        }`}
                        onClick={() => {
                          setSelectedSourceClientId(c.id);
                          setSelectedTargetClientId(c.id); // default target to source
                        }}
                      >
                        <td className="px-2 font-mono font-bold">{c.id}</td>
                        <td className="px-2 font-mono">{c.hostname}</td>
                        <td className="px-2">{c.user}</td>
                        <td className="px-2 text-[10px]">{c.os}</td>
                        <td className="px-2">{c.policyName}</td>
                        <td className="px-2 text-right font-mono">{c.storageConsumedGb} GB</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {sourceClient && (
              <div className="win-inset-gray p-2 text-[11px] bg-[#dfdfdf] flex items-center justify-between">
                <span>
                  Selected Source: <b>{sourceClient.hostname}</b> ({sourceClient.id}) — User: <b>{sourceClient.user}</b>
                </span>
                <span className="font-mono text-[#000080] font-bold">
                  Last Backup: {sourceClient.lastBackup}
                </span>
              </div>
            )}
          </div>
        )}

        {/* STEP 2: Select Recovery Point */}
        {currentStep === 2 && (
          <div className="flex flex-col gap-3">
            <div className="bg-[#000080] text-white p-2 font-bold text-[12px] flex items-center gap-1.5">
              <span>Step 2: Select Snapshot Recovery Point for {sourceClient?.hostname}</span>
            </div>
            <p className="text-[11px] text-black">
              Choose the exact point-in-time snapshot to restore from. Snapshots are verified with SHA-256 block hashes.
            </p>

            <div className="win-inset bg-white p-1 max-h-72 overflow-y-auto">
              <table className="w-full text-[11px] border-collapse font-sans">
                <thead className="sticky top-0 bg-[#c0c0c0] win-outset">
                  <tr>
                    <th className="px-2 py-1 text-left">Snapshot Timestamp</th>
                    <th className="px-2 py-1 text-left">Type</th>
                    <th className="px-2 py-1 text-right">Size</th>
                    <th className="px-2 py-1 text-right">Protected Files</th>
                    <th className="px-2 py-1 text-left">Catalog Root</th>
                    <th className="px-2 py-1 text-center">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {availableRecoveryPoints.map((pt) => {
                    const isSelected = selectedPointId === pt.id;
                    return (
                      <tr
                        key={pt.id}
                        className={`h-6 cursor-pointer select-none ${
                          isSelected ? 'bg-[#000080] text-white' : 'hover:bg-[#f0f0f0] text-black'
                        }`}
                        onClick={() => setSelectedPointId(pt.id)}
                      >
                        <td className="px-2 font-mono font-bold">{pt.timestamp}</td>
                        <td className="px-2 font-mono">{pt.type}</td>
                        <td className="px-2 text-right font-mono">{pt.sizeMb.toLocaleString()} MB</td>
                        <td className="px-2 text-right font-mono">{pt.fileCount} files</td>
                        <td className="px-2 font-mono text-[10px]">{pt.rootPath}</td>
                        <td className="px-2 text-center text-[#008000] font-bold">VERIFIED</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="win-fieldset p-2">
              <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
                POINT-IN-TIME DETAILS
              </legend>
              <div className="grid grid-cols-3 gap-2 text-[11px]">
                <div>
                  <span className="text-[#606060]">Point ID:</span> <b>{selectedRecoveryPoint.id}</b>
                </div>
                <div>
                  <span className="text-[#606060]">Timestamp:</span> <b>{selectedRecoveryPoint.timestamp}</b>
                </div>
                <div>
                  <span className="text-[#606060]">Integrity Check:</span> <b className="text-[#008000]">PASSED (SHA-256)</b>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Browse Backed-Up Files */}
        {currentStep === 3 && (
          <div className="flex flex-col gap-2 flex-1 min-h-0">
            <div className="bg-[#000080] text-white p-2 font-bold text-[12px] flex items-center justify-between shrink-0">
              <span>Step 3: Browse Backed-Up Files & Folders</span>
              <span className="text-[10px] font-mono font-normal">
                Point: {selectedRecoveryPoint.timestamp}
              </span>
            </div>
            <p className="text-[11px] text-black shrink-0">
              Navigate the directory tree and mark the specific files or folders you wish to recover.
            </p>

            <div className="flex-1 min-h-0">
              <WinFileBrowser
                root={MOCK_FILE_TREE}
                selectedPaths={selectedFilePaths}
                onTogglePath={handleTogglePath}
                className="h-full"
              />
            </div>
          </div>
        )}

        {/* STEP 4: Select Restore Location & Target Client */}
        {currentStep === 4 && (
          <div className="flex flex-col gap-3">
            <div className="bg-[#000080] text-white p-2 font-bold text-[12px] flex items-center gap-1.5">
              <span>Step 4: Configure Destination Workstation & Path</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Left Column: Target Client */}
              <div className="win-fieldset">
                <legend className="text-[11px] font-bold text-black bg-[#c0c0c0] px-1">
                  TARGET WORKSTATION
                </legend>
                <div className="flex flex-col gap-2 p-1">
                  <div className="text-[11px] text-black">
                    Select where the restored files should be transferred:
                  </div>

                  <select
                    value={selectedTargetClientId}
                    onChange={(e) => handleTargetClientChange(e.target.value)}
                    className="win-inset bg-white px-2 py-1 text-[11px] text-black font-sans cursor-pointer"
                  >
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.hostname} ({c.id}) — {c.user} {c.id === selectedSourceClientId ? '[SOURCE CLIENT]' : ''}
                      </option>
                    ))}
                  </select>

                  {isCrossClient && (
                    <div className="win-inset bg-[#fff8e7] border border-[#cc8800] p-2 text-[10px] text-[#805000] flex items-start gap-1.5 mt-2">
                      <WarningIcon size={16} />
                      <div>
                        <b>CROSS-CLIENT RESTORE ACTIVE:</b> You are attempting to restore data from <b>{sourceClient?.hostname}</b> to a different computer <b>{targetClient?.hostname}</b>.
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Path Selection */}
              <div className="win-fieldset">
                <legend className="text-[11px] font-bold text-black bg-[#c0c0c0] px-1">
                  DESTINATION PATH OPTIONS
                </legend>
                <div className="flex flex-col gap-2 p-1">
                  <label className="flex items-center gap-2 cursor-pointer text-[11px]">
                    <input
                      type="radio"
                      name="restoreLoc"
                      checked={restoreLocationType === 'ORIGINAL'}
                      onChange={() => setRestoreLocationType('ORIGINAL')}
                    />
                    <span><b>Original Location</b> (Overwrite or update original file paths)</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer text-[11px]">
                    <input
                      type="radio"
                      name="restoreLoc"
                      checked={restoreLocationType === 'CUSTOM'}
                      onChange={() => setRestoreLocationType('CUSTOM')}
                    />
                    <span><b>Custom Location</b> (Extract to separate folder)</span>
                  </label>

                  {restoreLocationType === 'CUSTOM' && (
                    <div className="mt-1 flex flex-col gap-1 pl-5">
                      <span className="text-[10px] text-[#404040]">Specify custom directory:</span>
                      <input
                        type="text"
                        value={customPath}
                        onChange={(e) => setCustomPath(e.target.value)}
                        className="win-inset bg-white px-2 py-1 font-mono text-[11px] text-black"
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Comparison Table */}
            <div className="win-fieldset mt-1">
              <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
                RESTORE ROUTING SUMMARY
              </legend>
              <div className="grid grid-cols-4 gap-2 p-1 text-[11px] font-sans">
                <div>
                  <span className="text-[#606060] block">Source Client:</span>
                  <span className="font-mono font-bold text-black">{sourceClient?.hostname} ({sourceClient?.id})</span>
                </div>
                <div>
                  <span className="text-[#606060] block">Target Client:</span>
                  <span className={`font-mono font-bold ${isCrossClient ? 'text-[#aa0000]' : 'text-black'}`}>
                    {targetClient?.hostname} ({targetClient?.id})
                  </span>
                </div>
                <div>
                  <span className="text-[#606060] block">Recovery Point:</span>
                  <span className="font-mono text-black">{selectedRecoveryPoint.timestamp}</span>
                </div>
                <div>
                  <span className="text-[#606060] block">Target Path:</span>
                  <span className="font-mono text-black">{effectiveTargetPath}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 5: Confirm & Execute Restore */}
        {currentStep === 5 && (
          <div className="flex flex-col gap-3">
            <div className="bg-[#000080] text-white p-2 font-bold text-[12px] flex items-center gap-1.5">
              <span>Step 5: Review & Confirm Restoration</span>
            </div>

            {!restoreCompleted ? (
              <div className="flex flex-col gap-3">
                <div className="win-inset bg-white p-3 flex flex-col gap-2 text-[11px] font-sans">
                  <div className="font-bold border-b border-[#808080] pb-1 text-black">
                    Please confirm the following restore parameters before proceeding:
                  </div>

                  <div className="grid grid-cols-2 gap-y-1.5 text-[11px]">
                    <div>
                      <span className="text-[#606060]">Source Workstation:</span> <b>{sourceClient?.hostname} ({sourceClient?.id})</b>
                    </div>
                    <div>
                      <span className="text-[#606060]">Target Workstation:</span>{' '}
                      <b className={isCrossClient ? 'text-[#cc0000]' : ''}>
                        {targetClient?.hostname} ({targetClient?.id})
                      </b>
                    </div>
                    <div>
                      <span className="text-[#606060]">Recovery Point:</span> <b>{selectedRecoveryPoint.timestamp}</b>
                    </div>
                    <div>
                      <span className="text-[#606060]">Target Destination:</span> <b>{effectiveTargetPath}</b>
                    </div>
                    <div>
                      <span className="text-[#606060]">Selected Items to Restore:</span> <b>{selectedFilePaths.length} items marked</b>
                    </div>
                    <div>
                      <span className="text-[#606060]">Security Clearance:</span> <b className="text-[#008000]">AUTHORIZED (ADMIN)</b>
                    </div>
                  </div>

                  <div className="win-fieldset mt-2">
                    <legend className="text-[10px] font-bold text-black bg-white px-1">
                      MANIFEST OF ITEMS TO EXTRACT
                    </legend>
                    <div className="max-h-28 overflow-y-auto font-mono text-[10px] text-black flex flex-col gap-0.5 p-1">
                      {selectedFilePaths.map((f, idx) => (
                        <div key={idx} className="flex items-center gap-1">
                          <span className="text-[#000080]">▶</span>
                          <span>{f}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {isRestoring && (
                  <div className="win-fieldset p-3">
                    <legend className="text-[10px] font-bold text-black bg-[#c0c0c0] px-1">
                      RESTORATION IN PROGRESS...
                    </legend>
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center gap-3">
                        <RestoreArrowIcon size={24} className="animate-spin" />
                        <span className="text-[11px] font-mono text-black">
                          Streaming blocks from D:\BackupRepository to {targetClient?.hostname}...
                        </span>
                      </div>
                      <WinProgressBar percent={restoreProgress} showPercentText={true} />
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="win-inset bg-white p-4 flex flex-col items-center gap-3 text-center">
                <div className="w-12 h-12 rounded-full bg-[#008000] flex items-center justify-center text-white text-[24px]">
                  ✓
                </div>
                <h2 className="text-[14px] font-bold text-black m-0">
                  Restoration Completed Successfully
                </h2>
                <p className="text-[11px] text-[#404040] max-w-md m-0">
                  {selectedFilePaths.length} files were successfully extracted and verified on <b>{targetClient?.hostname}</b> at <b>{effectiveTargetPath}</b>.
                </p>
                <div className="win-inset-gray p-2 font-mono text-[10px] text-black">
                  SHA-256 verification checksum: 4a2f8b1c...99e8 PASSED
                </div>
                <WinButton isDefault onClick={handleReset}>
                  Start Another Recovery
                </WinButton>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Wizard Footer Controls */}
      <div className="win-outset px-3 py-2 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="text-[10px] text-[#505050]">
          Step {currentStep} of 5
        </div>

        <div className="flex items-center gap-2">
          {currentStep > 1 && !isRestoring && !restoreCompleted && (
            <WinButton onClick={handleBack}>
              &lt; Back
            </WinButton>
          )}

          {currentStep < 5 && (
            <WinButton
              isDefault
              onClick={handleNext}
              disabled={currentStep === 3 && selectedFilePaths.length === 0}
            >
              Next &gt;
            </WinButton>
          )}

          {currentStep === 5 && !restoreCompleted && (
            <WinButton
              isDefault
              onClick={handleStartRestore}
              disabled={isRestoring || selectedFilePaths.length === 0}
            >
              {isRestoring ? 'Restoring...' : 'Execute Restore Now'}
            </WinButton>
          )}

          <WinButton onClick={handleReset} disabled={isRestoring}>
            Cancel Wizard
          </WinButton>
        </div>
      </div>

      {/* Explicit Cross-Client Confirmation Safeguard Dialog */}
      <WinDialog
        isOpen={showCrossClientWarning}
        onClose={() => {
          setSelectedTargetClientId(selectedSourceClientId);
          setShowCrossClientWarning(false);
        }}
        title="SECURITY WARNING: Cross-Client Recovery Safeguard"
        icon={<WarningIcon size={16} />}
        width={460}
        okText="Authorize Cross-Client Restore"
        okDisabled={false}
        onOk={() => {
          setHasAcknowledgedCrossClient(true);
          setShowCrossClientWarning(false);
        }}
        cancelText="Revert to Same Client"
      >
        <div className="flex gap-3 p-1">
          <div className="shrink-0 pt-1">
            <WarningIcon size={32} />
          </div>
          <div className="flex flex-col gap-2 text-[11px] font-sans">
            <h3 className="text-[12px] font-bold text-[#800000] m-0">
              CAUTION: CROSS-WORKSTATION RESTORE DETECTED
            </h3>
            <p className="text-black leading-snug">
              You have selected <b>{sourceClient?.hostname}</b> as the data source, but specified <b>{targetClient?.hostname}</b> as the destination target.
            </p>
            <p className="text-[#404040] leading-snug">
              Restoring files to another user's machine may overwrite sensitive files or breach data governance privacy policies.
            </p>
            <div className="win-inset bg-[#fff8e7] p-2 text-[10px] font-mono text-[#804000] border border-[#d09000]">
              Are you certain you wish to redirect this restore operation to <b>{targetClient?.hostname}</b>?
            </div>
          </div>
        </div>
      </WinDialog>
    </div>
  );
};
