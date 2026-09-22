import React from 'react';
import { useApp } from '../../context/AppContext';

export interface WinTitleBarProps {
  title: string;
  icon?: React.ReactNode;
  active?: boolean;
  onMinimize?: () => void;
  onMaximize?: () => void;
  onClose?: () => void;
  showControls?: boolean;
  className?: string;
}

export const WinTitleBar: React.FC<WinTitleBarProps> = ({
  title,
  icon,
  active = true,
  onMinimize,
  onMaximize,
  onClose,
  showControls = true,
  className = '',
}) => {
  const { playWin95Sound } = useApp();

  const handleCtrlClick = (action?: () => void) => {
    playWin95Sound('click');
    if (action) action();
  };

  return (
    <div className={`win-titlebar ${!active ? 'inactive' : ''} ${className}`}>
      <div className="flex items-center gap-1.5 overflow-hidden">
        {icon && <span className="shrink-0">{icon}</span>}
        <span className="truncate select-none font-bold text-[12px]">{title}</span>
      </div>

      {showControls && (
        <div className="flex items-center gap-0.5 ml-2 shrink-0">
          <button
            type="button"
            className="win-ctrl-btn"
            title="Minimize"
            aria-label="Minimize"
            onClick={() => handleCtrlClick(onMinimize)}
          >
            <span className="font-extrabold -mt-1">_</span>
          </button>
          <button
            type="button"
            className="win-ctrl-btn"
            title="Maximize"
            aria-label="Maximize"
            onClick={() => handleCtrlClick(onMaximize)}
          >
            <span className="font-bold text-[10px] -mt-0.5">□</span>
          </button>
          <button
            type="button"
            className="win-ctrl-btn ml-0.5"
            title="Close"
            aria-label="Close"
            onClick={() => handleCtrlClick(onClose)}
          >
            <span className="font-extrabold text-[10px]">✕</span>
          </button>
        </div>
      )}
    </div>
  );
};
