import React, { useState, useEffect } from 'react';
import { WinPanel } from '../components/win95/WinPanel';
import { WinButton } from '../components/win95/WinButton';
import { WinTable, type Column } from '../components/win95/WinTable';
import { WinBadge } from '../components/win95/WinBadge';
import { WinDialog } from '../components/win95/WinDialog';
import { WinInput, WinSelect, WinCheckbox } from '../components/win95/WinFormControls';
import { HardDriveIcon, ShieldCheckIcon } from '../components/win95/WinIcons';
import { useApp } from '../context/AppContext';
import {
  getStorageTiers,
  createStorageTier,
  deleteStorageTier,
  validateStorageTier,
  testStorageTierConnection,
  offloadObjects,
  getCloudCredentials,
  createCloudCredential,
  deleteCloudCredential,
  type StorageTierResponse,
  type CloudCredentialResponse,
  type StorageTierCreate,
  type CloudCredentialCreate
} from '../api/cloud';

export const CloudStoragePage: React.FC = () => {
  const { addToast, playWin95Sound } = useApp();

  const [tiers, setTiers] = useState<StorageTierResponse[]>([]);
  const [credentials, setCredentials] = useState<CloudCredentialResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [showCreateTier, setShowCreateTier] = useState<boolean>(false);
  const [showCredManager, setShowCredManager] = useState<boolean>(false);
  const [showOffloadModal, setShowOffloadModal] = useState<boolean>(false);
  const [selectedTierForOffload, setSelectedTierForOffload] = useState<StorageTierResponse | null>(null);

  // Testing connection state
  const [testingTierId, setTestingTierId] = useState<string | null>(null);

  // Form states
  const [tierForm, setTierForm] = useState<StorageTierCreate>({
    name: '',
    tier_type: 'CLOUD_S3',
    provider: 's3',
    credential_id: '',
    bucket: '',
    prefix: 'vault-backups',
    object_lock_enabled: false,
    retention_period_days: 30,
    immutability_mode: 'NONE',
    is_default: false
  });

  const [credForm, setCredForm] = useState<CloudCredentialCreate>({
    name: '',
    provider: 's3',
    access_key: '',
    secret_key: '',
    endpoint: '',
    region: 'us-east-1',
    prefix: '',
    use_tls: true,
    verify_ssl: true
  });

  const [offloadObjectIdsText, setOffloadObjectIdsText] = useState<string>('');
  const [offloadLoading, setOffloadLoading] = useState<boolean>(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [tiersRes, credsRes] = await Promise.all([
        getStorageTiers(),
        getCloudCredentials()
      ]);
      if (tiersRes.success) setTiers(tiersRes.data || []);
      if (credsRes.success) setCredentials(credsRes.data || []);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Failed to load cloud storage data';
      setError(msg);
      addToast('Cloud Storage Error', msg, 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTestConnection = async (tier: StorageTierResponse) => {
    setTestingTierId(tier.tier_id);
    try {
      playWin95Sound('click');
      const res = await testStorageTierConnection(tier.tier_id);
      if (res.success) {
        addToast('Connection Success', `Tier '${tier.name}' connected successfully to bucket '${tier.bucket}'`, 'info');
      } else {
        addToast('Connection Warning', res.message || 'Connection test did not return positive status', 'warning');
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Connection failed';
      addToast('Connection Failed', msg, 'error');
    } finally {
      setTestingTierId(null);
    }
  };

  const handleValidateTier = async (tier: StorageTierResponse) => {
    try {
      playWin95Sound('click');
      const res = await validateStorageTier(tier.tier_id);
      if (res.success && res.data.valid) {
        addToast('Validation Passed', `Storage tier '${tier.name}' validated. State: ${res.data.state}`, 'info');
      } else {
        addToast('Validation Failed', res.data?.error || 'Tier validation failed', 'error');
      }
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Validation error';
      addToast('Validation Error', msg, 'error');
    }
  };

  const handleDeleteTier = async (tier: StorageTierResponse) => {
    if (!window.confirm(`Are you sure you want to delete storage tier '${tier.name}'? Existing offloaded objects may become inaccessible.`)) {
      return;
    }
    try {
      playWin95Sound('click');
      await deleteStorageTier(tier.tier_id);
      addToast('Storage Tier Deleted', `Tier '${tier.name}' removed`, 'info');
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Failed to delete tier';
      addToast('Delete Failed', msg, 'error');
    }
  };

  const handleCreateTier = async () => {
    if (!tierForm.name.trim() || !tierForm.bucket.trim()) {
      addToast('Form Validation', 'Tier name and bucket name are required', 'warning');
      return;
    }
    try {
      playWin95Sound('click');
      const payload: StorageTierCreate = {
        ...tierForm,
        credential_id: tierForm.credential_id ? String(tierForm.credential_id) : undefined
      };
      await createStorageTier(payload);
      addToast('Storage Tier Created', `Storage tier '${tierForm.name}' configured`, 'info');
      setShowCreateTier(false);
      setTierForm({
        name: '',
        tier_type: 'CLOUD_S3',
        provider: 's3',
        credential_id: '',
        bucket: '',
        prefix: 'vault-backups',
        object_lock_enabled: false,
        retention_period_days: 30,
        immutability_mode: 'NONE',
        is_default: false
      });
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Failed to create tier';
      addToast('Create Tier Failed', msg, 'error');
    }
  };

  const handleCreateCredential = async () => {
    if (!credForm.name.trim() || !credForm.access_key.trim() || !credForm.secret_key.trim()) {
      addToast('Form Validation', 'Name, Access Key, and Secret Key are required', 'warning');
      return;
    }
    try {
      playWin95Sound('click');
      await createCloudCredential(credForm);
      addToast('Credential Saved', `Encrypted credentials '${credForm.name}' stored`, 'info');
      setCredForm({
        name: '',
        provider: 's3',
        access_key: '',
        secret_key: '',
        endpoint: '',
        region: 'us-east-1',
        prefix: '',
        use_tls: true,
        verify_ssl: true
      });
      const credsRes = await getCloudCredentials();
      if (credsRes.success) setCredentials(credsRes.data || []);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Failed to save credential';
      addToast('Credential Error', msg, 'error');
    }
  };

  const handleDeleteCredential = async (cred: CloudCredentialResponse) => {
    if (!window.confirm(`Delete credential '${cred.name}'? Tiers referencing this credential may fail validation.`)) {
      return;
    }
    try {
      playWin95Sound('click');
      await deleteCloudCredential(cred.credential_id);
      addToast('Credential Removed', `Credential '${cred.name}' deleted`, 'info');
      const credsRes = await getCloudCredentials();
      if (credsRes.success) setCredentials(credsRes.data || []);
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Failed to delete credential';
      addToast('Delete Error', msg, 'error');
    }
  };

  const handleExecuteOffload = async () => {
    if (!selectedTierForOffload) return;
    const objectIds = offloadObjectIdsText
      .split(/[\n, ]+/)
      .map(s => s.trim())
      .filter(s => s.length > 0);

    if (objectIds.length === 0) {
      addToast('Offload Validation', 'Please enter at least one CAS StorageObject ID', 'warning');
      return;
    }

    setOffloadLoading(true);
    try {
      playWin95Sound('click');
      const res = await offloadObjects(selectedTierForOffload.tier_id, objectIds);
      if (res.success) {
        addToast(
          'Offload Completed',
          `Offloaded: ${res.data.offloaded_count}, Failed: ${res.data.failed_count} to tier '${selectedTierForOffload.name}'`,
          res.data.failed_count === 0 ? 'info' : 'warning'
        );
        setShowOffloadModal(false);
        setOffloadObjectIdsText('');
      }
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.response?.data?.detail || err.message || 'Offload execution failed';
      addToast('Offload Failed', msg, 'error');
    } finally {
      setOffloadLoading(false);
    }
  };

  const tierColumns: Column<StorageTierResponse>[] = [
    {
      key: 'name',
      header: 'Tier Name / ID',
      sortable: true,
      render: (t) => (
        <div>
          <div className="font-bold text-black flex items-center gap-1.5">
            <HardDriveIcon size={14} />
            <span>{t.name}</span>
            {t.is_default && (
              <span className="text-[9px] bg-[#000080] text-white font-mono px-1 py-0.2 rounded-xs font-bold">
                DEFAULT
              </span>
            )}
          </div>
          <div className="text-[10px] text-[#555] font-mono">{t.tier_id}</div>
        </div>
      )
    },
    {
      key: 'provider',
      header: 'Provider & Type',
      width: '120px',
      render: (t) => (
        <div className="text-[11px]">
          <span className="font-bold uppercase font-mono">{t.provider}</span>
          <div className="text-[10px] text-[#666]">{t.tier_type}</div>
        </div>
      )
    },
    {
      key: 'bucket',
      header: 'Bucket & Prefix',
      render: (t) => (
        <div className="font-mono text-[11px] truncate">
          <span className="font-semibold text-black">{t.bucket}</span>
          {t.prefix && <span className="text-[#666]">/{t.prefix}</span>}
        </div>
      )
    },
    {
      key: 'state',
      header: 'Status',
      width: '110px',
      sortable: true,
      render: (t) => (
        <div>
          <WinBadge status={t.state} label={t.state} />
          {t.error_message && (
            <div className="text-[9px] text-[#aa0000] truncate max-w-[100px]" title={t.error_message}>
              {t.error_message}
            </div>
          )}
        </div>
      )
    },
    {
      key: 'object_lock_enabled',
      header: 'WORM Immutability',
      width: '130px',
      render: (t) => (
        <div className="text-[10px]">
          {t.object_lock_enabled ? (
            <span className="font-bold text-[#006600] flex items-center gap-1">
              <ShieldCheckIcon size={12} />
              <span>{t.immutability_mode} ({t.retention_period_days}d)</span>
            </span>
          ) : (
            <span className="text-[#777]">None</span>
          )}
        </div>
      )
    },
    {
      key: 'last_validated_at',
      header: 'Last Validated',
      width: '130px',
      render: (t) => (
        <div className="text-[10px] font-mono text-[#555]">
          {t.last_validated_at ? new Date(t.last_validated_at).toLocaleString() : 'Never'}
        </div>
      )
    },
    {
      key: 'id',
      header: 'Actions',
      width: '260px',
      render: (t) => (
        <div className="flex items-center gap-1">
          <WinButton
            onClick={() => handleTestConnection(t)}
            disabled={testingTierId === t.tier_id}
            className="text-[10px] py-0.5 px-1.5"
          >
            {testingTierId === t.tier_id ? 'Testing...' : 'Test'}
          </WinButton>
          <WinButton
            onClick={() => handleValidateTier(t)}
            className="text-[10px] py-0.5 px-1.5"
          >
            Validate
          </WinButton>
          <WinButton
            onClick={() => {
              setSelectedTierForOffload(t);
              setShowOffloadModal(true);
            }}
            className="text-[10px] py-0.5 px-1.5"
          >
            Offload
          </WinButton>
          <WinButton
            onClick={() => handleDeleteTier(t)}
            className="text-[10px] py-0.5 px-1.5 text-[#aa0000]"
          >
            Delete
          </WinButton>
        </div>
      )
    }
  ];

  return (
    <div className="flex-1 flex flex-col p-2 gap-2 overflow-y-auto">
      {/* Top Action Toolbar */}
      <div className="win-outset px-3 py-1.5 flex items-center justify-between bg-[#c0c0c0] shrink-0">
        <div className="flex items-center gap-2">
          <HardDriveIcon size={18} />
          <div>
            <h1 className="text-[13px] font-bold text-black m-0 leading-tight">
              RetroVault V12 — Cloud & Hybrid Storage Tiering
            </h1>
            <p className="text-[10px] text-[#505050] m-0">
              S3 / Wasabi / MinIO WORM Object Lock & Verification
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <WinButton onClick={() => setShowCredManager(true)} className="text-[11px] font-bold">
            Manage Credentials ({credentials.length})
          </WinButton>
          <WinButton onClick={() => setShowCreateTier(true)} isDefault className="text-[11px] font-bold">
            + New Storage Tier
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

      {/* Main Tiers Table */}
      <WinPanel title="Configured Hybrid Storage Tiers">
        <div className="min-h-[220px]">
          {loading ? (
            <div className="win-inset bg-white p-4 text-center text-[11px] text-[#666]">
              Loading storage tiers and credentials from control plane...
            </div>
          ) : (
            <WinTable<StorageTierResponse>
              columns={tierColumns}
              data={tiers}
              keyExtractor={(t) => t.tier_id}
              emptyText="No cloud storage tiers configured. Click '+ New Storage Tier' to attach an S3 bucket or MinIO cluster."
            />
          )}
        </div>
      </WinPanel>

      {/* Summary Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        <WinPanel title="Storage Tier Health">
          <div className="flex flex-col gap-1 text-[11px]">
            <div className="flex justify-between">
              <span>Total Tiers:</span>
              <span className="font-bold font-mono">{tiers.length}</span>
            </div>
            <div className="flex justify-between">
              <span>Active / Ready:</span>
              <span className="font-bold font-mono text-[#008800]">
                {tiers.filter(t => t.state === 'READY').length}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Degraded / Error:</span>
              <span className="font-bold font-mono text-[#aa0000]">
                {tiers.filter(t => t.state === 'DEGRADED' || t.state === 'ERROR').length}
              </span>
            </div>
          </div>
        </WinPanel>

        <WinPanel title="WORM Immutability Policy">
          <div className="flex flex-col gap-1 text-[11px]">
            <div className="flex justify-between">
              <span>Compliance Locked Tiers:</span>
              <span className="font-bold font-mono text-[#000080]">
                {tiers.filter(t => t.object_lock_enabled && t.immutability_mode === 'COMPLIANCE').length}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Governance Mode:</span>
              <span className="font-bold font-mono">
                {tiers.filter(t => t.object_lock_enabled && t.immutability_mode === 'GOVERNANCE').length}
              </span>
            </div>
            <div className="text-[10px] text-[#555] italic mt-1">
              Objects locked in Compliance mode cannot be deleted by any administrator before retention expiration.
            </div>
          </div>
        </WinPanel>

        <WinPanel title="Architecture Invariant">
          <div className="text-[10px] text-[#444] leading-relaxed">
            <div className="font-bold text-black mb-1">Local-First Verification:</div>
            All offload operations enforce strict <code className="font-mono bg-white px-1">COPY → VERIFY → RECORD</code> sequence. Checksums are re-validated before CAS references are updated.
          </div>
        </WinPanel>
      </div>

      {/* Dialog: Create Storage Tier */}
      <WinDialog
        isOpen={showCreateTier}
        onClose={() => setShowCreateTier(false)}
        title="Configure S3 Storage Tier"
        icon={<HardDriveIcon size={16} />}
        width={520}
        onOk={handleCreateTier}
        okText="Create Tier"
      >
        <div className="flex flex-col gap-2.5">
          <WinInput
            label="Tier Name *"
            value={tierForm.name}
            onChange={(e) => setTierForm({ ...tierForm, name: e.target.value })}
            placeholder="e.g. AWS-Primary-Vault"
          />

          <div className="grid grid-cols-2 gap-2">
            <WinSelect
              label="Provider Type"
              value={tierForm.provider}
              onChange={(e) => setTierForm({ ...tierForm, provider: e.target.value })}
            >
              <option value="s3">AWS S3</option>
              <option value="minio">MinIO (Self-Hosted)</option>
              <option value="wasabi">Wasabi Hot Cloud</option>
              <option value="mock">In-Memory Mock Provider</option>
            </WinSelect>

            <WinSelect
              label="Tier Classification"
              value={tierForm.tier_type}
              onChange={(e) => setTierForm({ ...tierForm, tier_type: e.target.value })}
            >
              <option value="CLOUD_S3">CLOUD_S3</option>
              <option value="HOT">HOT</option>
              <option value="WARM">WARM</option>
              <option value="COLD">COLD</option>
              <option value="ARCHIVE">ARCHIVE</option>
            </WinSelect>
          </div>

          <WinSelect
            label="Cloud Credential Reference"
            value={tierForm.credential_id || ''}
            onChange={(e) => setTierForm({ ...tierForm, credential_id: e.target.value })}
          >
            <option value="">-- None / Default Environment --</option>
            {credentials.map(c => (
              <option key={c.credential_id} value={c.credential_id}>
                {c.name} ({c.provider.toUpperCase()} - {c.access_key_masked})
              </option>
            ))}
          </WinSelect>

          <div className="grid grid-cols-2 gap-2">
            <WinInput
              label="Bucket Name *"
              value={tierForm.bucket}
              onChange={(e) => setTierForm({ ...tierForm, bucket: e.target.value })}
              placeholder="retrovault-cloud-bucket"
            />
            <WinInput
              label="Prefix Path"
              value={tierForm.prefix || ''}
              onChange={(e) => setTierForm({ ...tierForm, prefix: e.target.value })}
              placeholder="backups"
            />
          </div>

          {/* WORM Object Lock Options */}
          <div className="win-inset p-2 bg-[#f4f4f4] flex flex-col gap-2 mt-1">
            <WinCheckbox
              label="Enable WORM Object Lock (Immutability)"
              checked={tierForm.object_lock_enabled || false}
              onChange={(checked) => setTierForm({ ...tierForm, object_lock_enabled: checked })}
            />

            {tierForm.object_lock_enabled && (
              <div className="grid grid-cols-2 gap-2 pt-1 border-t border-[#dfdfdf]">
                <WinSelect
                  label="Immutability Mode"
                  value={tierForm.immutability_mode}
                  onChange={(e) => setTierForm({ ...tierForm, immutability_mode: e.target.value })}
                >
                  <option value="NONE">NONE</option>
                  <option value="GOVERNANCE">GOVERNANCE (Admin overrideable)</option>
                  <option value="COMPLIANCE">COMPLIANCE (Strict SEC/FINRA)</option>
                </WinSelect>

                <WinInput
                  label="Retention Period (Days)"
                  type="number"
                  min="1"
                  value={tierForm.retention_period_days}
                  onChange={(e) => setTierForm({ ...tierForm, retention_period_days: parseInt(e.target.value) || 0 })}
                />
              </div>
            )}
          </div>

          <WinCheckbox
            label="Set as default cloud offload destination"
            checked={tierForm.is_default || false}
            onChange={(checked) => setTierForm({ ...tierForm, is_default: checked })}
          />
        </div>
      </WinDialog>

      {/* Dialog: Credential Manager */}
      <WinDialog
        isOpen={showCredManager}
        onClose={() => setShowCredManager(false)}
        title="Secure Cloud Credential Store"
        icon={<ShieldCheckIcon size={16} />}
        width={620}
        showFooter={false}
      >
        <div className="flex flex-col gap-3">
          <div className="text-[11px] text-[#444]">
            Credentials are encrypted at rest with PBKDF2-HMAC-SHA256 authenticated encryption. Secret keys are never sent back in API responses.
          </div>

          {/* Existing Credentials List */}
          <div className="win-inset p-2 bg-white max-h-[160px] overflow-y-auto flex flex-col gap-1.5">
            {credentials.length === 0 ? (
              <div className="text-[#808080] text-center py-2 text-[11px]">No credentials stored. Add one below.</div>
            ) : (
              credentials.map(c => (
                <div key={c.credential_id} className="flex items-center justify-between border-b border-[#dfdfdf] pb-1 text-[11px]">
                  <div>
                    <span className="font-bold text-black">{c.name}</span>{' '}
                    <span className="font-mono text-[10px] text-[#555]">({c.provider.toUpperCase()} | {c.access_key_masked})</span>
                    {c.endpoint && <div className="text-[9px] text-[#777] font-mono">{c.endpoint}</div>}
                  </div>
                  <WinButton
                    onClick={() => handleDeleteCredential(c)}
                    className="text-[10px] text-[#aa0000] px-1 py-0.5"
                  >
                    Delete
                  </WinButton>
                </div>
              ))
            )}
          </div>

          {/* Add New Credential Form */}
          <div className="win-outset p-2 bg-[#dfdfdf] flex flex-col gap-2">
            <div className="font-bold text-[11px] text-black">Add New Credential</div>
            <div className="grid grid-cols-2 gap-2">
              <WinInput
                label="Identifier Name *"
                value={credForm.name}
                onChange={(e) => setCredForm({ ...credForm, name: e.target.value })}
                placeholder="aws-production-keys"
              />
              <WinSelect
                label="Provider Backend"
                value={credForm.provider}
                onChange={(e) => setCredForm({ ...credForm, provider: e.target.value })}
              >
                <option value="s3">AWS S3</option>
                <option value="minio">MinIO</option>
                <option value="wasabi">Wasabi</option>
                <option value="mock">Mock</option>
              </WinSelect>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <WinInput
                label="Access Key ID *"
                value={credForm.access_key}
                onChange={(e) => setCredForm({ ...credForm, access_key: e.target.value })}
                placeholder="AKIAIOSFODNN7EXAMPLE"
              />
              <WinInput
                label="Secret Access Key *"
                type="password"
                value={credForm.secret_key}
                onChange={(e) => setCredForm({ ...credForm, secret_key: e.target.value })}
                placeholder="••••••••••••••••••••••••"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <WinInput
                label="Custom Endpoint (optional)"
                value={credForm.endpoint || ''}
                onChange={(e) => setCredForm({ ...credForm, endpoint: e.target.value })}
                placeholder="https://s3.wasabisys.com"
              />
              <WinInput
                label="Region"
                value={credForm.region || ''}
                onChange={(e) => setCredForm({ ...credForm, region: e.target.value })}
                placeholder="us-east-1"
              />
            </div>

            <div className="flex justify-end mt-1">
              <WinButton onClick={handleCreateCredential} isDefault className="text-[11px]">
                Save Encrypted Credential
              </WinButton>
            </div>
          </div>

          <div className="flex justify-end pt-1">
            <WinButton onClick={() => setShowCredManager(false)} className="text-[11px]">
              Close
            </WinButton>
          </div>
        </div>
      </WinDialog>

      {/* Dialog: Manual CAS Offload Trigger */}
      <WinDialog
        isOpen={showOffloadModal}
        onClose={() => setShowOffloadModal(false)}
        title={`Offload CAS Objects → ${selectedTierForOffload?.name || ''}`}
        icon={<HardDriveIcon size={16} />}
        width={480}
        onOk={handleExecuteOffload}
        okText={offloadLoading ? 'Offloading...' : 'Execute Offload'}
        okDisabled={offloadLoading}
      >
        <div className="flex flex-col gap-2">
          <div className="text-[11px] text-[#444]">
            Specify CAS StorageObject identifiers to upload and verify against bucket{' '}
            <code className="font-mono font-bold bg-white px-1">{selectedTierForOffload?.bucket}</code>:
          </div>

          <textarea
            className="win-inset p-2 font-mono text-[11px] bg-white h-24 focus:outline-none"
            placeholder="ivr_obj_1234567890&#10;ivr_obj_abcdef0123"
            value={offloadObjectIdsText}
            onChange={(e) => setOffloadObjectIdsText(e.target.value)}
          />

          <div className="text-[10px] text-[#666] italic">
            Enter one object ID per line or comma-separated. The engine will verify cryptographic hashes before recording remote persistence.
          </div>
        </div>
      </WinDialog>
    </div>
  );
};
export default CloudStoragePage;
