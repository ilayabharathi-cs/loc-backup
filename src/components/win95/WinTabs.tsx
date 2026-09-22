import React from 'react';
import type { ReactNode } from 'react';
import { useApp } from '../../context/AppContext';

export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
  content: ReactNode;
}

export interface WinTabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  className?: string;
}

export const WinTabs: React.FC<WinTabsProps> = ({
  tabs,
  activeTab,
  onChange,
  className = '',
}) => {
  const { playWin95Sound } = useApp();

  const currentTab = tabs.find(t => t.id === activeTab) || tabs[0];

  return (
    <div className={`flex flex-col select-none ${className}`}>
      {/* Tab Strip */}
      <div className="flex items-end gap-1 px-2 border-b-2 border-[#dfdfdf] relative z-10 -mb-[2px]">
        {tabs.map((tab) => {
          const isActive = tab.id === activeTab;

          return (
            <button
              key={tab.id}
              type="button"
              className={`px-3 py-1 text-[11px] font-medium flex items-center gap-1.5 cursor-pointer outline-none transition-none ${
                isActive
                  ? 'win-outset bg-[#c0c0c0] font-bold text-black border-b-0 -mb-[2px] pb-1.5 pt-1 rounded-t-xs z-20'
                  : 'bg-[#b0b0b0] text-[#404040] hover:bg-[#b8b8b8] border-t border-l border-r border-[#808080] pb-1 pt-0.5 rounded-t-xs'
              }`}
              onClick={() => {
                playWin95Sound('click');
                onChange(tab.id);
              }}
            >
              {tab.icon && <span>{tab.icon}</span>}
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Content Panel */}
      <div className="win-outset p-3 bg-[#c0c0c0] relative z-0">
        {currentTab?.content}
      </div>
    </div>
  );
};
