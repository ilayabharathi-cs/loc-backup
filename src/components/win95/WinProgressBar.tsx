import React from 'react';

export interface WinProgressBarProps {
  percent: number;
  label?: string;
  className?: string;
  showPercentText?: boolean;
  color?: string;
}

export const WinProgressBar: React.FC<WinProgressBarProps> = ({
  percent,
  label,
  className = '',
  showPercentText = true,
  color = '#000080',
}) => {
  const clamped = Math.max(0, Math.min(100, Math.round(percent)));
  const totalBlocks = 24;
  const filledBlocks = Math.round((clamped / 100) * totalBlocks);

  return (
    <div className={`flex flex-col gap-1 select-none ${className}`}>
      {label && (
        <div className="flex justify-between text-[11px] font-sans">
          <span className="font-semibold text-black">{label}</span>
          {showPercentText && (
            <span className="font-mono text-black font-bold">{clamped}%</span>
          )}
        </div>
      )}

      {/* Sunken track */}
      <div className="win-inset-gray h-5 p-0.5 flex items-center bg-[#ffffff] relative overflow-hidden">
        {/* Segmented blocks */}
        <div className="flex w-full h-full gap-0.5">
          {Array.from({ length: totalBlocks }).map((_, index) => {
            const isFilled = index < filledBlocks;
            return (
              <div
                key={index}
                className="flex-1 h-full transition-none"
                style={{
                  backgroundColor: isFilled ? color : 'transparent',
                }}
              />
            );
          })}
        </div>

        {/* Optional overlay text if no external label */}
        {!label && showPercentText && (
          <div className="absolute inset-0 flex items-center justify-center text-[10px] font-mono font-bold text-black drop-shadow-sm pointer-events-none">
            {clamped}%
          </div>
        )}
      </div>
    </div>
  );
};
