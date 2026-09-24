import React, { useState, useEffect } from 'react';
import {
  getCapacityOverview,
  takeCapacitySnapshot,
  getCapacityForecast
} from '../api/v10';
import type { CapacityOverview, CapacityForecast } from '../api/v10';

export const CapacityPage: React.FC = () => {
  const [capacity, setCapacity] = useState<CapacityOverview | null>(null);
  const [selectedRepoId, setSelectedRepoId] = useState<number | null>(null);
  const [forecast, setForecast] = useState<CapacityForecast | null>(null);
  const [forecastWindow, setForecastWindow] = useState<number>(30);
  const [loading, setLoading] = useState<boolean>(true);
  const [forecastLoading, setForecastLoading] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await getCapacityOverview();
      setCapacity(res);
      if (res.repositories.length > 0 && selectedRepoId === null) {
        setSelectedRepoId(res.repositories[0].repository_id);
      }
    } catch (e: any) {
      console.error('Error loading capacity data:', e);
      setStatusMsg(`Error loading capacity overview: ${e.message || e}`);
    } finally {
      setLoading(false);
    }
  };

  const loadForecast = async (repoId: number, windowDays: number) => {
    setForecastLoading(true);
    try {
      const res = await getCapacityForecast(repoId, windowDays);
      setForecast(res);
    } catch (e: any) {
      console.error('Error loading forecast:', e);
      setStatusMsg(`Forecast error: ${e.message || e}`);
    } finally {
      setForecastLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedRepoId !== null) {
      loadForecast(selectedRepoId, forecastWindow);
    }
  }, [selectedRepoId, forecastWindow]);

  const handleTakeSnapshot = async (repoId: number) => {
    try {
      await takeCapacitySnapshot(repoId);
      setStatusMsg(`Snapshot taken for repository ID ${repoId}.`);
      await loadData();
      if (selectedRepoId === repoId) {
        await loadForecast(repoId, forecastWindow);
      }
    } catch (e: any) {
      setStatusMsg(`Failed to take snapshot: ${e.message}`);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#c0c0c0] p-2 overflow-auto text-[11px]">
      {/* Title Bar Area */}
      <div className="win-outset p-2 mb-2 bg-[#dfdfdf] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-[#008080]" />
          <span className="font-bold text-[12px] text-[#000080]">
            RetroVault Storage Capacity Intelligence & Mathematical Forecasting
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

      {/* Global Storage Cards */}
      {capacity && (
        <div className="grid grid-cols-4 gap-2 mb-2">
          <div className="win-outset p-2 bg-[#f9fafb]">
            <div className="text-[#666666] font-semibold text-[10px]">TOTAL REPOSITORIES</div>
            <div className="text-[16px] font-bold text-[#000080] font-mono">{capacity.total_repositories}</div>
          </div>
          <div className="win-outset p-2 bg-[#f9fafb]">
            <div className="text-[#666666] font-semibold text-[10px]">TOTAL CAPACITY</div>
            <div className="text-[16px] font-bold text-[#333333] font-mono">{formatBytes(capacity.total_capacity_bytes)}</div>
          </div>
          <div className="win-outset p-2 bg-[#f9fafb]">
            <div className="text-[#666666] font-semibold text-[10px]">TOTAL USED</div>
            <div className="text-[16px] font-bold text-[#b91c1c] font-mono">{formatBytes(capacity.total_used_bytes)}</div>
          </div>
          <div className="win-outset p-2 bg-[#f9fafb]">
            <div className="text-[#666666] font-semibold text-[10px]">OVERALL UTILIZATION</div>
            <div className="text-[16px] font-bold text-[#008000] font-mono">{capacity.overall_utilization_pct}%</div>
          </div>
        </div>
      )}

      {/* Repositories Table */}
      <div className="win-outset p-2 mb-2 bg-white flex flex-col">
        <div className="font-bold text-[11px] text-[#000080] mb-1">Configured Storage Repositories</div>
        <table className="w-full border-collapse text-left text-[11px]">
          <thead>
            <tr className="bg-[#000080] text-white">
              <th className="p-1 border border-[#808080]">Repository</th>
              <th className="p-1 border border-[#808080]">Path</th>
              <th className="p-1 border border-[#808080]">Capacity</th>
              <th className="p-1 border border-[#808080]">Used</th>
              <th className="p-1 border border-[#808080]">Free</th>
              <th className="p-1 border border-[#808080]">Utilization</th>
              <th className="p-1 border border-[#808080]">Actions</th>
            </tr>
          </thead>
          <tbody>
            {capacity?.repositories.map((r) => (
              <tr
                key={r.repository_id}
                onClick={() => setSelectedRepoId(r.repository_id)}
                className={`cursor-pointer border-b border-[#dfdfdf] ${
                  selectedRepoId === r.repository_id ? 'bg-[#cce5ff]' : 'hover:bg-[#f0f4f8]'
                }`}
              >
                <td className="p-1 font-bold text-[#000080]">{r.name}</td>
                <td className="p-1 font-mono text-[10px]">{r.path}</td>
                <td className="p-1 font-mono">{formatBytes(r.capacity_bytes)}</td>
                <td className="p-1 font-mono font-bold text-[#b91c1c]">{formatBytes(r.used_bytes)}</td>
                <td className="p-1 font-mono text-[#008000]">{formatBytes(r.free_bytes)}</td>
                <td className="p-1 font-mono">{r.utilization_pct}%</td>
                <td className="p-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleTakeSnapshot(r.repository_id);
                    }}
                    className="win-btn px-2 py-0.5 text-[10px]"
                  >
                    Take Snapshot
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Forecasting Section */}
      <div className="win-outset p-2 bg-[#f9fafb] flex-1 flex flex-col">
        <div className="flex justify-between items-center mb-2 pb-1 border-b border-[#a0a0a0]">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[12px] text-[#000080]">Storage Depletion Forecasting:</span>
            <span className="font-mono text-[11px] text-[#333333]">
              Repository #{selectedRepoId}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[#666666]">Data Window:</span>
            <select
              value={forecastWindow}
              onChange={(e) => setForecastWindow(Number(e.target.value))}
              className="win-inset px-1 py-0.5 text-[11px] bg-white"
            >
              <option value={7}>7 Days</option>
              <option value={30}>30 Days</option>
              <option value={90}>90 Days</option>
            </select>
          </div>
        </div>

        {forecastLoading ? (
          <div className="p-4 text-center text-[#666666]">Calculating linear regression projections...</div>
        ) : forecast?.status === 'INSUFFICIENT_DATA' ? (
          <div className="win-inset bg-[#fffbe6] p-3 text-[#333333] flex flex-col gap-1">
            <div className="font-bold text-[#b45309] text-[12px]">⚠️ INSUFFICIENT HISTORICAL DATA</div>
            <p className="text-[11px]">
              {forecast.message || 'At least 3 historical capacity snapshots are required to calculate transparent statistical growth projections.'}
            </p>
            <div className="text-[10px] text-[#666666] mt-1">
              Current sample count: <span className="font-mono font-bold">{forecast.sample_count}</span> snapshots. Click "Take Snapshot" above to establish baseline data points.
            </div>
          </div>
        ) : forecast?.status === 'PROJECTED' ? (
          <div className="flex flex-col gap-2">
            <div className="win-inset bg-[#ffffe6] p-2 text-[#b45309] text-[10px] font-bold">
              PROJECTION NOTICE: The following figures represent mathematical projections based on linear regression (R² = {forecast.confidence_r_squared}). They are not guaranteed depletion dates.
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="win-outset p-2 bg-white">
                <div className="text-[#666666] text-[10px]">DAILY BURN RATE</div>
                <div className="font-mono text-[14px] font-bold text-[#b91c1c]">
                  {formatBytes(forecast.daily_burn_rate_bytes)} / day
                </div>
              </div>
              <div className="win-outset p-2 bg-white">
                <div className="text-[#666666] text-[10px]">DAYS TO DEPLETION</div>
                <div className="font-mono text-[14px] font-bold text-[#000080]">
                  {forecast.days_to_depletion !== null ? `${forecast.days_to_depletion} days` : 'Stable (No Growth)'}
                </div>
              </div>
              <div className="win-outset p-2 bg-white">
                <div className="text-[#666666] text-[10px]">ESTIMATED DEPLETION DATE</div>
                <div className="font-mono text-[12px] font-bold text-[#333333]">
                  {forecast.estimated_depletion_date
                    ? forecast.estimated_depletion_date.substring(0, 10)
                    : 'N/A'}
                </div>
              </div>
            </div>

            {/* Projections Table */}
            <div className="win-outset p-2 bg-white">
              <div className="font-bold text-[11px] mb-1 text-[#000080]">Projected Repository Footprint:</div>
              <table className="w-full border-collapse text-left text-[11px]">
                <thead>
                  <tr className="bg-[#808080] text-white">
                    <th className="p-1 border border-[#dfdfdf]">Horizon</th>
                    <th className="p-1 border border-[#dfdfdf]">Projected Used Bytes</th>
                    <th className="p-1 border border-[#dfdfdf]">Method Used</th>
                    <th className="p-1 border border-[#dfdfdf]">Sample Count</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-[#dfdfdf]">
                    <td className="p-1 font-bold">+7 Days</td>
                    <td className="p-1 font-mono font-bold">{formatBytes(forecast.forecast_7d_bytes || 0)}</td>
                    <td className="p-1 font-mono">{forecast.method_used}</td>
                    <td className="p-1 font-mono">{forecast.sample_count}</td>
                  </tr>
                  <tr className="border-b border-[#dfdfdf]">
                    <td className="p-1 font-bold">+30 Days</td>
                    <td className="p-1 font-mono font-bold">{formatBytes(forecast.forecast_30d_bytes || 0)}</td>
                    <td className="p-1 font-mono">{forecast.method_used}</td>
                    <td className="p-1 font-mono">{forecast.sample_count}</td>
                  </tr>
                  <tr>
                    <td className="p-1 font-bold">+90 Days</td>
                    <td className="p-1 font-mono font-bold">{formatBytes(forecast.forecast_90d_bytes || 0)}</td>
                    <td className="p-1 font-mono">{forecast.method_used}</td>
                    <td className="p-1 font-mono">{forecast.sample_count}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="p-4 text-center text-[#666666]">Select a repository to view capacity projections.</div>
        )}
      </div>
    </div>
  );
};
