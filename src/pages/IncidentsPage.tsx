import React, { useState, useEffect } from 'react';
import {
  getOperationalIncidents,
  updateIncidentStatus
} from '../api/v10';
import type { OperationalIncident } from '../api/v10';

export const IncidentsPage: React.FC = () => {
  const [incidents, setIncidents] = useState<OperationalIncident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<OperationalIncident | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [noteInput, setNoteInput] = useState<string>('');

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getOperationalIncidents();
      setIncidents(res);
      if (res.length > 0 && !selectedIncident) {
        setSelectedIncident(res[0]);
      } else if (selectedIncident) {
        const updated = res.find(i => i.incident_id === selectedIncident.incident_id);
        if (updated) setSelectedIncident(updated);
      }
    } catch (e: any) {
      console.error('Error loading incidents:', e);
      setStatusMsg(`Error: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUpdateStatus = async (newStatus: string) => {
    if (!selectedIncident) return;
    try {
      const updated = await updateIncidentStatus(selectedIncident.incident_id, newStatus, noteInput || undefined);
      setSelectedIncident(updated);
      setNoteInput('');
      setStatusMsg(`Incident ${updated.incident_id} updated to ${newStatus}.`);
      await loadData();
    } catch (e: any) {
      setStatusMsg(`Failed to update status: ${e.message}`);
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case 'CRITICAL':
        return <span className="bg-[#b91c1c] text-white px-2 py-0.5 text-[10px] font-bold">CRITICAL</span>;
      case 'HIGH':
        return <span className="bg-[#ea580c] text-white px-2 py-0.5 text-[10px] font-bold">HIGH</span>;
      case 'MEDIUM':
        return <span className="bg-[#d97706] text-white px-2 py-0.5 text-[10px] font-bold">MEDIUM</span>;
      default:
        return <span className="bg-[#008000] text-white px-2 py-0.5 text-[10px] font-bold">LOW</span>;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#c0c0c0] p-2 overflow-auto text-[11px]">
      {/* Title Bar Area */}
      <div className="win-outset p-2 mb-2 bg-[#dfdfdf] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-[#b91c1c]" />
          <span className="font-bold text-[12px] text-[#000080]">
            RetroVault Incident Management & Alert Correlation Console
          </span>
        </div>
        <button onClick={loadData} className="win-btn px-2 py-0.5 text-[11px] font-bold">
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {statusMsg && (
        <div className="win-inset p-1.5 mb-2 bg-[#ffffe0] text-[#000000] flex justify-between items-center text-[11px]">
          <span>{statusMsg}</span>
          <button onClick={() => setStatusMsg(null)} className="font-bold text-[#b91c1c]">×</button>
        </div>
      )}

      {/* Main Split Layout */}
      <div className="flex-1 flex gap-2 min-h-0">
        {/* Left Side: Incident List */}
        <div className="w-1/2 win-outset p-2 bg-white flex flex-col">
          <div className="font-bold text-[11px] text-[#000080] mb-1">
            Correlated Operational Incidents ({incidents.length})
          </div>
          <div className="flex-1 overflow-auto">
            {incidents.length === 0 ? (
              <div className="p-4 text-center text-[#666666]">No operational incidents detected.</div>
            ) : (
              <table className="w-full border-collapse text-left text-[11px]">
                <thead>
                  <tr className="bg-[#000080] text-white">
                    <th className="p-1 border border-[#808080]">ID</th>
                    <th className="p-1 border border-[#808080]">Title</th>
                    <th className="p-1 border border-[#808080]">Severity</th>
                    <th className="p-1 border border-[#808080]">Status</th>
                    <th className="p-1 border border-[#808080]">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.map((inc) => (
                    <tr
                      key={inc.incident_id}
                      onClick={() => setSelectedIncident(inc)}
                      className={`cursor-pointer border-b border-[#dfdfdf] ${
                        selectedIncident?.incident_id === inc.incident_id ? 'bg-[#cce5ff]' : 'hover:bg-[#f0f4f8]'
                      }`}
                    >
                      <td className="p-1 font-mono font-bold">{inc.incident_id}</td>
                      <td className="p-1 font-semibold">{inc.title}</td>
                      <td className="p-1">{getSeverityBadge(inc.severity)}</td>
                      <td className="p-1 font-bold text-[10px]">{inc.status}</td>
                      <td className="p-1 font-mono text-[10px]">{inc.created_at.substring(0, 16).replace('T', ' ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right Side: Incident Detail & Timeline */}
        <div className="w-1/2 win-outset p-2 bg-[#f9fafb] flex flex-col overflow-auto">
          {selectedIncident ? (
            <div className="flex flex-col gap-2 flex-1">
              <div className="flex justify-between items-center pb-1 border-b border-[#a0a0a0]">
                <div>
                  <span className="font-mono text-[12px] font-bold text-[#000080]">{selectedIncident.incident_id}</span>
                  <span className="text-[12px] font-bold text-[#333333] ml-2">{selectedIncident.title}</span>
                </div>
                {getSeverityBadge(selectedIncident.severity)}
              </div>

              {/* Status and Transition Actions */}
              <div className="win-inset p-2 bg-[#ffffff] flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-[#000000]">Current Lifecycle Status:</span>
                  <span className="font-mono font-bold text-[#000080] px-2 py-0.5 bg-[#e5e7eb] win-inset">
                    {selectedIncident.status}
                  </span>
                </div>
                <div className="flex gap-1 flex-wrap mt-1">
                  <button
                    onClick={() => handleUpdateStatus('INVESTIGATING')}
                    className="win-btn px-2 py-0.5 text-[10px]"
                  >
                    Mark Investigating
                  </button>
                  <button
                    onClick={() => handleUpdateStatus('MITIGATING')}
                    className="win-btn px-2 py-0.5 text-[10px]"
                  >
                    Mark Mitigating
                  </button>
                  <button
                    onClick={() => handleUpdateStatus('MONITORING')}
                    className="win-btn px-2 py-0.5 text-[10px]"
                  >
                    Mark Monitoring
                  </button>
                  <button
                    onClick={() => handleUpdateStatus('RESOLVED')}
                    className="win-btn px-2 py-0.5 text-[10px] font-bold text-[#008000]"
                  >
                    Resolve Incident
                  </button>
                  <button
                    onClick={() => handleUpdateStatus('CLOSED')}
                    className="win-btn px-2 py-0.5 text-[10px] font-bold text-[#555555]"
                  >
                    Close
                  </button>
                </div>
                <div className="flex gap-1 mt-1">
                  <input
                    type="text"
                    placeholder="Add operational investigation note..."
                    value={noteInput}
                    onChange={(e) => setNoteInput(e.target.value)}
                    className="win-inset px-2 py-0.5 flex-1 bg-white text-[11px]"
                  />
                </div>
              </div>

              {/* Correlation Details */}
              <div className="win-outset p-2 bg-white">
                <div className="font-bold text-[11px] text-[#000080] mb-1">Root Event & Evidence:</div>
                <div className="text-[11px] mb-1">
                  <span className="font-semibold">Root Event: </span>
                  <span className="font-mono text-[#b91c1c]">{selectedIncident.root_event}</span>
                </div>
                <div className="text-[11px] mb-1">
                  <span className="font-semibold">Relationship Type: </span>
                  <span className="font-mono">{selectedIncident.relationship_type}</span>
                </div>
                <div className="text-[11px] mb-1">
                  <span className="font-semibold">Affected Resources ({selectedIncident.affected_resources.length}): </span>
                  <span className="font-mono text-[10px]">{selectedIncident.affected_resources.join(', ')}</span>
                </div>
                <div className="text-[11px]">
                  <span className="font-semibold">Correlated Child Alerts ({selectedIncident.child_alerts.length}): </span>
                  <span className="font-mono text-[10px]">{selectedIncident.child_alerts.join(', ')}</span>
                </div>
              </div>

              {/* Incident Timeline */}
              <div className="win-outset p-2 bg-white flex-1 flex flex-col">
                <div className="font-bold text-[11px] text-[#000080] mb-1">Incident Event Timeline:</div>
                <div className="flex-1 overflow-auto flex flex-col gap-1">
                  {selectedIncident.timeline.map((entry, idx) => (
                    <div key={idx} className="win-inset p-1 bg-[#f9fafb] text-[10px] font-mono">
                      <div className="flex justify-between text-[#666666]">
                        <span>{entry.timestamp.substring(0, 19).replace('T', ' ')}</span>
                        <span>{entry.user || 'SYSTEM'}</span>
                      </div>
                      <div className="font-bold text-[#000080]">{entry.event}</div>
                      <div className="text-[#333333]">{entry.message || entry.note}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-[#666666]">Select an incident to view root-cause analysis and timeline.</div>
          )}
        </div>
      </div>
    </div>
  );
};
