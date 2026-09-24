import React, { useState, useEffect } from 'react';
import { v12Api, parseApiError } from '../api/v12';
import type { StorageTier, StorageTierCreate, CloudCredential } from '../api/v12';
import { StorageTierCard } from '../components/v12/StorageTierCard';
import { WinDialog } from '../components/win95/WinDialog';
import { HardDriveIcon, RefreshIcon } from '../components/win95/WinIcons';

export const StorageTiersPage: React.FC = () => {
  const [tiers, setTiers] = useState<StorageTier[]>([]);
  const [credentials, setCredentials] = useState<CloudCredential[]>([]);
  const [selectedTier, setSelectedTier] = useState<StorageTier | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Create Tier Modal State
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newTierName, setNewTierName] = useState('');
  const [newTierType, setNewTierType] = useState<'HOT' | 'COOL' | 'COLD' | 'ARCHIVE'>('COOL');
  const [newProviderType, setNewProviderType] = useState<'LOCAL' | 'AWS_S3' | 'AZURE_BLOB' | 'S3_COMPATIBLE'>('AWS_S3');
  const [newCredId, setNewCredId] = useState('');
  const [newObjectLock, setNewObjectLock] = useState(true);
  const [newLockMode, setNewLockMode] = useState<'COMPLIANCE' | 'GOVERNANCE'>('COMPLIANCE');
  const [newRetentionDays, setNewRetentionDays] = useState(90);
  const [submitting, setSubmitting] = useState(false);

  // Offload Confirmation Modal State
  const [offloadTarget, setOffloadTarget] = useState<StorageTier | null>(null);
  const [offloadOlderThanDays, setOffloadOlderThanDays] = useState<number>(30);
  const [offloadSubmitting, setOffloadSubmitting] = useState<boolean>(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [tiersData, credsData] = await Promise.all([
        v12Api.listStorageTiers(),
        v12Api.listCloudCredentials()
      ]);
      setTiers(tiersData);
      setCredentials(credsData);
      if (tiersData.length > 0 && !selectedTier) {
        setSelectedTier(tiersData[0]);
      }
    } catch (err: unknown) {
      setError(parseApiError(err, 'Failed to connect to storage tier subsystem'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateTier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTierName.trim() || submitting) return;

    setSubmitting(true);
    try {
      const payload: StorageTierCreate = {
        name: newTierName.trim(),
        tier_type: newTierType,
        provider_type: newProviderType,
        credential_id: newProviderType !== 'LOCAL' ? newCredId : undefined,
        object_lock_enabled: newObjectLock,
        object_lock_mode: newObjectLock ? newLockMode : undefined,
        retention_days: newObjectLock ? newRetentionDays : undefined
      };

      const created = await v12Api.createStorageTier(payload);
      setActionMessage(`Storage Tier "${created.name}" created successfully.`);
      setShowCreateModal(false);
      setNewTierName('');
      await loadData();
    } catch (err: unknown) {
      setActionMessage(`Create error: ${parseApiError(err)}`);
    } finally {
      setSubmitting(false);
    }
  };

  const executeOffload = async () => {
    if (!offloadTarget || offloadSubmitting) return;

    setOffloadSubmitting(true);
    setActionMessage(`Executing data offload to "${offloadTarget.name}"...`);
    try {
      const res = await v12Api.offloadStorageTier(offloadTarget.tier_id, {
        older_than_days: offloadOlderThanDays
      });
      setActionMessage(
        `Offload completed! Operation ID: ${res.operation_id}. Transferred ${res.objects_offloaded} objects (${(res.bytes_offloaded / (1024 * 1024 * 1024)).toFixed(2)} GB) to immutable cloud target.`
      );
      setOffloadTarget(null);
      await loadData();
    } catch (err: unknown) {
      setActionMessage(`Offload error: ${parseApiError(err)}`);
    } finally {
      setOffloadSubmitting(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Title Bar */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span className="bg-[#000080] text-white px-1.5 py-0.5 rounded text-[10px]">V12</span>
            Cloud & Hybrid Storage Tiering Architecture
          </h2>
          <p className="text-[11px] text-gray-700">
            Multi-tier data lifecycle orchestration: Local NVMe cache, S3 Standard-IA, Azure Worm Archive, and WORM Object Lock
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={() => setShowCreateModal(true)}
            className="win-btn px-3 py-1 font-bold bg-[#dcdcdc]"
          >
            + Create Storage Tier
          </button>
          <button onClick={loadData} className="win-btn px-3 py-1 flex items-center gap-1">
            <RefreshIcon size={12} /> Refresh
          </button>
        </div>
      </div>

      {/* Action / Warning Notice */}
      {actionMessage && (
        <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-xs font-semibold flex justify-between items-center">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="win-btn text-[10px] px-1.5 py-0.5">
            Dismiss
          </button>
        </div>
      )}

      {/* Main Content Area */}
      {loading ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3">
          <div className="text-xs font-bold text-gray-700">Loading storage tier telemetry...</div>
          <div className="w-64 h-4 win-inset-gray bg-[#dfdfdf] relative overflow-hidden">
            <div className="h-full bg-[#000080] animate-pulse w-3/4" />
          </div>
        </div>
      ) : error ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3 text-center">
          <div className="text-[#cc0000] font-bold text-sm">Failed to Load Storage Tiers</div>
          <div className="text-xs text-gray-700 max-w-md">{error}</div>
          <button onClick={loadData} className="win-btn px-4 py-1.5 font-bold">
            Retry Connection
          </button>
        </div>
      ) : tiers.length === 0 ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3 text-center">
          <HardDriveIcon size={32} />
          <div className="font-bold text-sm">No Storage Tiers Configured</div>
          <div className="text-xs text-gray-600 max-w-sm">
            Configure hot local performance storage and cloud cold tiers with S3 Object Lock for immutability.
          </div>
          <button onClick={() => setShowCreateModal(true)} className="win-btn px-4 py-1.5 font-bold">
            Create First Storage Tier
          </button>
        </div>
      ) : (
        <div className="flex-1 flex gap-2 min-h-0">
          {/* Left Column: Tiers List */}
          <div className="w-1/2 flex flex-col gap-2 overflow-auto pr-1">
            <div className="text-[11px] font-bold text-gray-700 px-1">
              Active Storage Tiers ({tiers.length}):
            </div>
            {tiers.map((tier: StorageTier) => (
              <StorageTierCard
                key={tier.tier_id}
                tier={tier}
                selected={selectedTier?.tier_id === tier.tier_id}
                onSelect={(t) => setSelectedTier(t)}
                onOffload={(t) => setOffloadTarget(t)}
              />
            ))}
          </div>

          {/* Right Column: Detailed Tier Inspector */}
          <div className="w-1/2 win-outset p-3 bg-[#dcdcdc] flex flex-col gap-3 overflow-auto">
            {selectedTier ? (
              <>
                <div className="flex justify-between items-center border-b border-[#808080] pb-2">
                  <h3 className="font-bold text-sm flex items-center gap-2">
                    <HardDriveIcon size={16} />
                    <span>Tier Configuration & Diagnostics</span>
                  </h3>
                  <span className="font-mono text-[10px] text-gray-600">{selectedTier.tier_id}</span>
                </div>

                <div className="win-inset bg-white p-2.5 flex flex-col gap-2">
                  <div className="font-bold text-xs text-[#000080] border-b border-gray-200 pb-1">
                    Tier Identity & Immutability
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>
                      <span className="text-gray-600 block">Friendly Name:</span>
                      <strong className="block">{selectedTier.name}</strong>
                    </div>
                    <div>
                      <span className="text-gray-600 block">Performance Tier:</span>
                      <strong className="block">{selectedTier.tier_type}</strong>
                    </div>
                    <div>
                      <span className="text-gray-600 block">Provider Engine:</span>
                      <strong className="block">{selectedTier.provider_type}</strong>
                    </div>
                    <div>
                      <span className="text-gray-600 block">Object Lock Mode:</span>
                      <strong className="block">
                        {selectedTier.object_lock_enabled
                          ? `${selectedTier.object_lock_mode || 'COMPLIANCE'} (${selectedTier.retention_days} days)`
                          : 'Disabled'}
                      </strong>
                    </div>
                    {selectedTier.local_path && (
                      <div className="col-span-2">
                        <span className="text-gray-600 block">Local Mount Path:</span>
                        <code className="block text-[10px] bg-gray-100 p-1 border border-gray-300">
                          {selectedTier.local_path}
                        </code>
                      </div>
                    )}
                    {selectedTier.credential_id && (
                      <div className="col-span-2">
                        <span className="text-gray-600 block">Linked Cloud Credential:</span>
                        <code className="block text-[10px] bg-gray-100 p-1 border border-gray-300">
                          {selectedTier.credential_id}
                        </code>
                      </div>
                    )}
                  </div>
                </div>

                <div className="win-inset bg-white p-2.5 flex flex-col gap-2">
                  <div className="font-bold text-xs text-[#000080] border-b border-gray-200 pb-1">
                    Tiering Policy & Lifecycle Rules
                  </div>
                  <ul className="list-disc pl-4 text-[11px] text-gray-700 flex flex-col gap-1">
                    <li>Primary backup write landing occurs on <strong>HOT</strong> local storage.</li>
                    <li>
                      Recovery points aged past <strong>{selectedTier.retention_days || 30} days</strong> are automatically moved via CAS offload.
                    </li>
                    {selectedTier.object_lock_enabled ? (
                      <li className="text-[#000080] font-semibold">
                        Objects locked under AWS/Azure WORM compliance; deletion is cryptographically forbidden.
                      </li>
                    ) : (
                      <li>Standard deletion protection via RetroVault Dual-Auth Mass Deletion Guard.</li>
                    )}
                  </ul>
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-[#808080]">
                  {selectedTier.provider_type !== 'LOCAL' && (
                    <button
                      onClick={() => setOffloadTarget(selectedTier)}
                      className="win-btn px-4 py-1 font-bold"
                    >
                      Trigger Offload Sweep Now
                    </button>
                  )}
                </div>
              </>
            ) : (
              <div className="text-gray-500 text-center py-8">Select a storage tier to inspect configuration.</div>
            )}
          </div>
        </div>
      )}

      {/* Create Storage Tier Modal */}
      <WinDialog
        isOpen={showCreateModal}
        title="Create New Storage Tier — [RetroVault V12]"
        icon={<HardDriveIcon size={16} />}
        onClose={() => setShowCreateModal(false)}
        width="500px"
      >
        <form onSubmit={handleCreateTier} className="flex flex-col gap-3 p-1 font-sans text-xs">
          <div className="flex flex-col gap-1">
            <label className="font-bold text-[11px]">Storage Tier Name *:</label>
            <input
              type="text"
              className="win-inset px-2 py-1 bg-white text-xs"
              placeholder="e.g. AWS S3 Glacier Deep Archive"
              value={newTierName}
              onChange={(e) => setNewTierName(e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1">
              <label className="font-bold text-[11px]">Tier Class *:</label>
              <select
                className="win-inset px-2 py-1 bg-white text-xs"
                value={newTierType}
                onChange={(e) => setNewTierType(e.target.value as any)}
              >
                <option value="HOT">HOT (Low Latency / Local)</option>
                <option value="COOL">COOL (Infrequent Access)</option>
                <option value="COLD">COLD (Archive Vault)</option>
                <option value="ARCHIVE">ARCHIVE (Deep Glacier / Tape)</option>
              </select>
            </div>

            <div className="flex flex-col gap-1">
              <label className="font-bold text-[11px]">Provider *:</label>
              <select
                className="win-inset px-2 py-1 bg-white text-xs"
                value={newProviderType}
                onChange={(e) => setNewProviderType(e.target.value as any)}
              >
                <option value="AWS_S3">Amazon Web Services (S3)</option>
                <option value="AZURE_BLOB">Microsoft Azure Blob</option>
                <option value="S3_COMPATIBLE">S3-Compatible (MinIO/Ceph)</option>
                <option value="LOCAL">Local Filesystem / SAN</option>
              </select>
            </div>
          </div>

          {newProviderType !== 'LOCAL' && (
            <div className="flex flex-col gap-1">
              <label className="font-bold text-[11px]">Linked Cloud Credential:</label>
              <select
                className="win-inset px-2 py-1 bg-white text-xs"
                value={newCredId}
                onChange={(e) => setNewCredId(e.target.value)}
              >
                <option value="">-- Select Credential --</option>
                {credentials.map((c: CloudCredential) => (
                  <option key={c.credential_id} value={c.credential_id}>
                    {c.name} ({c.bucket_name} - {c.region})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Object Lock Configuration */}
          <div className="win-inset p-2 bg-[#f4f4f4] flex flex-col gap-2">
            <label className="flex items-center gap-2 font-bold cursor-pointer">
              <input
                type="checkbox"
                checked={newObjectLock}
                onChange={(e) => setNewObjectLock(e.target.checked)}
              />
              <span>Enable WORM Object Lock Immutability</span>
            </label>

            {newObjectLock && (
              <div className="grid grid-cols-2 gap-2 pl-4 pt-1">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-bold">Lock Mode:</label>
                  <select
                    className="win-inset px-1.5 py-0.5 bg-white text-[11px]"
                    value={newLockMode}
                    onChange={(e) => setNewLockMode(e.target.value as any)}
                  >
                    <option value="COMPLIANCE">COMPLIANCE (Strict WORM)</option>
                    <option value="GOVERNANCE">GOVERNANCE (Admin Override)</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-bold">Retention (Days):</label>
                  <input
                    type="number"
                    className="win-inset px-1.5 py-0.5 bg-white text-[11px]"
                    value={newRetentionDays}
                    onChange={(e) => setNewRetentionDays(parseInt(e.target.value, 10))}
                    min={1}
                    max={3650}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-[#808080]">
            <button
              type="button"
              onClick={() => setShowCreateModal(false)}
              className="win-btn px-3 py-1"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="win-btn px-4 py-1 font-bold bg-[#dcdcdc]"
              disabled={submitting}
            >
              {submitting ? 'Creating...' : 'Create Tier'}
            </button>
          </div>
        </form>
      </WinDialog>

      {/* Offload Confirmation Modal */}
      <WinDialog
        isOpen={Boolean(offloadTarget)}
        title="Confirm Storage Offload Operation — [RetroVault V12]"
        icon={<HardDriveIcon size={16} />}
        onClose={() => {
          if (!offloadSubmitting) setOffloadTarget(null);
        }}
        width="440px"
      >
        <div className="flex flex-col gap-3 p-1 font-sans text-xs">
          <div className="win-inset p-2.5 bg-[#f0f4ff] border-l-4 border-[#000080]">
            <p className="font-bold text-xs text-[#000080]">
              Offload Target: {offloadTarget?.name} ({offloadTarget?.provider_type})
            </p>
            <p className="text-[11px] text-gray-700 mt-1">
              Eligible CAS data chunks will be encrypted and transferred to cold/archive storage. Active write blocks remain on NVMe cache.
            </p>
          </div>

          <div className="flex flex-col gap-1">
            <label className="font-bold text-[11px]">Offload Threshold (Older than days):</label>
            <input
              type="number"
              className="win-inset px-2 py-1 bg-white text-xs"
              value={offloadOlderThanDays}
              onChange={(e) => setOffloadOlderThanDays(parseInt(e.target.value, 10) || 1)}
              min={1}
              max={365}
              disabled={offloadSubmitting}
            />
            <span className="text-[10px] text-gray-500">
              Only recovery points older than this threshold will be migrated to the cold tier.
            </span>
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-[#808080]">
            <button
              onClick={() => setOffloadTarget(null)}
              className="win-btn px-3 py-1"
              disabled={offloadSubmitting}
            >
              Cancel
            </button>
            <button
              onClick={executeOffload}
              className="win-btn px-4 py-1 font-bold bg-[#dcdcdc]"
              disabled={offloadSubmitting}
            >
              {offloadSubmitting ? 'Starting Offload...' : 'Confirm Offload'}
            </button>
          </div>
        </div>
      </WinDialog>
    </div>
  );
};

export default StorageTiersPage;
