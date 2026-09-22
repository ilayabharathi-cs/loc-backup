import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';

export interface Column<T> {
  key: string;
  header: string;
  width?: string | number;
  align?: 'left' | 'center' | 'right';
  sortable?: boolean;
  render?: (item: T, index: number) => React.ReactNode;
}

export interface WinTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string;
  selectedId?: string | null;
  onSelect?: (item: T) => void;
  onDoubleClick?: (item: T) => void;
  onContextMenu?: (item: T, e: React.MouseEvent) => void;
  emptyText?: string;
  className?: string;
}

export function WinTable<T>({
  columns,
  data,
  keyExtractor,
  selectedId,
  onSelect,
  onDoubleClick,
  onContextMenu,
  emptyText = 'No records found.',
  className = '',
}: WinTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const { playWin95Sound } = useApp();

  const handleHeaderClick = (col: Column<T>) => {
    if (!col.sortable) return;
    playWin95Sound('click');
    if (sortKey === col.key) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(col.key);
      setSortDir('asc');
    }
  };

  const sortedData = [...data].sort((a, b) => {
    if (!sortKey) return 0;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const valA = (a as any)[sortKey];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const valB = (b as any)[sortKey];

    if (valA === valB) return 0;
    if (valA == null) return 1;
    if (valB == null) return -1;

    let comp = 0;
    if (typeof valA === 'number' && typeof valB === 'number') {
      comp = valA - valB;
    } else {
      comp = String(valA).localeCompare(String(valB));
    }
    return sortDir === 'asc' ? comp : -comp;
  });

  return (
    <div className={`win-inset bg-white overflow-auto select-none border border-black/20 ${className}`}>
      <table className="w-full border-collapse text-[11px] font-sans">
        <thead className="sticky top-0 z-10 bg-[#c0c0c0]">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{ width: col.width }}
                className={`win-outset px-2 py-1 text-black font-bold select-none cursor-pointer border-r border-[#808080] text-${
                  col.align || 'left'
                } hover:bg-[#d0d0d0] active:win-inset-gray active:pt-1.5 active:pb-0.5`}
                onClick={() => handleHeaderClick(col)}
              >
                <div className="flex items-center justify-between gap-1">
                  <span className="truncate">{col.header}</span>
                  {sortKey === col.key && (
                    <span className="text-[9px] font-mono shrink-0">
                      {sortDir === 'asc' ? '▲' : '▼'}
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="text-center py-6 text-[#808080] italic"
              >
                {emptyText}
              </td>
            </tr>
          ) : (
            sortedData.map((item, index) => {
              const id = keyExtractor(item);
              const isSelected = selectedId === id;

              return (
                <tr
                  key={id}
                  className={`h-5 cursor-default transition-none ${
                    isSelected
                      ? 'bg-[#000080] text-white'
                      : index % 2 === 1
                      ? 'bg-[#f4f4f4] text-black hover:bg-[#e8f0fe]'
                      : 'bg-white text-black hover:bg-[#e8f0fe]'
                  }`}
                  onClick={() => {
                    if (onSelect) onSelect(item);
                  }}
                  onDoubleClick={() => {
                    playWin95Sound('click');
                    if (onDoubleClick) onDoubleClick(item);
                  }}
                  onContextMenu={(e) => {
                    if (onContextMenu) {
                      e.preventDefault();
                      if (onSelect) onSelect(item);
                      onContextMenu(item, e);
                    }
                  }}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-2 py-0.5 border-r border-[#e0e0e0] truncate text-${
                        col.align || 'left'
                      } ${isSelected ? 'text-white font-medium' : ''}`}
                    >
                      {col.render ? (
                        col.render(item, index)
                      ) : (
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        <span>{(item as any)[col.key]}</span>
                      )}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
