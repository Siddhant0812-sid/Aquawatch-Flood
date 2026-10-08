import type { ForecastResponse, SegmentResponse, StationSummary } from '../../api/client'

interface KpiMetricsRowProps {
  stationForecast: ForecastResponse | null
  selectedStation?: StationSummary
  segment: SegmentResponse | null
  basinRisk: string
  riskScoreDisplay: number
  stationsCount: number
  riskColor: (risk: string) => string
}

export default function KpiMetricsRow({
  stationForecast,
  selectedStation,
  segment,
  basinRisk,
  riskScoreDisplay,
  stationsCount,
  riskColor,
}: KpiMetricsRowProps) {
  return (
    <section className="metrics-kpi-row" aria-label="Key hydrological metrics">
      {/* Card 1: Water Level */}
      <div className="kpi-card">
        <div className="kpi-card-head">
          <span className="kpi-label">Water Level</span>
          <span className="kpi-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00b4d8" strokeWidth="2">
              <path d="M2 12h20M2 16h20M2 8h20" />
            </svg>
          </span>
        </div>
        <div className="kpi-main-val">
          <span className="val-number">{stationForecast ? stationForecast.current_level_m.toFixed(2) : '--'}</span>
          <span className="val-unit">m</span>
        </div>
        <div className="kpi-subtext">
          {stationForecast ? (
            stationForecast.current_level_m >= stationForecast.danger_level_m ? (
              <span className="sub-danger">▲ Above danger mark ({stationForecast.danger_level_m.toFixed(1)}m)</span>
            ) : (
              <span className="sub-normal">
                ▼ {(stationForecast.danger_level_m - stationForecast.current_level_m).toFixed(2)}m below danger
              </span>
            )
          ) : (
            <span>Station: {selectedStation?.name}</span>
          )}
        </div>
      </div>

      {/* Card 2: SAR Inundation Extent */}
      <div className="kpi-card">
        <div className="kpi-card-head">
          <span className="kpi-label">Flood Inundation Extent</span>
          <span className="kpi-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M8 12s1.5-2 4-2 4 2 4 2" />
            </svg>
          </span>
        </div>
        <div className="kpi-main-val">
          <span className="val-number">{segment?.coverage_pct ?? '8.9'}</span>
          <span className="val-unit">%</span>
        </div>
        <div className="kpi-subtext">
          <span className="sub-accent">ResNet-34 U-Net (10m SAR VV/VH)</span>
        </div>
      </div>

      {/* Card 3: Basin Flood Risk */}
      <div className="kpi-card">
        <div className="kpi-card-head">
          <span className="kpi-label">Basin Flood Risk</span>
          <span className="kpi-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={riskColor(basinRisk)} strokeWidth="2">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </span>
        </div>
        <div className="kpi-main-val">
          <span className="val-text" style={{ color: riskColor(basinRisk) }}>
            {basinRisk}
          </span>
        </div>
        <div className="kpi-subtext">
          <span>Risk Score: <strong>{riskScoreDisplay} / 100</strong></span>
        </div>
      </div>

      {/* Card 4: River Gauges */}
      <div className="kpi-card">
        <div className="kpi-card-head">
          <span className="kpi-label">Monitored Gauges</span>
          <span className="kpi-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
          </span>
        </div>
        <div className="kpi-main-val">
          <span className="val-number">{stationsCount}</span>
          <span className="val-unit">Active</span>
        </div>
        <div className="kpi-subtext">
          <span>Brahmaputra River Corridor</span>
        </div>
      </div>

      {/* Card 5: Forecasting Lead Horizons */}
      <div className="kpi-card">
        <div className="kpi-card-head">
          <span className="kpi-label">AI Forecast Horizons</span>
          <span className="kpi-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a855f7" strokeWidth="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </span>
        </div>
        <div className="kpi-main-val">
          <span className="val-text val-purple">24 · 48 · 72h</span>
        </div>
        <div className="kpi-subtext">
          <span>Stacked LSTM (48h MAE: 0.22m)</span>
        </div>
      </div>
    </section>
  )
}

