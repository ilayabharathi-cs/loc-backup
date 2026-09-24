import React, { useState, useEffect } from 'react';
import {
  getSystemHealth,
  getOperationalAlerts,
  acknowledgeAlert,
  resolveAlert,
  getRecommendations
} from '../api/v10';
import type { SystemHealth, OperationalAlert, Recommendation } from '../api/v10';

export const OperationsPage: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [alerts, setAlerts] = useState<OperationalAlert[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'health' | 'alerts' | 'recommendations'>('health');
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [hRes, aRes, rRes] = await Promise.all([
        getSystemHealth('deep_health'),
        getOperationalAlerts(),
        getRecommendations()
      ]);
      setHealth(hRes);
      setAlerts(Array.isArray(aRes) ? aRes : []);
      setRecommendations(Array.isArray(rRes) ? rRes : []);
    } catch (e: any) {
      console.error('Error loading operations data:', e);
      setStatusMsg(`Error loading data: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 15000);
    return () => clearInterval(timer);
  }, []);

  const handleAckAlert = async (alertId: string) => {
    try {
      await acknowledgeAlert(alertId);
      setStatusMsg(`Alert ${alertId} acknowledged.`);
      await loadData();
    } catch (e: any) {
      setStatusMsg(`Failed to acknowledge alert: ${e.message}`);
    }
  };

  const handleResolveAlert = async (alertId: string) => {
    try {
      await resolveAlert(alertId);
      setStatusMsg(`Alert ${alertId} marked as resolved.`);
      await loadData();
    } catch (e: any) {
      setStatusMsg(`Failed to resolve alert: ${e.message}`);
    }
  };

  const getStatusBadge = (st: string) => {
    switch (st) {
      case 'HEALTHY':
        return <span className="bg-[#008000] text-white px-2 py-0.5 text-[10px] font-bold">HEALTHY</span>;
      case 'WARNING':
        return <span className="bg-[#d97706] text-white px-2 py-0.5 text-[10px] font-bold">WARNING</span>;
      case 'DEGRADED':
        return <span className="bg-[#ea580c] text-white px-2 py-0.5 text-[10px] font-bold">DEGRADED</span>;
      case 'CRITICAL':
        return <span className="bg-[#b91c1c] text-white px-2 py-0.5 text-[10px] font-bold animate-pulse">CRITICAL</span>;
      default:
        return <span className="bg-[#6b7280] text-white px-2 py-0.5 text-[10px] font-bold">{st}</span>;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#c0c0c0] p-2 overflow-auto text-[11px]">
      {/* Title Bar Area */}
      <div className="win-outset p-2 mb-2 bg-[#dfdfdf] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-[#000080]" />
          <span className="font-bold text-[12px] text-[#000080]">
            RetroVault Operations Center — Operational Intelligence & Health Console
          </span>
        </div>
        <div className="flex items-center gap-2">
          {health && getStatusBadge(health.overall_status)}
          <button onClick={loadData} className="win-btn px-2 py-0.5 text-[11px] font-bold">
            {loading ? 'Refreshing...' : 'Refresh Now'}
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="win-inset p-1.5 mb-2 bg-[#ffffe0] text-[#000000] flex justify-between items-center text-[11px]">
          <span>{statusMsg}</span>
          <button onClick={() => setStatusMsg(null)} className="font-bold text-[#b91c1c]">×</button>
        </div>
      )}

      {/* Explainable Overall Health Banner */}
      {health && (
        <div className="win-outset p-2 mb-2 bg-[#ffffff]">
          <div className="flex items-center justify-between mb-1">
            <span className="font-bold text-[11px] text-[#000000]">System Health Explanation:</span>
            <span className="text-[10px] text-[#666666]">Evaluated: {health.evaluated_at}</span>
          </div>
          <p className="text-[11px] text-[#333333] font-mono bg-[#f3f4f6] p-1.5 win-inset">
            {health.overall_reason}
          </p>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-1 border-b border-[#808080]">
        <button
          onClick={() => setActiveTab('health')}
          className={`px-3 py-1 font-bold text-[11px] ${
            activeTab === 'health' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-[#ffffff]'
          }`}
        >
          Infrastructure Components ({health?.components ? Object.keys(health.components).length : 0})
        </button>
        <button
          onClick={() => setActiveTab('alerts')}
          className={`px-3 py-1 font-bold text-[11px] ${
            activeTab === 'alerts' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-[#ffffff]'
          }`}
        >
          Operational Alerts ({(Array.isArray(alerts) ? alerts : []).filter(a => a.status === 'ACTIVE').length} Active)
        </button>
        <button
          onClick={() => setActiveTab('recommendations')}
          className={`px-3 py-1 font-bold text-[11px] ${
            activeTab === 'recommendations' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-[#ffffff]'
          }`}
        >
          Explainable Recommendations ({(Array.isArray(recommendations) ? recommendations : []).length})
        </button>
      </div>

      {/* Tab 1: Components Health */}
      {activeTab === 'health' && health && (
        <div className="win-inset bg-white p-1 flex-1 overflow-auto">
          <table className="w-full border-collapse text-left text-[11px]">
            <thead>
              <tr className="bg-[#000080] text-white">
                <th className="p-1 border border-[#808080]">Component</th>
                <th className="p-1 border border-[#808080]">Status</th>
                <th className="p-1 border border-[#808080]">Latency</th>
                <th className="p-1 border border-[#808080]">Reason / System Finding</th>
                <th className="p-1 border border-[#808080]">Last Success</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(health.components || {}).map(([name, comp]) => (
                <tr key={name} className="hover:bg-[#f0f4f8] border-b border-[#dfdfdf]">
                  <td className="p-1 font-bold text-[#000080] uppercase">{comp?.component || name}</td>
                  <td className="p-1">{getStatusBadge(comp?.status || 'UNKNOWN')}</td>
                  <td className="p-1 font-mono">{comp?.latency_ms ?? 0} ms</td>
                  <td className="p-1 text-[#333333]">{comp?.reason || 'Component operational'}</td>
                  <td className="p-1 font-mono text-[10px] text-[#666666]">
                    {comp?.last_success ? comp.last_success.substring(0, 19).replace('T', ' ') : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 2: Operational Alerts */}
      {activeTab === 'alerts' && (
        <div className="win-inset bg-white p-1 flex-1 overflow-auto">
          {alerts.length === 0 ? (
            <div className="p-4 text-center text-[#666666]">No operational alerts recorded in database.</div>
          ) : (
            <table className="w-full border-collapse text-left text-[11px]">
              <thead>
                <tr className="bg-[#000080] text-white">
                  <th className="p-1 border border-[#808080]">Alert ID</th>
                  <th className="p-1 border border-[#808080]">Type</th>
                  <th className="p-1 border border-[#808080]">Severity</th>
                  <th className="p-1 border border-[#808080]">Status</th>
                  <th className="p-1 border border-[#808080]">Resource</th>
                  <th className="p-1 border border-[#808080]">Count</th>
                  <th className="p-1 border border-[#808080]">Last Seen</th>
                  <th className="p-1 border border-[#808080]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alt) => (
                  <tr key={alt.alert_id} className="hover:bg-[#f0f4f8] border-b border-[#dfdfdf]">
                    <td className="p-1 font-mono font-bold">{alt.alert_id}</td>
                    <td className="p-1 font-semibold">{alt.alert_type}</td>
                    <td className="p-1">
                      <span className={`px-1 py-0.5 text-[9px] font-bold text-white ${
                        alt.severity === 'CRITICAL' ? 'bg-[#b91c1c]' : alt.severity === 'ERROR' ? 'bg-[#ea580c]' : 'bg-[#d97706]'
                      }`}>
                        {alt.severity}
                      </span>
                    </td>
                    <td className="p-1">
                      <span className={`px-1 py-0.5 text-[9px] font-bold ${
                        alt.status === 'ACTIVE' ? 'bg-[#ffcccc] text-[#990000]' : 'bg-[#ccffcc] text-[#006600]'
                      }`}>
                        {alt.status}
                      </span>
                    </td>
                    <td className="p-1 font-mono text-[10px]">{alt.resource_id}</td>
                    <td className="p-1 font-mono font-bold text-center">{alt.occurrence_count}</td>
                    <td className="p-1 font-mono text-[10px]">{alt.last_seen_at.substring(0, 19).replace('T', ' ')}</td>
                    <td className="p-1">
                      <div className="flex gap-1">
                        {alt.status === 'ACTIVE' && (
                          <button
                            onClick={() => handleAckAlert(alt.alert_id)}
                            className="win-btn px-1 py-0.5 text-[10px]"
                          >
                            Ack
                          </button>
                        )}
                        {alt.status !== 'RESOLVED' && (
                          <button
                            onClick={() => handleResolveAlert(alt.alert_id)}
                            className="win-btn px-1 py-0.5 text-[10px]"
                          >
                            Resolve
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab 3: Explainable Recommendations */}
      {activeTab === 'recommendations' && (
        <div className="win-inset bg-white p-2 flex-1 overflow-auto flex flex-col gap-2">
          {recommendations.length === 0 ? (
            <div className="p-4 text-center text-[#666666]">
              All backup objectives, replication schedules, and cluster resources are operating nominally. No recommendations needed.
            </div>
          ) : (
            recommendations.map((rec) => (
              <div key={rec.id} className="win-outset p-2 bg-[#f9fafb] border border-[#a0a0a0]">
                <div className="flex justify-between items-center mb-1">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 text-[10px] font-bold text-white ${
                      rec.severity === 'CRITICAL' || rec.severity === 'HIGH' ? 'bg-[#b91c1c]' : 'bg-[#d97706]'
                    }`}>
                      {rec.severity}
                    </span>
                    <span className="font-bold text-[12px] text-[#000080]">{rec.affected_resource}</span>
                  </div>
                  <span className="text-[10px] text-[#666666] font-mono">{rec.id}</span>
                </div>
                <div className="text-[11px] mb-1">
                  <span className="font-bold text-[#000000]">Factual Reason: </span>
                  <span className="text-[#333333]">{rec.reason}</span>
                </div>
                <div className="text-[11px] mb-1 bg-[#eef2f6] p-1 win-inset font-mono text-[10px]">
                  <span className="font-bold">Evidence: </span>
                  {JSON.stringify(rec.evidence)}
                </div>
                <div className="text-[11px] text-[#006600] font-semibold">
                  <span className="font-bold text-[#000000]">Recommended Action: </span>
                  {rec.recommended_action}
                </div>
                <div className="mt-1 text-[9px] text-[#888888] italic">
                  Note: Automated destructive remediation is disabled by policy. Operator review is required.
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
