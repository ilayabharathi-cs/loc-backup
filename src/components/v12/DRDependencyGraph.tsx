import React from 'react';
import type { DRDependencyNode, DRDependencyEdge } from '../../api/v12';
import { ServerIcon, WarningIcon, CheckIcon, ErrorIcon } from '../win95/WinIcons';

interface DRDependencyGraphProps {
  nodes: DRDependencyNode[];
  edges: DRDependencyEdge[];
  cycleDetected?: boolean;
  cyclePath?: string[] | null;
  onNodeClick?: (node: DRDependencyNode) => void;
  selectedNodeId?: string | null;
}

export const DRDependencyGraph: React.FC<DRDependencyGraphProps> = ({
  nodes,
  edges,
  cycleDetected = false,
  cyclePath,
  onNodeClick,
  selectedNodeId
}) => {
  // Sort nodes primarily by boot order
  const sortedNodes = [...nodes].sort((a, b) => a.boot_order - b.boot_order);

  // Group nodes by boot order level for clean staged DAG visualization
  const levelsMap: { [order: number]: DRDependencyNode[] } = {};
  sortedNodes.forEach((node) => {
    if (!levelsMap[node.boot_order]) {
      levelsMap[node.boot_order] = [];
    }
    levelsMap[node.boot_order].push(node);
  });

  const levelKeys = Object.keys(levelsMap)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <div className="flex flex-col gap-3 font-sans text-xs">
      {/* Circular Dependency Warning Alert */}
      {cycleDetected && (
        <div className="win-outset p-3 bg-[#ffebee] border-2 border-[#cc0000] flex flex-col gap-2 shadow">
          <div className="flex items-center gap-2 text-[#cc0000] font-bold text-sm">
            <WarningIcon size={18} />
            <span>ERROR: Circular Dependency Detected in Execution Graph</span>
          </div>
          <p className="text-[11px] text-gray-800">
            A fatal loop exists in the workload dependency specifications. The runbook execution engine will deadlock if initiated.
          </p>

          {cyclePath && cyclePath.length > 0 && (
            <div className="win-inset bg-white p-2 text-xs font-mono text-[#cc0000] flex flex-wrap items-center gap-1.5">
              {cyclePath.map((step, idx) => (
                <React.Fragment key={idx}>
                  <span className="font-bold bg-red-100 px-1.5 py-0.5 border border-red-300">
                    {step}
                  </span>
                  {idx < cyclePath.length - 1 && <span className="font-black text-gray-500">&rarr;</span>}
                </React.Fragment>
              ))}
            </div>
          )}

          <div className="text-[11px] font-semibold text-[#800000]">
            Runbook cannot be executed or simulated until the dependency cycle is resolved.
          </div>
        </div>
      )}

      {/* DAG Node Cascade Visualizer */}
      <div className="win-inset bg-[#e8e8e8] p-4 overflow-auto min-h-[300px] flex flex-col items-center gap-4">
        {levelKeys.length === 0 ? (
          <div className="text-gray-500 py-12">No workload nodes configured in runbook.</div>
        ) : (
          levelKeys.map((level, levelIdx) => {
            const currentLevelNodes = levelsMap[level];
            const hasNextLevel = levelIdx < levelKeys.length - 1;

            return (
              <React.Fragment key={level}>
                {/* Level Stage Header & Node Grid */}
                <div className="w-full flex flex-col items-center gap-2">
                  <div className="text-[10px] uppercase tracking-wider font-bold text-[#000080] bg-[#dfdfdf] px-3 py-0.5 win-outset-thin">
                    Execution Stage {level} (Parallel Boot Group)
                  </div>

                  <div className="flex flex-wrap justify-center gap-3 w-full max-w-4xl">
                    {currentLevelNodes.map((node) => {
                      const isSelected = selectedNodeId === node.id;
                      const hasParents = edges.some((e) => e.target_id === node.id);

                      // Status icons
                      let statusBadge = (
                        <span className="text-[10px] px-1 py-0.2 bg-gray-200 text-gray-700 font-bold border border-gray-400">
                          READY
                        </span>
                      );
                      if (cycleDetected) {
                        statusBadge = (
                          <span className="text-[10px] px-1 py-0.2 bg-red-600 text-white font-bold flex items-center gap-0.5">
                            <ErrorIcon size={10} /> BLOCKED
                          </span>
                        );
                      } else if (node.status === 'READY') {
                        statusBadge = (
                          <span className="text-[10px] px-1 py-0.2 bg-green-700 text-white font-bold flex items-center gap-0.5">
                            <CheckIcon size={10} /> OK
                          </span>
                        );
                      }

                      return (
                        <div
                          key={node.id}
                          onClick={() => onNodeClick?.(node)}
                          className={`w-64 p-2.5 cursor-pointer transition-all flex flex-col gap-1.5 ${
                            isSelected
                              ? 'win-inset bg-[#ffffcc] border-2 border-[#000080]'
                              : 'win-outset bg-[#c0c0c0] hover:bg-[#dcdcdc]'
                          }`}
                        >
                          <div className="flex justify-between items-start">
                            <div className="flex items-center gap-1.5">
                              <ServerIcon size={16} />
                              <strong className="text-xs truncate max-w-[140px]" title={node.workload_name}>
                                {node.workload_name}
                              </strong>
                            </div>
                            {statusBadge}
                          </div>

                          <div className="text-[10px] text-gray-600 font-mono">
                            Type: {node.workload_type}
                          </div>

                          <div className="win-inset-thin bg-white p-1 text-[10px] flex justify-between">
                            <span>Health Check:</span>
                            <span className="font-bold text-[#000080]">{node.health_check_type}</span>
                          </div>

                          <div className="text-[9px] text-gray-500 flex justify-between">
                            <span>Boot Order: #{node.boot_order}</span>
                            <span>{hasParents ? 'Has Pre-reqs' : 'Base Root'}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Arrow Down to Next Stage */}
                {hasNextLevel && (
                  <div className="flex flex-col items-center gap-0.5 text-[#000080]">
                    <div className="w-0.5 h-4 bg-[#000080]" />
                    <span className="text-base font-black leading-none">&#x25BC;</span>
                  </div>
                )}
              </React.Fragment>
            );
          })
        )}
      </div>
    </div>
  );
};

export default DRDependencyGraph;
