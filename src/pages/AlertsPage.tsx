import React, { useState, useEffect } from 'react';
import { getAlerts, acknowledgeAlert, resolveAlert } from '../api/v7';
import type { AlertItem } from '../api/v7';

export const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('ACTIVE');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);

  const loadAlerts = async () => {
    setLoading(true);
    try {
      const res = await getAlerts(statusFilter || undefined, severityFilter || undefined);
      if (res.success) setAlerts(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
  }, [statusFilter, severityFilter]);

  const handleAck = async (id: number) => {
    try {
      await acknowledgeAlert(id);
      loadAlerts();
    } catch (e: any) {
      alert('Acknowledge failed: ' + e.message);
    }
  };

  const handleResolve = async (id: number) => {
    try {
      await resolveAlert(id);
      loadAlerts();
    } catch (e: any) {
      alert('Resolve failed: ' + e.message);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Top Banner */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold">Operational Alerting & Incident Notification Center</h2>
          <p className="text-[11px] text-gray-700">Real-time status of backup, replication, storage, and agent integrity alerts</p>
        </div>
        <button onClick={loadAlerts} className="win-btn px-3 py-1 font-bold">Refresh Alerts</button>
      </div>

      {/* Filter Bar */}
      <div className="win-outset p-2 flex items-center justify-between bg-white">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <span className="font-bold">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="win-inset bg-white p-1 text-xs"
            >
              <option value="">ALL STATUSES</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="RESOLVED">RESOLVED</option>
            </select>
          </div>

          <div className="flex items-center gap-1">
            <span className="font-bold">Severity:</span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="win-inset bg-white p-1 text-xs"
            >
              <option value="">ALL SEVERITIES</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="ERROR">ERROR</option>
              <option value="WARNING">WARNING</option>
              <option value="INFO">INFO</option>
            </select>
          </div>
        </div>

        <div className="text-[11px] font-mono text-gray-600">
          Showing <strong>{alerts.length}</strong> matching alert events
        </div>
      </div>

      {/* Alerts Table */}
      <div className="flex-1 win-inset bg-white p-1 overflow-auto">
        <table className="w-full border-collapse text-[11px] text-left">
          <thead>
            <tr className="bg-[#000080] text-white">
              <th className="p-1 border border-[#808080]">Severity</th>
              <th className="p-1 border border-[#808080]">Alert Type</th>
              <th className="p-1 border border-[#808080]">Title & Incident Message</th>
              <th className="p-1 border border-[#808080]">Resource</th>
              <th className="p-1 border border-[#808080]">Status</th>
              <th className="p-1 border border-[#808080]">Time (UTC)</th>
              <th className="p-1 border border-[#808080]">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="p-4 text-center text-gray-500">Loading alerts...</td>
              </tr>
            ) : alerts.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-4 text-center text-gray-500">No alerts found matching filter criteria.</td>
              </tr>
            ) : (
              alerts.map((a) => (
                <tr key={a.id} className="border-b border-[#dfdfdf] hover:bg-[#f0f0f0]">
                  <td className="p-1">
                    <span className={`px-1.5 py-0.5 text-[9px] font-bold font-mono text-white ${
                      a.severity === 'CRITICAL' ? 'bg-[#ff0000]' :
                      a.severity === 'ERROR' ? 'bg-[#aa0000]' :
                      a.severity === 'WARNING' ? 'bg-[#d4a017]' : 'bg-[#0055ff]'
                    }`}>
                      {a.severity}
                    </span>
                  </td>
                  <td className="p-1 font-mono font-bold">{a.alert_type}</td>
                  <td className="p-1">
                    <div className="font-bold">{a.title}</div>
                    <div className="text-[10px] text-gray-600">{a.message}</div>
                  </td>
                  <td className="p-1 font-mono text-[10px]">
                    {a.resource_type ? `${a.resource_type}:${a.resource_id || '*'}` : '-'}
                  </td>
                  <td className="p-1 font-mono font-bold">
                    <span className={`px-1 py-0.5 text-[9px] ${
                      a.status === 'ACTIVE' ? 'text-red-700 bg-red-100 font-bold' :
                      a.status === 'ACKNOWLEDGED' ? 'text-amber-700 bg-amber-100' :
                      'text-green-700 bg-green-100'
                    }`}>
                      {a.status}
                    </span>
                  </td>
                  <td className="p-1 font-mono text-[10px]">{a.created_at}</td>
                  <td className="p-1">
                    <div className="flex gap-1">
                      {a.status === 'ACTIVE' && (
                        <button
                          onClick={() => handleAck(a.id)}
                          className="win-btn px-2 py-0.5 text-[10px]"
                        >
                          Ack
                        </button>
                      )}
                      {a.status !== 'RESOLVED' && (
                        <button
                          onClick={() => handleResolve(a.id)}
                          className="win-btn px-2 py-0.5 text-[10px] text-green-800 font-bold"
                        >
                          Resolve
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
