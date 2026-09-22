import React from 'react';
import type { InputHTMLAttributes, SelectHTMLAttributes } from 'react';

export interface WinInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
}

export const WinInput: React.FC<WinInputProps> = ({
  label,
  helperText,
  className = '',
  id,
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={inputId} className="text-[11px] font-bold text-black select-none">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`win-inset px-1.5 py-0.5 text-[11px] text-black bg-white focus:outline-none focus:ring-1 focus:ring-black disabled:bg-[#dfdfdf] disabled:text-[#808080] font-sans ${className}`}
        {...props}
      />
      {helperText && (
        <span className="text-[10px] text-[#404040] italic">{helperText}</span>
      )}
    </div>
  );
};

export interface WinSelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
}

export const WinSelect: React.FC<WinSelectProps> = ({
  label,
  children,
  className = '',
  id,
  ...props
}) => {
  const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={selectId} className="text-[11px] font-bold text-black select-none">
          {label}
        </label>
      )}
      <select
        id={selectId}
        className={`win-inset px-1.5 py-0.5 text-[11px] text-black bg-white focus:outline-none focus:ring-1 focus:ring-black disabled:bg-[#dfdfdf] font-sans cursor-pointer ${className}`}
        {...props}
      >
        {children}
      </select>
    </div>
  );
};

export interface WinCheckboxProps {
  label: string | React.ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}

export const WinCheckbox: React.FC<WinCheckboxProps> = ({
  label,
  checked,
  onChange,
  disabled = false,
  className = '',
}) => {
  return (
    <label
      className={`inline-flex items-center gap-1.5 cursor-pointer select-none text-[11px] font-normal text-black ${
        disabled ? 'opacity-60 cursor-not-allowed text-[#808080]' : ''
      } ${className}`}
    >
      <div
        className={`w-3.5 h-3.5 win-inset flex items-center justify-center bg-white ${
          disabled ? 'bg-[#dfdfdf]' : ''
        }`}
        onClick={(e) => {
          if (!disabled) {
            e.preventDefault();
            onChange(!checked);
          }
        }}
      >
        {checked && (
          <span className="text-black font-extrabold text-[12px] leading-none mb-0.5 select-none">
            ✓
          </span>
        )}
      </div>
      <span>{label}</span>
    </label>
  );
};
