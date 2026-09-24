import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { v12Api, parseApiError } from '../api/v12';
import type { DRRunbookDetail, DRDependencyNode, DRSimulationResult } from '../api/v12';
import { DRDependencyGraph } from '../components/v12/DRDependencyGraph';
import { WinTabs } from '../components/win95/WinTabs';
import { RunbookIcon, RefreshIcon, CheckIcon, ErrorIcon, WarningIcon } from '../components/win95/WinIcons';

export const DRRunbookDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [runbook, setRunbook] = useState<DRRunbookDetail | null>(null);
  const [selectedNode, setSelectedNode] = useState<DRDependencyNode | null>(null);
  const [activeTab, setActiveTab] = useState<string>('graph');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [simulationResult, setSimulationResult] = useState<DRSimulationResult | null>(null);
  const [simulating, setSimulating] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadRunbook = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await v12Api.getDRRunbook(id);
      setRunbook(data);
      if (data.nodes.length > 0 && !selectedNode) {
        setSelectedNode(data.nodes[0]);
      }
    } catch (err: unknown) {
      setError(parseApiError(err, 'Failed to load runbook detail'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRunbook();
  }, [id]);

  const handleSimulate = async () => {
    if (!runbook) return;
    setSimulating(true);
    setActionMessage('Evaluating topological sort and pre-flight sandbox validation checks...');
    try {
      const res = await v12Api.simulateDRRunbook(runbook.runbook_id);
      setSimulationResult(res);
      if (res.passed) {
        setActionMessage(`Simulation PASSED with estimated RTO of ${res.simulated_rto_seconds}s.`);
      } else {
        setActionMessage(`Simulation FAILED: ${res.errors.join('; ')}`);
      }
      setActiveTab('simulation');
    } catch (err: unknown) {
      setActionMessage(parseApiError(err, 'Simulation failed'));
    } finally {
      setSimulating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 win-inset bg-white m-3 p-8 flex flex-col items-center justify-center gap-3">
        <div className="text-xs font-bold text-gray-700">Loading Directed Acyclic Graph topology...</div>
        <div className="w-64 h-4 win-inset-gray bg-[#dfdfdf] relative overflow-hidden">
          <div className="h-full bg-[#000080] animate-pulse w-3/4" />
        </div>
      </div>
    );
  }

  if (error || !runbook) {
    return (
      <div className="flex-1 win-inset bg-white m-3 p-8 flex flex-col items-center justify-center gap-3 text-center">
        <div className="text-[#cc0000] font-bold text-sm">Failed to Load Runbook</div>
        <div className="text-xs text-gray-700">{error || 'Runbook not found'}</div>
        <button onClick={() => navigate('/dr/runbooks')} className="win-btn px-4 py-1.5 font-bold">
          &larr; Return to Runbook Catalog
        </button>
      </div>
    );
  }

  const tabs = [
    { id: 'graph', label: 'Dependency DAG Graph' },
    { id: 'bootOrder', label: 'Boot Order & Stages' },
    { id: 'preflight', label: 'Pre-flight Validation' },
    { id: 'simulation', label: 'Simulation Results' }
  ];

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Header Bar */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate('/dr/runbooks')} className="win-btn px-2 py-0.5 font-bold">
            &larr; Back
          </button>
          <div>
            <h2 className="text-sm font-bold flex items-center gap-2">
              <RunbookIcon size={16} />
              <span>{runbook.name}</span>
              <span className="font-mono text-[10px] text-gray-600 bg-white px-1 border border-gray-400">
                {runbook.runbook_id}
              </span>
            </h2>
            <p className="text-[11px] text-gray-700">
              Target: <strong>{runbook.target_environment}</strong> &bull; Network: <code>{runbook.failover_network || 'Default'}</code>
            </p>
          </div>
        </div>

        <div className="flex gap-2 items-center">
          <button
            onClick={handleSimulate}
            className="win-btn px-3 py-1 font-bold bg-[#e6f2ff] text-[#000080]"
            disabled={simulating}
          >
            {simulating ? 'Simulating...' : 'Run Simulation'}
          </button>
          <button onClick={loadRunbook} className="win-btn px-3 py-1 flex items-center gap-1">
            <RefreshIcon size={12} /> Refresh
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="win-inset p-2 bg-[#ffffe0] border-l-4 border-[#000080] text-xs font-semibold flex justify-between items-center">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="win-btn text-[10px] px-1.5 py-0.5">
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <WinTabs tabs={tabs} activeTab={activeTab} onChange={(t) => setActiveTab(t)} />

      {/* Tab Panels */}
      <div className="flex-1 flex gap-2 min-h-0">
        {activeTab === 'graph' && (
          <div className="flex-1 flex gap-2 min-h-0">
            {/* Left: DAG */}
            <div className="flex-1 overflow-auto">
              <DRDependencyGraph
                nodes={runbook.nodes}
                edges={runbook.edges}
                cycleDetected={runbook.cycle_detected}
                cyclePath={runbook.cycle_path}
                selectedNodeId={selectedNode?.id}
                onNodeClick={(n) => setSelectedNode(n)}
              />
            </div>

            {/* Right: Selected Node Detail */}
            <div className="w-80 win-outset p-3 bg-[#dcdcdc] flex flex-col gap-2 overflow-auto">
              <div className="font-bold text-xs border-b border-[#808080] pb-1 text-[#000080]">
                Workload Node Specification
              </div>
              {selectedNode ? (
                <div className="win-inset bg-white p-2.5 flex flex-col gap-2 text-[11px]">
                  <div>
                    <span className="text-gray-600 block">Workload Name:</span>
                    <strong className="block text-xs">{selectedNode.workload_name}</strong>
                  </div>
                  <div>
                    <span className="text-gray-600 block">Workload ID:</span>
                    <code className="text-[10px] block">{selectedNode.workload_id}</code>
                  </div>
                  <div>
                    <span className="text-gray-600 block">Workload Type:</span>
                    <strong className="block">{selectedNode.workload_type}</strong>
                  </div>
                  <div>
                    <span className="text-gray-600 block">Boot Order:</span>
                    <strong className="block text-[#000080]">Stage {selectedNode.boot_order}</strong>
                  </div>
                  <div>
                    <span className="text-gray-600 block">Health Check Verification:</span>
                    <span className="px-1.5 py-0.5 bg-gray-100 font-mono text-[10px] border border-gray-300 block">
                      {selectedNode.health_check_type} (Timeout: {selectedNode.health_timeout_seconds}s)
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-gray-500 text-center py-6">Select a node in the DAG to inspect.</div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'bootOrder' && (
          <div className="flex-1 win-inset bg-white p-3 overflow-auto">
            <h3 className="font-bold text-xs text-[#000080] mb-2">Sequential Boot Order Stages</h3>
            <table className="w-full border-collapse text-left text-xs">
              <thead className="bg-[#e0e0e0] border-b border-[#808080]">
                <tr>
                  <th className="p-1.5 border-r border-[#808080]">Boot Order</th>
                  <th className="p-1.5 border-r border-[#808080]">Workload Name</th>
                  <th className="p-1.5 border-r border-[#808080]">Type</th>
                  <th className="p-1.5 border-r border-[#808080]">Health Probe</th>
                  <th className="p-1.5">Max Wait</th>
                </tr>
              </thead>
              <tbody>
                {[...runbook.nodes]
                  .sort((a, b) => a.boot_order - b.boot_order)
                  .map((node) => (
                    <tr key={node.id} className="border-b border-gray-200">
                      <td className="p-1.5 font-bold font-mono">Stage #{node.boot_order}</td>
                      <td className="p-1.5 font-semibold">{node.workload_name}</td>
                      <td className="p-1.5 font-mono text-[10px]">{node.workload_type}</td>
                      <td className="p-1.5 font-mono text-[#000080]">{node.health_check_type}</td>
                      <td className="p-1.5">{node.health_timeout_seconds}s</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'preflight' && (
          <div className="flex-1 win-inset bg-white p-4 overflow-auto flex flex-col gap-3">
            <h3 className="font-bold text-xs text-[#000080]">Pre-flight Recovery Verification Rules</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="win-outset p-3 bg-[#f8f8f8]">
                <strong className="block text-xs text-gray-800">1. Topological Acyclicity Guard</strong>
                <p className="text-[11px] text-gray-600 mt-1">
                  Ensures all dependency edges form a strictly acyclic directed graph with no self-referential or transitive cyclic loops.
                </p>
              </div>
              <div className="win-outset p-3 bg-[#f8f8f8]">
                <strong className="block text-xs text-gray-800">2. Network IP Allocation Check</strong>
                <p className="text-[11px] text-gray-600 mt-1">
                  Validates available private IP addresses on <code>{runbook.failover_network || 'DR-VNet'}</code> before starting VM boots.
                </p>
              </div>
              <div className="win-outset p-3 bg-[#f8f8f8]">
                <strong className="block text-xs text-gray-800">3. Cryptographic Storage Checksums</strong>
                <p className="text-[11px] text-gray-600 mt-1">
                  Probes CAS chunks and object lock status to ensure all dependent recovery points are valid and uncorrupted.
                </p>
              </div>
              <div className="win-outset p-3 bg-[#f8f8f8]">
                <strong className="block text-xs text-gray-800">4. Application Quiesce State</strong>
                <p className="text-[11px] text-gray-600 mt-1">
                  Verifies that source database transaction logs are consistent for crash-free database engine spin-up.
                </p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'simulation' && (
          <div className="flex-1 win-inset bg-white p-4 overflow-auto flex flex-col gap-3">
            {simulationResult ? (
              <>
                <div
                  className={`win-outset p-3 flex justify-between items-center ${
                    simulationResult.passed ? 'bg-green-50 border-green-600' : 'bg-red-50 border-red-600'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {simulationResult.passed ? <CheckIcon size={18} /> : <ErrorIcon size={18} />}
                    <strong className="text-sm">
                      {simulationResult.passed ? 'Pre-flight Simulation PASSED' : 'Pre-flight Simulation FAILED'}
                    </strong>
                  </div>
                  <span className="font-mono text-xs font-bold">
                    Simulated RTO: {simulationResult.simulated_rto_seconds} seconds
                  </span>
                </div>

                <div className="flex flex-col gap-2">
                  <div className="font-bold text-xs text-gray-700">Checks Performed:</div>
                  {simulationResult.checks_performed.map((chk, idx) => (
                    <div
                      key={idx}
                      className="win-inset p-2 bg-[#fdfdfd] border-l-4 flex justify-between items-center"
                      style={{ borderLeftColor: chk.passed ? '#008000' : '#cc0000' }}
                    >
                      <div>
                        <strong>{chk.name}</strong>
                        <div className="text-[11px] text-gray-600">{chk.message}</div>
                      </div>
                      <span className="font-mono text-[10px] text-gray-500">{chk.duration_ms}ms</span>
                    </div>
                  ))}
                </div>

                {simulationResult.errors.length > 0 && (
                  <div className="win-inset p-2 bg-[#ffebee] border-l-4 border-[#cc0000] text-[#cc0000]">
                    <strong>Simulation Errors:</strong>
                    <ul className="list-disc pl-4 mt-1 text-[11px]">
                      {simulationResult.errors.map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-12 flex flex-col items-center gap-2">
                <WarningIcon size={24} />
                <div className="font-bold">No Simulation Results Cached</div>
                <button onClick={handleSimulate} className="win-btn px-4 py-1.5 font-bold">
                  Run Pre-flight Simulation
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DRRunbookDetailsPage;
