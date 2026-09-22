import React from 'react';
import type { ReactNode } from 'react';
import { WinTitleBar } from './WinTitleBar';
import { WinButton } from './WinButton';

export interface WinDialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  icon?: React.ReactNode;
  children: ReactNode;
  width?: string | number;
  showFooter?: boolean;
  onOk?: () => void;
  okText?: string;
  cancelText?: string;
  okDisabled?: boolean;
  extraFooterButtons?: ReactNode;
}

export const WinDialog: React.FC<WinDialogProps> = ({
  isOpen,
  onClose,
  title,
  icon,
  children,
  width = 480,
  showFooter = true,
  onOk,
  okText = 'OK',
  cancelText = 'Cancel',
  okDisabled = false,
  extraFooterButtons,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className="win-outset bg-[#c0c0c0] flex flex-col shadow-2xl relative select-none max-h-[90vh] overflow-hidden"
        style={{ width: typeof width === 'number' ? `${width}px` : width }}
      >
        <WinTitleBar
          title={title}
          icon={icon}
          onClose={onClose}
          showControls={true}
        />

        <div className="p-3 overflow-y-auto flex-1 text-[11px] font-sans">
          {children}
        </div>

        {showFooter && (
          <div className="p-2.5 bg-[#c0c0c0] border-t border-[#dfdfdf] flex items-center justify-end gap-2 shrink-0">
            {extraFooterButtons}
            {onOk && (
              <WinButton
                isDefault
                onClick={onOk}
                disabled={okDisabled}
                className="min-w-[75px]"
              >
                {okText}
              </WinButton>
            )}
            <WinButton
              onClick={onClose}
              className="min-w-[75px]"
            >
              {cancelText}
            </WinButton>
          </div>
        )}
      </div>
    </div>
  );
};
