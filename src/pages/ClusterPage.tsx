import React, { useState, useEffect } from 'react';
import { v9Api } from '../api/v9';
import type { ClusterNode, ClusterStatus, ClusterEvent } from '../api/v9';

export const ClusterPage: React.FC = () => {
  const [status, setStatus] = useState<ClusterStatus | null>(null);
  const [nodes, setNodes] = useState<ClusterNode[]>([]);
  const [events, setEvents] = useState<ClusterEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  // New Node Form State
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newNodeId, setNewNodeId] = useState<string>('node-c-worker');
  const [newHostname, setNewHostname] = useState<string>('retrovault-node-c');
  const [newIp, setNewIp] = useState<string>('192.168.1.103');
  const [newPort, setNewPort] = useState<number>(8000);
  const [newRoles, setNewRoles] = useState<string>('WORKER,REPOSITORY_WORKER');

  const loadClusterData = async () => {
    setLoading(true);
    try {
      const [statusRes, nodesRes, eventsRes] = await Promise.all([
        v9Api.getClusterStatus(),
        v9Api.listNodes(),
        v9Api.listEvents(30),
      ]);
      setStatus(statusRes);
      setNodes(nodesRes);
      setEvents(eventsRes);
    } catch (e: any) {
      console.error('Failed to load cluster data:', e);
      setActionMsg(`Error fetching cluster data: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClusterData();
    const interval = setInterval(loadClusterData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleDrain = async (nodeId: string) => {
    try {
      await v9Api.drainNode(nodeId);
      setActionMsg(`Node ${nodeId} set to DRAINING.`);
      await loadClusterData();
    } catch (e: any) {
      setActionMsg(`Drain failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleResume = async (nodeId: string) => {
    try {
      await v9Api.resumeNode(nodeId);
      setActionMsg(`Node ${nodeId} resumed to ACTIVE.`);
      await loadClusterData();
    } catch (e: any) {
      setActionMsg(`Resume failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleResign = async (nodeId: string) => {
    try {
      await v9Api.resignLeader(nodeId);
      setActionMsg(`Leader lease resigned by ${nodeId}. Failover initiated.`);
      await loadClusterData();
    } catch (e: any) {
      setActionMsg(`Resign failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleElect = async (nodeId: string) => {
    try {
      const res = await v9Api.electLeader(nodeId, 20);
      setActionMsg(`Election outcome for ${nodeId}: ${res.action || (res.is_leader ? 'ELECTED' : 'DENIED')}`);
      await loadClusterData();
    } catch (e: any) {
      setActionMsg(`Elect failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleReconcile = async () => {
    if (!status?.leader.leader_node_id) {
      setActionMsg('Cannot reconcile: No active cluster leader.');
      return;
    }
    try {
      const res = await v9Api.reconcileCluster(status.leader.leader_node_id, true);
      setActionMsg(`Reconciled: ${res.orphans?.requeued_count || 0} orphaned jobs requeued, ${res.expired_locks_cleared || 0} locks cleared.`);
      await loadClusterData();
    } catch (e: any) {
      setActionMsg(`Reconciliation failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  const handleRegisterNode = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await v9Api.registerNode({
        node_id: newNodeId,
        hostname: newHostname,
        ip_address: newIp,
        port: newPort,
        roles: newRoles.split(',').map((r) => r.trim().toUpperCase()),
      });
      setShowAddModal(false);
      setActionMsg(`Node ${newNodeId} registered successfully.`);
      await loadClusterData();
    } catch (e: any) {
      setActionMsg(`Registration failed: ${e.response?.data?.detail || e.message}`);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-3 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Header Panel */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span>🌐 RetroVault High Availability Cluster Console (V9)</span>
          </h2>
          <p className="text-[11px] text-gray-700">
            Multi-node distributed control plane, leader lease consensus, and zero-downtime failover
          </p>
        </div>
        <div className="flex items-center gap-2">
          {loading && <span className="text-[11px] text-gray-500 font-mono">Syncing...</span>}
          <button onClick={loadClusterData} className="win-btn px-3 py-1 font-bold">
            Refresh
          </button>
          <button onClick={() => setShowAddModal(true)} className="win-btn px-3 py-1 font-bold">
            + Register Node
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="win-outset p-2 bg-[#ffffcc] text-black font-mono flex justify-between items-center">
          <span>ℹ {actionMsg}</span>
          <button onClick={() => setActionMsg(null)} className="win-btn px-2 text-[10px]">
            Dismiss
          </button>
        </div>
      )}

      {/* Cluster Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
        <div className="win-outset p-2 bg-white">
          <div className="text-[10px] text-gray-500 font-bold uppercase">Cluster Health</div>
          <div className="mt-1 flex items-center gap-2">
            <span
              className={`px-2 py-0.5 font-bold font-mono text-xs text-white ${
                status?.cluster_status === 'HEALTHY' ? 'bg-[#008000]' : 'bg-[#c00000]'
              }`}
            >
              ● {status?.cluster_status || 'UNKNOWN'}
            </span>
            <span className="font-mono text-[11px]">
              {status?.active_nodes ?? 0} / {status?.total_nodes ?? 0} Online
            </span>
          </div>
        </div>

        <div className="win-outset p-2 bg-white">
          <div className="text-[10px] text-gray-500 font-bold uppercase">Active Cluster Leader</div>
          <div className="mt-1 font-mono font-bold text-xs text-[#000080] truncate">
            👑 {status?.leader.leader_node_id || 'NO ACTIVE LEADER'}
          </div>
          <div className="text-[10px] text-gray-600 mt-0.5">
            Lease Status: {status?.leader.is_active ? 'Valid / Active' : 'Expired / Stale'}
          </div>
        </div>

        <div className="win-outset p-2 bg-white">
          <div className="text-[10px] text-gray-500 font-bold uppercase">Database Layer HA</div>
          <div className="mt-1 font-mono font-bold text-xs flex items-center gap-1">
            <span>🗄 {status?.database.dialect.toUpperCase() || 'SQL'}</span>
            <span className="text-[10px] text-gray-600 font-normal">
              ({status?.database.ha_mode === 'POSTGRESQL_DISTRIBUTED' ? 'PostgreSQL HA' : 'SQLite Local'})
            </span>
          </div>
          <div className="text-[10px] text-gray-600 mt-0.5 font-mono">
            Latency: {status?.database.latency_ms ?? 0} ms | {status?.database.status || 'UNKNOWN'}
          </div>
        </div>

        <div className="win-outset p-2 bg-white">
          <div className="text-[10px] text-gray-500 font-bold uppercase">Queue Backpressure</div>
          <div className="mt-1 font-mono font-bold text-xs">
            <span
              className={`px-1.5 py-0.2 ${
                status?.backpressure.backpressure_level === 'NORMAL'
                  ? 'bg-[#d0f0c0] text-[#006000]'
                  : 'bg-[#ffc0c0] text-[#800000]'
              }`}
            >
              {status?.backpressure.backpressure_level || 'NORMAL'}
            </span>
            <span className="ml-2 font-normal text-gray-700">
              {status?.queued_jobs_count ?? 0} Q'd / {status?.running_jobs_count ?? 0} Run
            </span>
          </div>
          <div className="text-[10px] text-gray-600 mt-0.5">
            Locks Held: {status?.active_locks_count ?? 0}
          </div>
        </div>
      </div>

      {/* Main Split Grid: Nodes on Left, Leader Consensus & Diagnostics on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Nodes Table (2 cols on large screen) */}
        <div className="lg:col-span-2 win-outset p-2 bg-[#dcdcdc] flex flex-col gap-2">
          <div className="flex justify-between items-center border-b pb-1">
            <span className="font-bold text-xs">Registered Cluster Nodes ({nodes.length})</span>
            <button onClick={handleReconcile} className="win-btn px-2 py-0.5 text-[11px] font-bold">
              ⚡ Run Cluster Reconciliation
            </button>
          </div>

          <div className="win-inset bg-white overflow-auto max-h-[360px]">
            <table className="w-full text-left border-collapse text-[11px]">
              <thead className="bg-[#000080] text-white font-mono sticky top-0">
                <tr>
                  <th className="p-1 border-r border-[#808080]">Node ID</th>
                  <th className="p-1 border-r border-[#808080]">Address</th>
                  <th className="p-1 border-r border-[#808080]">Roles</th>
                  <th className="p-1 border-r border-[#808080]">Status</th>
                  <th className="p-1 border-r border-[#808080]">Load</th>
                  <th className="p-1 border-r border-[#808080]">Jobs</th>
                  <th className="p-1">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 font-mono">
                {nodes.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-3 text-center text-gray-500 italic">
                      No nodes currently registered. Click "+ Register Node" to add.
                    </td>
                  </tr>
                ) : (
                  nodes.map((node) => {
                    const isLeader = status?.leader.leader_node_id === node.node_id;
                    return (
                      <tr key={node.node_id} className={node.is_draining ? 'bg-[#fff0e0]' : ''}>
                        <td className="p-1 border-r border-gray-200 font-bold">
                          {isLeader && <span title="Cluster Leader">👑 </span>}
                          {node.node_id}
                        </td>
                        <td className="p-1 border-r border-gray-200">
                          {node.ip_address}:{node.port}
                        </td>
                        <td className="p-1 border-r border-gray-200 text-[10px]">
                          {node.roles.join(', ')}
                        </td>
                        <td className="p-1 border-r border-gray-200">
                          <span
                            className={`px-1 py-0.2 text-[10px] font-bold ${
                              node.status === 'ACTIVE'
                                ? 'bg-[#c0ffc0] text-[#006000]'
                                : node.status === 'DRAINING'
                                ? 'bg-[#ffe080] text-[#804000]'
                                : 'bg-[#ffc0c0] text-[#800000]'
                            }`}
                          >
                            {node.status}
                          </span>
                        </td>
                        <td className="p-1 border-r border-gray-200">{node.current_load}%</td>
                        <td className="p-1 border-r border-gray-200">
                          {node.active_jobs_count} / {node.max_concurrent_jobs}
                        </td>
                        <td className="p-1 flex items-center gap-1">
                          {node.is_draining ? (
                            <button
                              onClick={() => handleResume(node.node_id)}
                              className="win-btn px-1.5 py-0.2 text-[10px]"
                            >
                              Resume
                            </button>
                          ) : (
                            <button
                              onClick={() => handleDrain(node.node_id)}
                              className="win-btn px-1.5 py-0.2 text-[10px]"
                            >
                              Drain
                            </button>
                          )}
                          {!isLeader && (
                            <button
                              onClick={() => handleElect(node.node_id)}
                              className="win-btn px-1.5 py-0.2 text-[10px]"
                              title="Nominate as leader"
                            >
                              Elect
                            </button>
                          )}
                          {isLeader && (
                            <button
                              onClick={() => handleResign(node.node_id)}
                              className="win-btn px-1.5 py-0.2 text-[10px] text-[#800000]"
                              title="Resign leadership"
                            >
                              Resign
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Panel: Lease Status & HA Architecture Overview */}
        <div className="win-outset p-2 bg-[#dcdcdc] flex flex-col gap-2">
          <div className="font-bold text-xs border-b pb-1">Leader Lease Consensus</div>
          <div className="win-inset bg-white p-2 font-mono text-[11px] flex flex-col gap-1.5">
            <div>
              <span className="text-gray-500">Current Leader:</span>{' '}
              <strong className="text-[#000080]">{status?.leader.leader_node_id || 'NONE'}</strong>
            </div>
            <div>
              <span className="text-gray-500">Lease Valid:</span>{' '}
              <span className={status?.leader.is_active ? 'text-[#008000] font-bold' : 'text-[#c00000] font-bold'}>
                {status?.leader.is_active ? 'YES (Active Consensus)' : 'NO (Expired)'}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Lease Expires:</span>{' '}
              <span className="text-xs">{status?.leader.lease_expires_at || 'N/A'}</span>
            </div>
            {status?.leader.last_leader && (
              <div>
                <span className="text-gray-500">Previous Leader:</span> {status.leader.last_leader}
              </div>
            )}
          </div>

          <div className="font-bold text-xs border-b pb-1 mt-1">High Availability Architecture</div>
          <div className="win-inset bg-white p-2 font-mono text-[10px] leading-tight text-gray-700">
            <p className="mb-1">
              <strong>Layer 4/7:</strong> External VIP / HAProxy balances client traffic.
            </p>
            <p className="mb-1">
              <strong>Control Plane:</strong> Lease-based leader coordinates reconciliation and queues.
            </p>
            <p className="mb-1">
              <strong>Job Queue:</strong> Compare-And-Swap atomic job claims with crash recovery.
            </p>
            <p>
              <strong>Data Store:</strong> Compatible with PostgreSQL Patroni HA & Connection Pooling.
            </p>
          </div>
        </div>
      </div>

      {/* Cluster Event Log */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex flex-col gap-1">
        <div className="flex justify-between items-center">
          <span className="font-bold text-xs">Cluster Audit & Failover Events ({events.length})</span>
          <span className="text-[10px] text-gray-600 font-mono">Real-time HA Event Stream</span>
        </div>
        <div className="win-inset bg-black text-[#00ff00] font-mono text-[11px] p-2 max-h-[160px] overflow-auto">
          {events.length === 0 ? (
            <div className="text-gray-500 italic">No events recorded.</div>
          ) : (
            events.map((ev) => (
              <div key={ev.id} className="leading-relaxed border-b border-[#222222] pb-0.5 mb-0.5">
                <span className="text-gray-400">[{new Date(ev.created_at).toLocaleTimeString()}]</span>{' '}
                <span
                  className={
                    ev.severity === 'CRITICAL' || ev.severity === 'ERROR'
                      ? 'text-[#ff4444] font-bold'
                      : ev.severity === 'WARNING'
                      ? 'text-[#ffbb33]'
                      : 'text-[#00ffcc]'
                  }
                >
                  [{ev.event_type}]
                </span>{' '}
                {ev.node_id && <span className="text-[#ffff00]">({ev.node_id})</span>}{' '}
                <span className="text-gray-200">{JSON.stringify(ev.details)}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Register Node Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="win-outset bg-[#dcdcdc] p-3 w-full max-w-md flex flex-col gap-3 font-sans">
            <div className="bg-[#000080] text-white p-1 font-bold flex justify-between items-center text-xs">
              <span>Register Cluster Node</span>
              <button
                onClick={() => setShowAddModal(false)}
                className="win-btn text-black px-1.5 py-0 text-xs font-mono"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleRegisterNode} className="flex flex-col gap-2 font-mono text-xs">
              <div>
                <label className="block text-[11px] font-bold text-gray-700">Node Identifier</label>
                <input
                  type="text"
                  value={newNodeId}
                  onChange={(e) => setNewNodeId(e.target.value)}
                  className="win-inset w-full p-1 bg-white"
                  required
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold text-gray-700">Hostname</label>
                <input
                  type="text"
                  value={newHostname}
                  onChange={(e) => setNewHostname(e.target.value)}
                  className="win-inset w-full p-1 bg-white"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-bold text-gray-700">IP Address</label>
                  <input
                    type="text"
                    value={newIp}
                    onChange={(e) => setNewIp(e.target.value)}
                    className="win-inset w-full p-1 bg-white"
                    required
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-gray-700">Port</label>
                  <input
                    type="number"
                    value={newPort}
                    onChange={(e) => setNewPort(parseInt(e.target.value) || 8000)}
                    className="win-inset w-full p-1 bg-white"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-[11px] font-bold text-gray-700">
                  Roles (comma separated: CONTROL_PLANE, WORKER, SCHEDULER, REPOSITORY_WORKER)
                </label>
                <input
                  type="text"
                  value={newRoles}
                  onChange={(e) => setNewRoles(e.target.value)}
                  className="win-inset w-full p-1 bg-white"
                  required
                />
              </div>
              <div className="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="win-btn px-3 py-1 font-bold"
                >
                  Cancel
                </button>
                <button type="submit" className="win-btn px-4 py-1 font-bold text-[#000080]">
                  Register
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
