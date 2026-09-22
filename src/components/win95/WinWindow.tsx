import React from 'react';
import type { ReactNode } from 'react';
import { WinTitleBar } from './WinTitleBar';

export interface WinWindowProps {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  headerControls?: boolean;
  onClose?: () => void;
  onMinimize?: () => void;
  onMaximize?: () => void;
  active?: boolean;
}

export const WinWindow: React.FC<WinWindowProps> = ({
  title,
  icon,
  children,
  className = '',
  headerControls = true,
  onClose,
  onMinimize,
  onMaximize,
  active = true,
}) => {
  return (
    <div className={`win-outset bg-[#c0c0c0] flex flex-col overflow-hidden ${className}`}>
      <WinTitleBar
        title={title}
        icon={icon}
        active={active}
        showControls={headerControls}
        onClose={onClose}
        onMinimize={onMinimize}
        onMaximize={onMaximize}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
};
