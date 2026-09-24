import React, { useState, useEffect } from 'react';
import {
  getReports,
  generateReport,
  exportReport,
  getReportDownloadUrl
} from '../api/v10';
import type { ComplianceReport } from '../api/v10';

export const ReportsPage: React.FC = () => {
  const [reports, setReports] = useState<ComplianceReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<ComplianceReport | null>(null);
  const [reportType, setReportType] = useState<string>('comprehensive_compliance');
  const [titleInput, setTitleInput] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getReports();
      setReports(res);
      if (res.length > 0 && !selectedReport) {
        setSelectedReport(res[0]);
      }
    } catch (e: any) {
      console.error('Error loading reports:', e);
      setStatusMsg(`Error loading reports: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const rep = await generateReport(reportType, titleInput || undefined);
      setStatusMsg(`Report ${rep.report_id} generated successfully.`);
      setTitleInput('');
      await loadData();
      setSelectedReport(rep);
    } catch (e: any) {
      setStatusMsg(`Generation error: ${e.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = async (reportId: string, format: string) => {
    try {
      const exec = await exportReport(reportId, format);
      setStatusMsg(`Exported ${format} artifact (${exec.file_size_bytes} bytes). SHA-256: ${exec.checksum_sha256?.substring(0, 16)}...`);
      // Open download link in new tab or trigger browser download
      window.open(getReportDownloadUrl(reportId, format), '_blank');
    } catch (e: any) {
      setStatusMsg(`Export error: ${e.message}`);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#c0c0c0] p-2 overflow-auto text-[11px]">
      {/* Title Bar Area */}
      <div className="win-outset p-2 mb-2 bg-[#dfdfdf] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-[#000080]" />
          <span className="font-bold text-[12px] text-[#000080]">
            RetroVault Compliance & Enterprise Audit Report Center
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

      {/* Generate Report Toolbar */}
      <div className="win-outset p-2 mb-2 bg-white flex flex-col gap-1.5">
        <div className="font-bold text-[11px] text-[#000080]">Compile Auditable Compliance Report:</div>
        <div className="flex items-center gap-2 flex-wrap">
          <label className="text-[10px] text-[#666666] font-semibold">Report Template:</label>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            className="win-inset px-2 py-1 bg-white text-[11px]"
          >
            <option value="comprehensive_compliance">Comprehensive Compliance (13 Domains)</option>
            <option value="backup_operations">Backup Operations Report</option>
            <option value="recovery_readiness">Recovery Readiness & DR Report</option>
            <option value="security_controls">Security Controls & Ransomware Report</option>
            <option value="access_control">Access Control & MFA Report</option>
            <option value="retention">Retention Policy Compliance Report</option>
            <option value="immutability">Tamper-Proof Immutability Report</option>
            <option value="replication">Offsite Replication Audit Report</option>
            <option value="audit_activity">Audit Trail Activity Report</option>
            <option value="fleet_health">Agent Fleet Health Report</option>
            <option value="capacity_forecast">Storage Capacity & Forecast Report</option>
          </select>

          <input
            type="text"
            placeholder="Custom title (optional)..."
            value={titleInput}
            onChange={(e) => setTitleInput(e.target.value)}
            className="win-inset px-2 py-1 flex-1 bg-white text-[11px]"
          />

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="win-btn px-3 py-1 font-bold text-[#000080]"
          >
            {generating ? 'Compiling Evidence...' : 'Generate Report'}
          </button>
        </div>
      </div>

      {/* Split View: Reports Table & Evidence Inspector */}
      <div className="flex-1 flex gap-2 min-h-0">
        {/* Left Side: Generated Reports */}
        <div className="w-1/2 win-outset p-2 bg-white flex flex-col">
          <div className="font-bold text-[11px] text-[#000080] mb-1">
            Archived Audit Reports ({reports.length})
          </div>
          <div className="flex-1 overflow-auto">
            {reports.length === 0 ? (
              <div className="p-4 text-center text-[#666666]">No reports generated yet.</div>
            ) : (
              <table className="w-full border-collapse text-left text-[11px]">
                <thead>
                  <tr className="bg-[#000080] text-white">
                    <th className="p-1 border border-[#808080]">Report ID</th>
                    <th className="p-1 border border-[#808080]">Title</th>
                    <th className="p-1 border border-[#808080]">Type</th>
                    <th className="p-1 border border-[#808080]">Generated</th>
                    <th className="p-1 border border-[#808080]">Exports</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((r) => (
                    <tr
                      key={r.report_id}
                      onClick={() => setSelectedReport(r)}
                      className={`cursor-pointer border-b border-[#dfdfdf] ${
                        selectedReport?.report_id === r.report_id ? 'bg-[#cce5ff]' : 'hover:bg-[#f0f4f8]'
                      }`}
                    >
                      <td className="p-1 font-mono font-bold">{r.report_id}</td>
                      <td className="p-1 font-semibold">{r.title}</td>
                      <td className="p-1 font-mono text-[10px] text-[#555555]">{r.report_type}</td>
                      <td className="p-1 font-mono text-[10px]">{r.generated_at.substring(0, 16).replace('T', ' ')}</td>
                      <td className="p-1">
                        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => handleExport(r.report_id, 'JSON')}
                            className="win-btn px-1 py-0.5 text-[9px] font-mono"
                          >
                            JSON
                          </button>
                          <button
                            onClick={() => handleExport(r.report_id, 'CSV')}
                            className="win-btn px-1 py-0.5 text-[9px] font-mono"
                          >
                            CSV
                          </button>
                          <button
                            onClick={() => handleExport(r.report_id, 'PDF')}
                            className="win-btn px-1 py-0.5 text-[9px] font-mono font-bold text-[#b91c1c]"
                          >
                            PDF
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right Side: Report Evidence Viewer */}
        <div className="w-1/2 win-outset p-2 bg-[#f9fafb] flex flex-col overflow-auto">
          {selectedReport ? (
            <div className="flex flex-col gap-2 flex-1">
              <div className="flex justify-between items-center pb-1 border-b border-[#a0a0a0]">
                <div>
                  <span className="font-mono text-[12px] font-bold text-[#000080]">{selectedReport.report_id}</span>
                  <span className="text-[12px] font-bold text-[#333333] ml-2">{selectedReport.title}</span>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => handleExport(selectedReport.report_id, 'JSON')}
                    className="win-btn px-2 py-0.5 text-[10px] font-bold"
                  >
                    Export JSON
                  </button>
                  <button
                    onClick={() => handleExport(selectedReport.report_id, 'CSV')}
                    className="win-btn px-2 py-0.5 text-[10px] font-bold"
                  >
                    Export CSV
                  </button>
                  <button
                    onClick={() => handleExport(selectedReport.report_id, 'PDF')}
                    className="win-btn px-2 py-0.5 text-[10px] font-bold text-[#b91c1c]"
                  >
                    Export PDF
                  </button>
                </div>
              </div>

              {/* Metadata Banner */}
              <div className="win-inset p-2 bg-[#ffffff] grid grid-cols-3 gap-2 text-[10px] font-mono">
                <div>Scope: <span className="font-bold">{selectedReport.scope}</span></div>
                <div>System Version: <span className="font-bold">{selectedReport.system_version}</span></div>
                <div>Author: <span className="font-bold">{selectedReport.generated_by}</span></div>
                <div className="col-span-3">
                  Period: {selectedReport.period_start} to {selectedReport.period_end}
                </div>
              </div>

              {/* Factual Evidence Payload */}
              <div className="win-outset p-2 bg-white flex-1 flex flex-col">
                <div className="font-bold text-[11px] text-[#000080] mb-1">
                  Tamper-Evident Evidence Breakdown:
                </div>
                <div className="win-inset bg-[#1e1e1e] text-[#d4d4d4] p-2 flex-1 overflow-auto font-mono text-[10px]">
                  <pre>{JSON.stringify(selectedReport.evidence_summary, null, 2)}</pre>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-[#666666]">Select an enterprise report to inspect factual evidence.</div>
          )}
        </div>
      </div>
    </div>
  );
};
