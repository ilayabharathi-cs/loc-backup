import React, { useState } from 'react';
import type { BackupFileNode } from '../../types';
import { WinTreeView } from './WinTreeView';
import { WinTable } from './WinTable';
import type { Column } from './WinTable';
import { WinCheckbox } from './WinFormControls';
import { FolderIcon, DocumentIcon } from './WinIcons';

interface WinFileBrowserProps {
  root: BackupFileNode;
  selectedPaths: string[];
  onTogglePath: (path: string) => void;
  onSelectAllInCurrentFolder?: (paths: string[]) => void;
  className?: string;
}

export const WinFileBrowser: React.FC<WinFileBrowserProps> = ({
  root,
  selectedPaths,
  onTogglePath,
  className = '',
}) => {
  const [currentNode, setCurrentNode] = useState<BackupFileNode>(
    root.children?.[0]?.children?.[0]?.children?.[0] || root
  );

  const formatBytes = (bytes?: number) => {
    if (!bytes) return '--';
    if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
    return `${Math.round(bytes / 1024)} KB`;
  };

  const currentItems = currentNode.children || [];

  const columns: Column<BackupFileNode>[] = [
    {
      key: 'select',
      header: '✓',
      width: '32px',
      align: 'center',
      render: (item) => (
        <div onClick={(e) => e.stopPropagation()} className="flex justify-center">
          <WinCheckbox
            label=""
            checked={selectedPaths.includes(item.path)}
            onChange={() => onTogglePath(item.path)}
          />
        </div>
      ),
    },
    {
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (item) => (
        <div className="flex items-center gap-1.5 truncate">
          <span className="shrink-0">
            {item.isDirectory ? <FolderIcon size={14} /> : <DocumentIcon size={14} />}
          </span>
          <span className="truncate">{item.name}</span>
        </div>
      ),
    },
    {
      key: 'sizeBytes',
      header: 'Size',
      width: '80px',
      align: 'right',
      sortable: true,
      render: (item) => <span>{item.isDirectory ? '<DIR>' : formatBytes(item.sizeBytes)}</span>,
    },
    {
      key: 'modified',
      header: 'Modified',
      width: '120px',
      align: 'left',
      sortable: true,
      render: (item) => <span className="font-mono text-[10px]">{item.modified}</span>,
    },
  ];

  return (
    <div className={`flex flex-col gap-1 select-none ${className}`}>
      {/* Path Address Bar */}
      <div className="win-inset-gray px-2 py-1 flex items-center gap-2 text-[11px] bg-[#dfdfdf]">
        <span className="font-bold text-black select-none">Address:</span>
        <div className="win-inset bg-white px-1.5 py-0.5 flex-1 font-mono text-[10px] text-black truncate">
          {currentNode.path}
        </div>
        <span className="text-[10px] text-[#404040]">
          {selectedPaths.length} items marked for restore
        </span>
      </div>

      {/* Dual Pane Explorer */}
      <div className="grid grid-cols-12 gap-1.5 h-64">
        {/* Left pane: Tree View */}
        <div className="col-span-4 h-full">
          <WinTreeView
            root={root}
            selectedNodeId={currentNode.id}
            onSelectNode={(node) => {
              if (node.isDirectory) {
                setCurrentNode(node);
              }
            }}
            className="h-full"
          />
        </div>

        {/* Right pane: Contents Table */}
        <div className="col-span-8 h-full">
          <WinTable
            columns={columns}
            data={currentItems}
            keyExtractor={(item) => item.id}
            onDoubleClick={(item) => {
              if (item.isDirectory) {
                setCurrentNode(item);
              } else {
                onTogglePath(item.path);
              }
            }}
            emptyText="This folder is empty in this recovery point."
            className="h-full"
          />
        </div>
      </div>
    </div>
  );
};
