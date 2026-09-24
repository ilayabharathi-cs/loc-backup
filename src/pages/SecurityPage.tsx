import React, { useState, useEffect } from 'react';
import { getSecurityOverview, setupMfa, verifyMfa, disableMfa, getSecurityAudit } from '../api/v7';
import { v8Api } from '../api/v8';
import type { SecurityEvent, SecurityIncident, IntegrityScan, DeletionGuardRequest, SecuritySimulation } from '../api/v8';

export const SecurityPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'events' | 'incidents' | 'integrity' | 'simulations' | 'mfa' | 'audit' | 'permissions'>('events');
  const [overview, setOverview] = useState<any>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [mfaData, setMfaData] = useState<{ secret: string; provisioning_uri: string; recovery_codes: string[] } | null>(null);
  const [verifyCode, setVerifyCode] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [msg, setMsg] = useState<string>('');

  // V8 state
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [incidents, setIncidents] = useState<SecurityIncident[]>([]);
  const [scans, setScans] = useState<IntegrityScan[]>([]);
  const [simulations, setSimulations] = useState<SecuritySimulation[]>([]);
  const [guards, setGuards] = useState<DeletionGuardRequest[]>([]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [oRes, aRes, evRes, incRes, scRes, simRes, gdRes] = await Promise.all([
        getSecurityOverview().catch(() => ({ success: false, data: null })),
        getSecurityAudit().catch(() => ({ success: false, data: [] })),
        v8Api.getSecurityEvents().catch(() => ({ data: [] })),
        v8Api.getIncidents().catch(() => ({ data: [] })),
        v8Api.getIntegrityScans().catch(() => ({ data: [] })),
        v8Api.getSimulations().catch(() => ({ data: [] })),
        v8Api.getDeletionGuardRequests().catch(() => ({ data: [] })),
      ]);

      if (oRes.success) setOverview(oRes.data);
      if (aRes.success) setAuditLogs(aRes.data);
      if (evRes.data) setEvents(evRes.data);
      if (incRes.data) setIncidents(incRes.data);
      if (scRes.data) setScans(scRes.data);
      if (simRes.data) setSimulations(simRes.data);
      if (gdRes.data) setGuards(gdRes.data);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunSimulation = async () => {
    try {
      setMsg('Running safe isolated ransomware drill...');
      const res = await v8Api.runSimulation({ scenario_type: 'RANSOMWARE_ENCRYPTION_BURST', file_count: 15, encryption_ratio: 0.8 });
      setMsg(`Simulation completed! Anomaly Score: ${res.data.simulated_anomaly_score}/100, Action: ${res.data.containment_action}`);
      loadData();
    } catch (err: any) {
      alert('Simulation failed: ' + err.message);
    }
  };

  const handleAcknowledgeEvent = async (id: number) => {
    try {
      await v8Api.acknowledgeEvent(id);
      loadData();
    } catch (err: any) {
      alert('Action failed: ' + err.message);
    }
  };

  const handleResolveEvent = async (id: number) => {
    try {
      await v8Api.resolveEvent(id, 'RESOLVED');
      loadData();
    } catch (err: any) {
      alert('Action failed: ' + err.message);
    }
  };

  const handleSetupMfa = async () => {
    try {
      const res = await setupMfa();
      if (res.success) {
        setMfaData(res.data);
        setMsg('Scan QR or enter secret in Authenticator app, then verify below.');
      }
    } catch (err: any) {
      alert('Setup failed: ' + err.message);
    }
  };

  const handleVerifyMfa = async () => {
    if (!verifyCode) return;
    try {
      const res = await verifyMfa(verifyCode);
      if (res.success) {
        alert('MFA successfully enabled!');
        setMfaData(null);
        setVerifyCode('');
        loadData();
      }
    } catch (err: any) {
      alert('Verification failed: ' + (err.response?.data?.error?.message || err.message));
    }
  };

  const handleDisableMfa = async () => {
    const code = prompt('Enter current 6-digit TOTP code or recovery code to disable MFA:');
    if (!code) return;
    try {
      const res = await disableMfa(code);
      if (res.success) {
        alert('MFA disabled.');
        loadData();
      }
    } catch (err: any) {
      alert('Disable failed: ' + (err.response?.data?.error?.message || err.message));
    }
  };

  return (
    <div className="flex-1 flex flex-col p-3 gap-2 overflow-auto bg-[#c0c0c0] font-sans text-xs">
      {/* Top Banner */}
      <div className="win-outset p-2 bg-[#dcdcdc] flex justify-between items-center">
        <div>
          <h2 className="text-sm font-bold flex items-center gap-2">
            <span>🛡️</span> RetroVault V8 Ransomware Resilience & Security Operations Center
          </h2>
          <p className="text-[11px] text-gray-700">Ransomware Anomaly Shield, Integrity Scans, Disaster Drills, and Guard Controls</p>
        </div>
        <div className="flex gap-2 items-center">
          {loading && <span className="text-[10px] text-gray-500 font-mono">Syncing...</span>}
          <span className="font-mono text-[11px]">Logged in: <strong>{overview?.username || 'admin'}</strong> ({overview?.role || 'ADMIN'})</span>
        </div>
      </div>

      {msg && (
        <div className="p-1.5 bg-[#ffffcc] text-[#000080] border border-[#808000] font-bold text-[11px] flex justify-between items-center">
          <span>{msg}</span>
          <button onClick={() => setMsg('')} className="text-xs px-1 text-gray-600">✕</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#808080] pt-1">
        <button
          onClick={() => setActiveTab('events')}
          className={`px-3 py-1 font-bold ${activeTab === 'events' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-gray-800'}`}
        >
          Security Events ({events.length})
        </button>
        <button
          onClick={() => setActiveTab('incidents')}
          className={`px-3 py-1 font-bold ${activeTab === 'incidents' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-gray-800'}`}
        >
          Incident Lifecycle ({incidents.length})
        </button>
        <button
          onClick={() => setActiveTab('integrity')}
          className={`px-3 py-1 font-bold ${activeTab === 'integrity' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-gray-800'}`}
        >
          Integrity & Deletion Guard
        </button>
        <button
          onClick={() => setActiveTab('simulations')}
          className={`px-3 py-1 font-bold ${activeTab === 'simulations' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-gray-800'}`}
        >
          Ransomware Sandbox Drills
        </button>
        <button
          onClick={() => setActiveTab('mfa')}
          className={`px-3 py-1 font-bold ${activeTab === 'mfa' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-gray-800'}`}
        >
          MFA & Access
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`px-3 py-1 font-bold ${activeTab === 'audit' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-gray-800'}`}
        >
          Audit Logs ({auditLogs.length})
        </button>
        <button
          onClick={() => setActiveTab('permissions')}
          className={`px-3 py-1 font-bold ${activeTab === 'permissions' ? 'win-outset bg-[#c0c0c0] border-b-0' : 'bg-[#a0a0a0] text-gray-800'}`}
        >
          RBAC Matrix
        </button>
      </div>

      {/* Tab: Security Events */}
      {activeTab === 'events' && (
        <div className="flex-1 win-inset bg-white p-1 overflow-auto flex flex-col gap-2">
          <div className="p-2 bg-[#f0f0f0] border-b flex justify-between items-center text-[11px]">
            <span className="font-bold">Real-time Multi-Signal Anomaly & Threat Detection Feed</span>
            <button onClick={loadData} className="win-btn px-2 py-0.5 font-bold">Refresh Events</button>
          </div>
          <table className="w-full border-collapse text-[11px] text-left">
            <thead>
              <tr className="bg-[#000080] text-white">
                <th className="p-1 border border-[#808080]">Severity</th>
                <th className="p-1 border border-[#808080]">Event Type</th>
                <th className="p-1 border border-[#808080]">Risk Score</th>
                <th className="p-1 border border-[#808080]">Description</th>
                <th className="p-1 border border-[#808080]">Status</th>
                <th className="p-1 border border-[#808080]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {events.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-4 text-center text-gray-500 font-mono">No security events detected. System healthy.</td>
                </tr>
              ) : (
                events.map((e) => (
                  <tr key={e.id} className="border-b border-[#dfdfdf] hover:bg-[#fff9e6]">
                    <td className="p-1 font-bold">
                      <span className={`px-1 py-0.5 text-white text-[10px] ${
                        e.severity === 'CRITICAL' ? 'bg-red-700' : e.severity === 'HIGH' ? 'bg-orange-600' : 'bg-blue-600'
                      }`}>
                        {e.severity}
                      </span>
                    </td>
                    <td className="p-1 font-mono font-bold">{e.event_type}</td>
                    <td className="p-1 font-mono font-bold text-red-700">{e.score}/100</td>
                    <td className="p-1 text-[11px]">{e.description}</td>
                    <td className="p-1 font-mono text-[10px]">{e.status}</td>
                    <td className="p-1 flex gap-1">
                      {e.status === 'OPEN' && (
                        <button onClick={() => handleAcknowledgeEvent(e.id)} className="win-btn px-1.5 py-0.5 text-[10px]">Ack</button>
                      )}
                      {e.status !== 'RESOLVED' && (
                        <button onClick={() => handleResolveEvent(e.id)} className="win-btn px-1.5 py-0.5 text-[10px] text-green-800 font-bold">Resolve</button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab: Security Incidents */}
      {activeTab === 'incidents' && (
        <div className="flex-1 win-inset bg-white p-2 overflow-auto flex flex-col gap-2">
          <div className="flex justify-between items-center bg-[#f0f0f0] p-1.5 border">
            <span className="font-bold">10-State Security Incident Response Workflow</span>
            <span className="text-[10px] text-gray-600 font-mono">DETECTED → CONFIRMED → TRIAGED → CONTAINED → REMEDIATING → VERIFYING → RESOLVED → CLOSED</span>
          </div>
          <table className="w-full border-collapse text-[11px] text-left">
            <thead>
              <tr className="bg-[#000080] text-white">
                <th className="p-1 border border-[#808080]">Incident #</th>
                <th className="p-1 border border-[#808080]">Title</th>
                <th className="p-1 border border-[#808080]">Severity</th>
                <th className="p-1 border border-[#808080]">Status</th>
                <th className="p-1 border border-[#808080]">Candidate RP</th>
                <th className="p-1 border border-[#808080]">Created</th>
              </tr>
            </thead>
            <tbody>
              {incidents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-4 text-center text-gray-500 font-mono">No active incidents.</td>
                </tr>
              ) : (
                incidents.map((inc) => (
                  <tr key={inc.id} className="border-b border-[#dfdfdf] hover:bg-[#f0f0f0]">
                    <td className="p-1 font-mono font-bold">{inc.incident_number}</td>
                    <td className="p-1 font-bold">{inc.title}</td>
                    <td className="p-1 font-mono">{inc.severity}</td>
                    <td className="p-1 font-mono font-bold text-blue-800">{inc.status}</td>
                    <td className="p-1 font-mono">{inc.candidate_recovery_point_id ? `RP #${inc.candidate_recovery_point_id}` : 'None'}</td>
                    <td className="p-1 font-mono text-[10px]">{inc.created_at}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab: Integrity & Deletion Guard */}
      {activeTab === 'integrity' && (
        <div className="flex-1 win-inset bg-white p-3 overflow-auto flex flex-col gap-4">
          <div className="win-outset p-2 bg-[#f8f8f8]">
            <div className="font-bold text-sm mb-1">Deep Cryptographic Repository Integrity Monitor</div>
            <p className="text-gray-600 text-[11px] mb-2">Scans physical CAS repository objects, verifies SHA-256 signatures, and isolates bit rot or tampered files into quarantine.</p>
            <div className="flex gap-2">
              <button
                onClick={async () => {
                  try {
                    setMsg('Starting integrity scan...');
                    const res = await v8Api.triggerIntegrityScan({ repository_id: 1, scan_type: 'FULL' });
                    setMsg(`Scan finished! Valid: ${res.data.valid_objects}, Corrupted: ${res.data.corrupted_objects}, Status: ${res.data.status}`);
                    loadData();
                  } catch (e: any) {
                    alert('Scan failed: ' + e.message);
                  }
                }}
                className="win-btn px-3 py-1 font-bold bg-[#dfdfdf]"
              >
                Trigger Deep Integrity Scan (Repo #1)
              </button>
            </div>
            {scans.length > 0 && (
              <div className="mt-2 text-[10px] font-mono">
                Latest Scan: {scans[0].scan_id} | Status: <strong className="text-blue-800">{scans[0].status}</strong> | Total: {scans[0].total_objects} | Valid: {scans[0].valid_objects} | Corrupted: {scans[0].corrupted_objects}
              </div>
            )}
          </div>

          <div className="win-outset p-2 bg-[#f8f8f8]">
            <div className="font-bold text-sm mb-1">Mass-Deletion Guard & MFA Authorization Queue</div>
            <p className="text-gray-600 text-[11px] mb-2">Intercepts bulk deletion of recovery points or policies. High risk actions require dual-authorization and MFA token.</p>
            <table className="w-full border-collapse text-[11px] text-left">
              <thead>
                <tr className="bg-[#000080] text-white">
                  <th className="p-1 border border-[#808080]">Request ID</th>
                  <th className="p-1 border border-[#808080]">Type</th>
                  <th className="p-1 border border-[#808080]">Requester</th>
                  <th className="p-1 border border-[#808080]">Risk Score</th>
                  <th className="p-1 border border-[#808080]">Status</th>
                </tr>
              </thead>
              <tbody>
                {guards.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-2 text-center text-gray-500 font-mono">No pending deletion guard requests.</td>
                  </tr>
                ) : (
                  guards.map((g) => (
                    <tr key={g.id} className="border-b border-[#dfdfdf]">
                      <td className="p-1 font-mono">GUARD-{g.id}</td>
                      <td className="p-1 font-bold">{g.request_type}</td>
                      <td className="p-1 font-mono">{g.requester_username}</td>
                      <td className="p-1 font-mono font-bold text-red-700">{g.risk_score}/100</td>
                      <td className="p-1 font-mono">{g.status}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab: Sandbox Simulations */}
      {activeTab === 'simulations' && (
        <div className="flex-1 win-inset bg-white p-3 overflow-auto flex flex-col gap-3">
          <div className="win-outset p-3 bg-[#f8f8f8] flex justify-between items-center">
            <div>
              <div className="font-bold text-sm">Safe Isolated Ransomware & Disaster Recovery Sandbox Drills</div>
              <div className="text-gray-600 text-[11px]">Generates isolated synthetic high-entropy bursts in temp sandbox to verify detection & containment without touching production data</div>
            </div>
            <button
              onClick={handleRunSimulation}
              className="win-btn px-4 py-1.5 font-bold bg-[#000080] text-white"
            >
              Execute Sandbox Drill
            </button>
          </div>

          <div className="font-bold text-sm mt-2">Simulation History</div>
          <table className="w-full border-collapse text-[11px] text-left">
            <thead>
              <tr className="bg-[#000080] text-white">
                <th className="p-1 border border-[#808080]">Simulation ID</th>
                <th className="p-1 border border-[#808080]">Scenario</th>
                <th className="p-1 border border-[#808080]">Status</th>
                <th className="p-1 border border-[#808080]">Results Summary</th>
                <th className="p-1 border border-[#808080]">Executed At</th>
              </tr>
            </thead>
            <tbody>
              {simulations.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-3 text-center text-gray-500 font-mono">No simulation drills executed yet. Click above to run a safe test drill.</td>
                </tr>
              ) : (
                simulations.map((s) => (
                  <tr key={s.id} className="border-b border-[#dfdfdf] hover:bg-[#f0f0f0]">
                    <td className="p-1 font-mono font-bold">{s.simulation_id}</td>
                    <td className="p-1 font-mono">{s.scenario_type}</td>
                    <td className="p-1 font-mono font-bold text-green-700">{s.status}</td>
                    <td className="p-1 text-[10px] font-mono">{s.results_json || 'Completed'}</td>
                    <td className="p-1 font-mono text-[10px]">{s.started_at}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab: MFA */}
      {activeTab === 'mfa' && (
        <div className="flex-1 win-inset bg-white p-3 flex flex-col gap-3">
          <div className="win-outset p-3 bg-[#f8f8f8] flex justify-between items-center">
            <div>
              <div className="font-bold text-sm">Two-Factor Authentication (TOTP - RFC 6238)</div>
              <div className="text-gray-600 text-[11px]">Requires Google Authenticator, Authy, or Microsoft Authenticator for login</div>
            </div>
            <div>
              {overview?.mfa_enabled ? (
                <div className="flex items-center gap-2">
                  <span className="px-2 py-1 bg-[#008000] text-white font-mono font-bold">MFA ACTIVE</span>
                  <button onClick={handleDisableMfa} className="win-btn px-2 py-1 text-red-700 font-bold">Disable MFA</button>
                </div>
              ) : (
                <button onClick={handleSetupMfa} className="win-btn px-3 py-1 font-bold bg-[#000080] text-white">
                  Enable MFA
                </button>
              )}
            </div>
          </div>

          {mfaData && (
            <div className="win-outset p-3 bg-white flex flex-col gap-2">
              <div className="font-bold text-[#000080]">MFA Enrollment Key</div>
              <div className="font-mono text-sm bg-[#e8e8e8] p-2 win-inset select-all font-bold">
                {mfaData.secret}
              </div>
              <div className="text-[10px] text-gray-600 font-mono">
                Provisioning URI: {mfaData.provisioning_uri}
              </div>

              <div className="mt-2">
                <div className="font-bold mb-1">One-Time Emergency Recovery Codes:</div>
                <div className="grid grid-cols-4 gap-1 font-mono text-[10px] bg-[#ffffe0] p-2 win-inset">
                  {mfaData.recovery_codes.map((c, idx) => (
                    <div key={idx} className="font-bold">{c}</div>
                  ))}
                </div>
              </div>

              <div className="mt-2 flex gap-2 items-center">
                <input
                  type="text"
                  placeholder="Enter 6-digit TOTP code"
                  value={verifyCode}
                  onChange={(e) => setVerifyCode(e.target.value)}
                  className="win-inset bg-white p-1 font-mono text-center text-sm w-44"
                  maxLength={6}
                />
                <button
                  onClick={handleVerifyMfa}
                  className="win-btn px-4 py-1 font-bold bg-[#dfdfdf]"
                >
                  Verify & Activate MFA
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Audit Logs */}
      {activeTab === 'audit' && (
        <div className="flex-1 win-inset bg-white p-1 overflow-auto">
          <table className="w-full border-collapse text-[11px] text-left">
            <thead>
              <tr className="bg-[#000080] text-white">
                <th className="p-1 border border-[#808080]">Time (UTC)</th>
                <th className="p-1 border border-[#808080]">Action</th>
                <th className="p-1 border border-[#808080]">Resource</th>
                <th className="p-1 border border-[#808080]">Target ID</th>
                <th className="p-1 border border-[#808080]">User ID</th>
                <th className="p-1 border border-[#808080]">Details</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((l) => (
                <tr key={l.id} className="border-b border-[#dfdfdf] hover:bg-[#f0f0f0]">
                  <td className="p-1 font-mono text-[10px]">{l.timestamp}</td>
                  <td className="p-1 font-mono font-bold">{l.action}</td>
                  <td className="p-1 font-mono">{l.resource_type}</td>
                  <td className="p-1 font-mono">{l.resource_id || '-'}</td>
                  <td className="p-1 font-mono">{l.user_id || 'System'}</td>
                  <td className="p-1 text-[10px] text-gray-700">{l.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab: Permissions Matrix */}
      {activeTab === 'permissions' && (
        <div className="flex-1 win-inset bg-white p-3 overflow-auto">
          <div className="font-bold text-sm mb-2">Granular Role-Based Access Control (RBAC) Permissions Matrix</div>
          <table className="w-full border-collapse text-[11px] text-left">
            <thead>
              <tr className="bg-[#000080] text-white">
                <th className="p-1.5 border border-[#808080]">Role</th>
                <th className="p-1.5 border border-[#808080]">Granted Permissions</th>
                <th className="p-1.5 border border-[#808080]">Scope</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b">
                <td className="p-2 font-bold font-mono">ADMIN</td>
                <td className="p-2 font-mono text-[10px] text-[#008000] font-bold">* (Full System Control)</td>
                <td className="p-2">Repositories, replication, security, users, encryption, DR, policies</td>
              </tr>
              <tr className="border-b">
                <td className="p-2 font-bold font-mono">OPERATOR</td>
                <td className="p-2 font-mono text-[10px]">
                  clients.read, clients.manage, backup.execute, restore.execute, repositories.read, replication.execute, dr.execute
                </td>
                <td className="p-2">Day-to-day backup, restore, and replication operations</td>
              </tr>
              <tr className="border-b">
                <td className="p-2 font-bold font-mono">AUDITOR</td>
                <td className="p-2 font-mono text-[10px]">
                  audit.read, security.manage, clients.read, repositories.read, policies.read
                </td>
                <td className="p-2">Compliance reporting, security audit trail review</td>
              </tr>
              <tr className="border-b">
                <td className="p-2 font-bold font-mono">VIEWER</td>
                <td className="p-2 font-mono text-[10px]">
                  clients.read, policies.read, repositories.read, audit.read, replication.read, dr.read
                </td>
                <td className="p-2">Read-only operational status dashboards</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
