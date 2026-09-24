import React, { useState } from 'react';
import type { CloudCredentialCreate, CloudProviderType } from '../../api/v12';
import { WinDialog } from '../win95/WinDialog';
import { CloudStorageIcon } from '../win95/WinIcons';

interface CloudCredentialFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CloudCredentialCreate) => Promise<void>;
  loading?: boolean;
}

export const CloudCredentialForm: React.FC<CloudCredentialFormProps> = ({
  isOpen,
  onClose,
  onSubmit,
  loading = false
}) => {
  const [name, setName] = useState('');
  const [providerType, setProviderType] = useState<CloudProviderType>('AWS_S3');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [bucketName, setBucketName] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [accessKeyId, setAccessKeyId] = useState('');
  const [secretAccessKey, setSecretAccessKey] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim() || !bucketName.trim() || !accessKeyId.trim() || !secretAccessKey.trim()) {
      setError('All required fields marked with * must be filled.');
      return;
    }

    try {
      await onSubmit({
        name: name.trim(),
        provider_type: providerType,
        endpoint_url: endpointUrl.trim() || undefined,
        bucket_name: bucketName.trim(),
        region: region.trim(),
        access_key_id: accessKeyId.trim(),
        secret_access_key: secretAccessKey.trim()
      });

      // Clear sensitive secrets immediately from React state
      setSecretAccessKey('');
      setAccessKeyId('');
      setName('');
      setBucketName('');
      setEndpointUrl('');
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to register cloud credential';
      setError(msg);
    }
  };

  return (
    <WinDialog
      isOpen={isOpen}
      title="Add Cloud Storage Credential — [Security Context]"
      icon={<CloudStorageIcon size={16} />}
      onClose={() => {
        setSecretAccessKey(''); // Clear secret on cancel
        onClose();
      }}
      width="540px"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-3 p-1 font-sans text-xs">
        {/* Warning banner */}
        <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-[11px]">
          <strong>Security Notice:</strong> Sensitive tokens and secret access keys are encrypted upon receipt and never logged or displayed in plain text.
        </div>

        {error && (
          <div className="win-inset p-2 bg-[#ffebee] border-l-4 border-[#cc0000] text-[#cc0000] font-bold text-[11px]">
            {error}
          </div>
        )}

        <div className="flex flex-col gap-2">
          {/* Credential Name */}
          <div className="flex flex-col gap-0.5">
            <label className="font-bold text-[11px]">Credential Friendly Name *:</label>
            <input
              type="text"
              className="win-inset px-2 py-1 bg-white text-xs"
              placeholder="e.g. AWS Primary S3 Storage Vault"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={loading}
              required
            />
          </div>

          {/* Provider Type */}
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-0.5">
              <label className="font-bold text-[11px]">Cloud Provider *:</label>
              <select
                className="win-inset px-2 py-1 bg-white text-xs"
                value={providerType}
                onChange={(e) => {
                  const val = e.target.value as CloudProviderType;
                  setProviderType(val);
                  if (val === 'AZURE_BLOB' && region === 'us-east-1') setRegion('westus2');
                  if (val === 'AWS_S3' && region === 'westus2') setRegion('us-east-1');
                }}
                disabled={loading}
              >
                <option value="AWS_S3">Amazon Web Services (S3)</option>
                <option value="AZURE_BLOB">Microsoft Azure Blob Storage</option>
                <option value="S3_COMPATIBLE">S3-Compatible (MinIO / Ceph / Wasabi)</option>
              </select>
            </div>

            <div className="flex flex-col gap-0.5">
              <label className="font-bold text-[11px]">Region / Location *:</label>
              <input
                type="text"
                className="win-inset px-2 py-1 bg-white text-xs"
                placeholder="e.g. us-east-1, eu-central-1"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                disabled={loading}
                required
              />
            </div>
          </div>

          {/* Bucket Name & Custom Endpoint */}
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-0.5">
              <label className="font-bold text-[11px]">Bucket / Container Name *:</label>
              <input
                type="text"
                className="win-inset px-2 py-1 bg-white text-xs"
                placeholder="retrovault-backup-bucket"
                value={bucketName}
                onChange={(e) => setBucketName(e.target.value)}
                disabled={loading}
                required
              />
            </div>

            <div className="flex flex-col gap-0.5">
              <label className="font-bold text-[11px]">Custom Endpoint URL (Optional):</label>
              <input
                type="text"
                className="win-inset px-2 py-1 bg-white text-xs"
                placeholder="https://s3.custom-domain.local"
                value={endpointUrl}
                onChange={(e) => setEndpointUrl(e.target.value)}
                disabled={loading}
              />
            </div>
          </div>

          {/* Access Key ID */}
          <div className="flex flex-col gap-0.5">
            <label className="font-bold text-[11px]">Access Key ID / Account Name *:</label>
            <input
              type="text"
              className="win-inset px-2 py-1 bg-white text-xs font-mono"
              placeholder="AKIAIOSFODNN7EXAMPLE"
              value={accessKeyId}
              onChange={(e) => setAccessKeyId(e.target.value)}
              disabled={loading}
              required
            />
          </div>

          {/* Secret Access Key (Password Masked) */}
          <div className="flex flex-col gap-0.5">
            <label className="font-bold text-[11px]">Secret Access Key / SAS Token *:</label>
            <input
              type="password"
              className="win-inset px-2 py-1 bg-white text-xs font-mono"
              placeholder="••••••••••••••••••••••••••••••••"
              value={secretAccessKey}
              onChange={(e) => setSecretAccessKey(e.target.value)}
              disabled={loading}
              autoComplete="new-password"
              required
            />
            <span className="text-[10px] text-gray-600">
              Value is redacted immediately after transmission and stored under hardware-isolated cryptographic key.
            </span>
          </div>
        </div>

        {/* Buttons */}
        <div className="flex justify-end gap-2 pt-2 border-t border-[#808080]">
          <button
            type="button"
            onClick={() => {
              setSecretAccessKey('');
              onClose();
            }}
            className="win-btn px-3 py-1"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="win-btn px-4 py-1 font-bold bg-[#dcdcdc]"
            disabled={loading}
          >
            {loading ? 'Validating...' : 'Save & Encrypt Credential'}
          </button>
        </div>
      </form>
    </WinDialog>
  );
};

export default CloudCredentialForm;
