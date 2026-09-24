import React, { useState } from 'react';
import { WinDialog } from '../win95/WinDialog';
import { ErrorIcon, WarningIcon, CheckIcon } from '../win95/WinIcons';
import type { ParsedApiError } from '../../api/v12';

interface V12ErrorDialogProps {
  isOpen: boolean;
  error: ParsedApiError | null;
  onClose: () => void;
}

export const V12ErrorDialog: React.FC<V12ErrorDialogProps> = ({
  isOpen,
  error,
  onClose
}) => {
  const [copied, setCopied] = useState(false);

  if (!error) return null;

  const handleCopyId = () => {
    navigator.clipboard.writeText(error.errorId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <WinDialog
      isOpen={isOpen}
      title={`${error.title || 'Application Error'} — [Incident Reference]`}
      icon={<ErrorIcon size={16} />}
      onClose={onClose}
      width="460px"
    >
      <div className="flex flex-col gap-3 p-1 font-sans text-xs">
        {/* Main Error Alert Box */}
        <div className="win-inset p-3 bg-[#ffebee] border-l-4 border-[#cc0000] flex gap-2.5 items-start">
          <ErrorIcon size={24} className="text-[#cc0000] shrink-0 mt-0.5" />
          <div className="flex flex-col gap-1">
            <span className="font-bold text-xs text-[#cc0000]">{error.title}</span>
            <p className="text-[11px] text-gray-800 leading-relaxed">{error.message}</p>
          </div>
        </div>

        {/* Error ID and Metadata Details */}
        <div className="win-inset p-2.5 bg-[#f4f4f4] flex flex-col gap-2">
          <div className="flex justify-between items-center border-b border-gray-300 pb-1.5">
            <span className="text-[10px] text-gray-600 font-bold uppercase">Tracking Reference ID:</span>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-xs font-bold text-[#000080] bg-white px-1.5 py-0.5 border border-gray-400">
                {error.errorId}
              </span>
              <button
                type="button"
                onClick={handleCopyId}
                className="win-btn text-[10px] px-1.5 py-0.5 flex items-center gap-1"
                title="Copy Error ID to clipboard"
              >
                {copied ? <CheckIcon size={10} /> : null}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-1.5 text-[11px]">
            <div>
              <span className="text-gray-600 block text-[10px]">HTTP Status:</span>
              <strong className="font-mono">{error.statusCode ? `HTTP ${error.statusCode}` : 'Client / Network'}</strong>
            </div>
            <div>
              <span className="text-gray-600 block text-[10px]">Timestamp:</span>
              <span className="font-mono text-[10px]">{new Date(error.timestamp).toLocaleTimeString()}</span>
            </div>
          </div>

          {error.details && (
            <div className="mt-1 pt-1 border-t border-gray-300">
              <span className="text-gray-600 block text-[10px]">Additional Diagnostic Context:</span>
              <pre className="font-mono text-[10px] bg-white p-1.5 border border-gray-300 overflow-auto max-h-20 whitespace-pre-wrap">
                {error.details}
              </pre>
            </div>
          )}
        </div>

        {/* Security Notice */}
        <div className="text-[10px] text-gray-600 flex items-center gap-1">
          <WarningIcon size={12} />
          <span>Internal server stack traces and credentials are systematically redacted for security.</span>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2 border-t border-[#808080]">
          <button
            type="button"
            onClick={onClose}
            className="win-btn px-4 py-1 font-bold"
          >
            OK / Close
          </button>
        </div>
      </div>
    </WinDialog>
  );
};

export default V12ErrorDialog;
