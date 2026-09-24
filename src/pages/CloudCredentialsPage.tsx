import React, { useState, useEffect } from 'react';
import { v12Api, parseApiError } from '../api/v12';
import type { CloudCredential, CloudCredentialCreate } from '../api/v12';
import { CloudCredentialForm } from '../components/v12/CloudCredentialForm';
import { WinDialog } from '../components/win95/WinDialog';
import { CloudStorageIcon, RefreshIcon, ShieldCheckIcon } from '../components/win95/WinIcons';

export const CloudCredentialsPage: React.FC = () => {
  const [credentials, setCredentials] = useState<CloudCredential[]>([]);
  const [selectedCred, setSelectedCred] = useState<CloudCredential | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState<boolean>(false);
  const [deleteTarget, setDeleteTarget] = useState<CloudCredential | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadCredentials = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await v12Api.listCloudCredentials();
      setCredentials(data);
      if (data.length > 0 && !selectedCred) {
        setSelectedCred(data[0]);
      }
    } catch (err: unknown) {
      setError(parseApiError(err, 'Failed to retrieve cloud credentials'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCredentials();
  }, []);

  const handleCreateCredential = async (data: CloudCredentialCreate) => {
    try {
      const created = await v12Api.createCloudCredential(data);
      setActionMessage(`Cloud credential "${created.name}" securely stored.`);
      await loadCredentials();
    } catch (err: unknown) {
      setActionMessage(`Credential creation error: ${parseApiError(err)}`);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await v12Api.deleteCloudCredential(deleteTarget.credential_id);
      setActionMessage(`Cloud credential "${deleteTarget.name}" deleted.`);
      setDeleteTarget(null);
      await loadCredentials();
    } catch (err: unknown) {
      setActionMessage(`Delete error: ${parseApiError(err)}`);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Title Bar */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span className="bg-[#000080] text-white px-1.5 py-0.5 rounded text-[10px]">V12</span>
            Cloud Provider Authentication & Credential Vault
          </h2>
          <p className="text-[11px] text-gray-700">
            Encrypted management of S3 access keys, Azure Blob storage SAS keys, and custom endpoints
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <button
            onClick={() => setShowAddForm(true)}
            className="win-btn px-3 py-1 font-bold bg-[#dcdcdc]"
          >
            + Add Cloud Credential
          </button>
          <button onClick={loadCredentials} className="win-btn px-3 py-1 flex items-center gap-1">
            <RefreshIcon size={12} /> Refresh
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-xs font-semibold flex justify-between items-center">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="win-btn text-[10px] px-1.5 py-0.5">
            Dismiss
          </button>
        </div>
      )}

      {/* Main Grid: Credential Table + Detail Inspector */}
      {loading ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3">
          <div className="text-xs font-bold text-gray-700">Accessing hardware-encrypted credential store...</div>
          <div className="w-64 h-4 win-inset-gray bg-[#dfdfdf] relative overflow-hidden">
            <div className="h-full bg-[#000080] animate-pulse w-3/4" />
          </div>
        </div>
      ) : error ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3 text-center">
          <div className="text-[#cc0000] font-bold text-sm">Failed to Load Credentials</div>
          <div className="text-xs text-gray-700 max-w-md">{error}</div>
          <button onClick={loadCredentials} className="win-btn px-4 py-1.5 font-bold">
            Retry Connection
          </button>
        </div>
      ) : credentials.length === 0 ? (
        <div className="flex-1 win-inset bg-white p-8 flex flex-col items-center justify-center gap-3 text-center">
          <CloudStorageIcon size={32} />
          <div className="font-bold text-sm">No Cloud Credentials Configured</div>
          <div className="text-xs text-gray-600 max-w-sm">
            Add AWS S3 or Azure Blob credentials to link cloud repositories for offload and Object Lock immutability.
          </div>
          <button onClick={() => setShowAddForm(true)} className="win-btn px-4 py-1.5 font-bold">
            Add First Cloud Credential
          </button>
        </div>
      ) : (
        <div className="flex-1 flex gap-2 min-h-0">
          {/* Table View */}
          <div className="flex-1 win-inset bg-white overflow-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="bg-[#e0e0e0] sticky top-0 border-b border-[#808080]">
                <tr>
                  <th className="p-1.5 border-r border-[#808080]">Credential Name</th>
                  <th className="p-1.5 border-r border-[#808080]">Provider</th>
                  <th className="p-1.5 border-r border-[#808080]">Bucket / Container</th>
                  <th className="p-1.5 border-r border-[#808080]">Region</th>
                  <th className="p-1.5 border-r border-[#808080]">Access Key</th>
                  <th className="p-1.5 border-r border-[#808080]">Status</th>
                  <th className="p-1.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {credentials.map((c) => {
                  const isSelected = selectedCred?.credential_id === c.credential_id;
                  return (
                    <tr
                      key={c.credential_id}
                      onClick={() => setSelectedCred(c)}
                      className={`cursor-pointer border-b border-gray-200 select-none ${
                        isSelected ? 'bg-[#000080] text-white' : 'hover:bg-[#f0f0f0]'
                      }`}
                    >
                      <td className="p-1.5 font-bold">{c.name}</td>
                      <td className="p-1.5 font-mono">{c.provider_type}</td>
                      <td className="p-1.5">{c.bucket_name}</td>
                      <td className="p-1.5">{c.region}</td>
                      <td className="p-1.5 font-mono text-[10px]">{c.access_key_id}</td>
                      <td className="p-1.5">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            c.status === 'VALID'
                              ? isSelected
                                ? 'bg-green-300 text-black'
                                : 'bg-green-100 text-green-800'
                              : isSelected
                              ? 'bg-yellow-300 text-black'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="p-1.5">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteTarget(c);
                          }}
                          className={`win-btn text-[10px] px-2 py-0.5 ${
                            isSelected ? 'bg-[#c0c0c0] text-black' : ''
                          }`}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Right Inspector */}
          <div className="w-80 win-outset p-3 bg-[#dcdcdc] flex flex-col gap-3 overflow-auto">
            {selectedCred ? (
              <>
                <div className="flex justify-between items-center border-b border-[#808080] pb-2">
                  <h3 className="font-bold text-sm flex items-center gap-2">
                    <ShieldCheckIcon size={16} />
                    <span>Credential Security Detail</span>
                  </h3>
                  <span className="font-mono text-[10px] text-gray-600">{selectedCred.credential_id}</span>
                </div>

                <div className="win-inset bg-white p-2.5 flex flex-col gap-2">
                  <div className="text-[11px] font-bold text-[#000080] border-b border-gray-200 pb-1">
                    Redacted Security Profile
                  </div>
                  <div className="flex flex-col gap-1 text-[11px]">
                    <div>
                      <span className="text-gray-600 block">Access Key ID:</span>
                      <code className="bg-gray-100 p-0.5 border border-gray-300 font-mono text-[10px] block">
                        {selectedCred.access_key_id}
                      </code>
                    </div>
                    <div>
                      <span className="text-gray-600 block">Secret Access Key:</span>
                      <code className="bg-red-50 text-red-900 font-bold p-0.5 border border-red-300 font-mono text-[10px] block">
                        {selectedCred.secret_access_key_preview}
                      </code>
                    </div>
                    <div>
                      <span className="text-gray-600 block">Target S3 Bucket / Blob:</span>
                      <strong className="block">{selectedCred.bucket_name}</strong>
                    </div>
                    <div>
                      <span className="text-gray-600 block">Storage Region:</span>
                      <strong className="block">{selectedCred.region}</strong>
                    </div>
                    {selectedCred.endpoint_url && (
                      <div>
                        <span className="text-gray-600 block">Custom Endpoint:</span>
                        <code className="text-[10px] block truncate">{selectedCred.endpoint_url}</code>
                      </div>
                    )}
                    <div>
                      <span className="text-gray-600 block">Last Integrity Verification:</span>
                      <span className="text-gray-800 text-[10px]">
                        {selectedCred.last_verified_at
                          ? new Date(selectedCred.last_verified_at).toLocaleString()
                          : 'Untested'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="win-inset p-2 bg-[#ffffe0] border border-[#808080] text-[10px] text-gray-700">
                  <strong>Zero-Trust Guarantee:</strong> RetroVault never stores secret keys in plain text. Secret values are inaccessible via the REST API after creation.
                </div>

                <div className="flex justify-end pt-2 border-t border-[#808080]">
                  <button
                    onClick={() => setDeleteTarget(selectedCred)}
                    className="win-btn px-3 py-1 font-bold text-[#cc0000]"
                  >
                    Delete Credential...
                  </button>
                </div>
              </>
            ) : (
              <div className="text-gray-500 text-center py-8">Select a credential to inspect details.</div>
            )}
          </div>
        </div>
      )}

      {/* Add Credential Modal */}
      <CloudCredentialForm
        isOpen={showAddForm}
        onClose={() => setShowAddForm(false)}
        onSubmit={handleCreateCredential}
      />

      {/* Delete Confirmation Modal */}
      <WinDialog
        isOpen={Boolean(deleteTarget)}
        title="Confirm Credential Deletion — [Security Safeguard]"
        icon={<CloudStorageIcon size={16} />}
        onClose={() => setDeleteTarget(null)}
        width="420px"
      >
        <div className="flex flex-col gap-3 p-1 font-sans text-xs">
          <div className="win-inset p-2.5 bg-[#ffebee] border-l-4 border-[#cc0000]">
            <p className="font-bold text-[#cc0000]">Warning: Deleting Cloud Credential</p>
            <p className="text-[11px] text-gray-800 mt-1">
              Are you sure you want to remove <strong>{deleteTarget?.name}</strong>? Any storage tiers relying on this credential will transition to an OFFLINE state.
            </p>
          </div>
          <div className="flex justify-end gap-2 pt-2 border-t border-[#808080]">
            <button onClick={() => setDeleteTarget(null)} className="win-btn px-3 py-1">
              Cancel
            </button>
            <button onClick={handleDeleteConfirm} className="win-btn px-4 py-1 font-bold bg-[#ffebee] text-[#cc0000]">
              Confirm Delete
            </button>
          </div>
        </div>
      </WinDialog>
    </div>
  );
};

export default CloudCredentialsPage;
