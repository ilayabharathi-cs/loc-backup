import React from 'react';
import type { ButtonHTMLAttributes } from 'react';
import { useApp } from '../../context/AppContext';

export interface WinButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  isDefault?: boolean;
  active?: boolean;
  size?: 'sm' | 'md' | 'lg';
  playSound?: boolean;
}

export const WinButton: React.FC<WinButtonProps> = ({
  children,
  className = '',
  isDefault = false,
  active = false,
  size = 'md',
  onClick,
  disabled,
  playSound = true,
  ...props
}) => {
  const { playWin95Sound } = useApp();

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (!disabled && playSound) {
      playWin95Sound('click');
    }
    if (onClick) {
      onClick(e);
    }
  };

  const sizeClasses = {
    sm: 'text-[10px] px-1.5 py-0.5 min-h-[19px]',
    md: 'text-[11px] px-2.5 py-1 min-h-[22px]',
    lg: 'text-[12px] px-3.5 py-1.5 min-h-[26px]',
  }[size];

  return (
    <button
      className={`win-btn ${active ? 'pressed' : ''} ${isDefault ? 'win-btn-default' : ''} ${sizeClasses} select-none font-sans font-medium tracking-tight ${className}`}
      onClick={handleClick}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};
