import React from 'react';
import { useApp } from '../../context/AppContext';
import { InfoIcon, WarningIcon, ErrorIcon, CheckIcon } from './WinIcons';

export const WinToastContainer: React.FC = () => {
  const { toasts, removeToast } = useApp();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-10 right-4 z-50 flex flex-col gap-2 pointer-events-auto max-w-sm">
      {toasts.map((toast) => {
        let icon = <InfoIcon size={16} />;
        let titleBg = 'bg-[#000080] text-white';

        if (toast.type === 'error') {
          icon = <ErrorIcon size={16} />;
          titleBg = 'bg-[#800000] text-white';
        } else if (toast.type === 'warning') {
          icon = <WarningIcon size={16} />;
          titleBg = 'bg-[#808000] text-black';
        } else if (toast.type === 'success') {
          icon = <CheckIcon size={14} />;
          titleBg = 'bg-[#006000] text-white';
        }

        return (
          <div
            key={toast.id}
            className="win-outset bg-[#c0c0c0] shadow-xl p-0.5 select-none w-80 text-[11px] font-sans"
          >
            {/* Header */}
            <div className={`flex items-center justify-between px-1.5 py-0.5 ${titleBg} font-bold text-[11px]`}>
              <div className="flex items-center gap-1.5 truncate">
                <span className="shrink-0">{icon}</span>
                <span className="truncate">{toast.title}</span>
              </div>
              <button
                type="button"
                className="win-ctrl-btn text-[9px] w-3.5 h-3"
                onClick={() => removeToast(toast.id)}
              >
                ✕
              </button>
            </div>

            {/* Body */}
            <div className="p-2 text-black flex flex-col gap-1 bg-[#ffffe1] border border-[#808080] m-1">
              <p className="leading-snug">{toast.message}</p>
              <span className="text-[9px] font-mono text-[#606060] self-end">
                {toast.timestamp}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
