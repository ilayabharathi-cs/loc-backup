import React from 'react';
import type { ReactNode } from 'react';

export interface WinPanelProps {
  children: ReactNode;
  variant?: 'outset' | 'inset' | 'inset-gray' | 'groove' | 'ridge' | 'flat';
  title?: string;
  className?: string;
}

export const WinPanel: React.FC<WinPanelProps> = ({
  children,
  variant = 'outset',
  title,
  className = '',
}) => {
  if (title) {
    return (
      <fieldset className={`win-fieldset ${className}`}>
        <legend className="text-[11px] font-bold text-black select-none px-1 bg-[#c0c0c0]">
          {title}
        </legend>
        <div className="pt-1">{children}</div>
      </fieldset>
    );
  }

  const variantClass = {
    outset: 'win-outset',
    inset: 'win-inset',
    'inset-gray': 'win-inset-gray',
    groove: 'win-groove bg-[#c0c0c0]',
    ridge: 'win-ridge bg-[#c0c0c0]',
    flat: 'bg-[#c0c0c0]',
  }[variant];

  return (
    <div className={`${variantClass} ${className}`}>
      {children}
    </div>
  );
};
