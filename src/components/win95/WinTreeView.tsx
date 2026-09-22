import React, { useState } from 'react';
import type { BackupFileNode } from '../../types';
import { FolderIcon, FolderOpenIcon, DocumentIcon } from './WinIcons';
import { useApp } from '../../context/AppContext';

interface WinTreeViewProps {
  root: BackupFileNode;
  selectedNodeId: string;
  onSelectNode: (node: BackupFileNode) => void;
  className?: string;
}

export const WinTreeView: React.FC<WinTreeViewProps> = ({
  root,
  selectedNodeId,
  onSelectNode,
  className = '',
}) => {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set([root.id, 'node-users', 'node-arun']));
  const { playWin95Sound } = useApp();

  const toggleExpand = (nodeId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    playWin95Sound('click');
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const renderNode = (node: BackupFileNode, depth: number = 0) => {
    const isExpanded = expandedIds.has(node.id);
    const hasChildren = node.children && node.children.length > 0;
    const isSelected = selectedNodeId === node.id;

    return (
      <div key={node.id} className="select-none">
        <div
          className={`flex items-center gap-1 py-0.5 px-1 cursor-pointer font-sans text-[11px] ${
            isSelected ? 'bg-[#000080] text-white' : 'hover:bg-[#e0e0e0] text-black'
          }`}
          style={{ paddingLeft: `${depth * 14 + 4}px` }}
          onClick={() => {
            playWin95Sound('click');
            onSelectNode(node);
          }}
        >
          {/* Expand/Collapse Box */}
          {hasChildren ? (
            <button
              type="button"
              className="w-3 h-3 win-outset-thin flex items-center justify-center text-[9px] font-mono leading-none bg-white text-black shrink-0"
              onClick={(e) => toggleExpand(node.id, e)}
            >
              {isExpanded ? '-' : '+'}
            </button>
          ) : (
            <span className="w-3 inline-block" />
          )}

          {/* Icon */}
          <span className="shrink-0">
            {node.isDirectory ? (
              isExpanded ? <FolderOpenIcon size={14} /> : <FolderIcon size={14} />
            ) : (
              <DocumentIcon size={14} />
            )}
          </span>

          <span className="truncate">{node.name}</span>
        </div>

        {/* Child nodes */}
        {hasChildren && isExpanded && (
          <div className="border-l border-dotted border-[#808080] ml-3">
            {node.children!.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={`win-inset bg-white overflow-y-auto p-1 text-[11px] ${className}`}>
      {renderNode(root)}
    </div>
  );
};
