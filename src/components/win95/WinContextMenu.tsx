import React, { useEffect, useRef } from 'react';
import { useApp } from '../../context/AppContext';

export interface ContextMenuItem {
  label: string;
  icon?: React.ReactNode;
  action: () => void;
  divider?: boolean;
  disabled?: boolean;
}

export interface WinContextMenuProps {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}

export const WinContextMenu: React.FC<WinContextMenuProps> = ({
  x,
  y,
  items,
  onClose,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const { playWin95Sound } = useApp();

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [onClose]);

  // Ensure menu stays within screen bounds
  const adjustedX = Math.min(x, window.innerWidth - 180);
  const adjustedY = Math.min(y, window.innerHeight - 200);

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-[#c0c0c0] win-outset py-1 min-w-[170px] shadow-lg select-none text-[11px] font-sans"
      style={{ left: `${adjustedX}px`, top: `${adjustedY}px` }}
    >
      {items.map((item, index) => {
        if (item.divider) {
          return (
            <div
              key={index}
              className="my-1 border-t border-[#808080] border-b border-white"
            />
          );
        }

        return (
          <button
            key={index}
            type="button"
            disabled={item.disabled}
            className={`w-full text-left px-3 py-1 flex items-center gap-2 hover:bg-[#000080] hover:text-white select-none ${
              item.disabled ? 'text-[#808080] cursor-not-allowed hover:bg-transparent' : 'text-black'
            }`}
            onClick={() => {
              playWin95Sound('click');
              item.action();
              onClose();
            }}
          >
            {item.icon && <span className="shrink-0">{item.icon}</span>}
            <span className="truncate">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
};
