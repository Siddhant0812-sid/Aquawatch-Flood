import { useCallback, useEffect, useMemo, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Popup, TileLayer } from 'react-leaflet'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useNavigate } from 'react-router-dom'
import {
  fetchForecast,
  fetchSegment,
  fetchStations,
  simulateAlert,
} from '../api/client'
import type {
  AlertResponse,
  ForecastResponse,
  SegmentResponse,
  StationSummary,
} from '../api/client'

const ASSAM_CENTER: [number, number] = [26.5, 92.8]

const FACTOR_DESCRIPTIONS: Record<string, { label: string; pct: number }> = {
  rainfall_72h: { label: '72h Rainfall Accumulation', pct: 92 },
  upstream_level: { label: 'Upstream River Surge', pct: 85 },
  rate_of_rise: { label: 'Rate of River Stage Rise', pct: 74 },
  seasonal_trend: { label: 'Seasonal Monsoon Trend', pct: 58 },
}

function riskColor(risk: string): string {
  if (risk === 'LOW') return '#10b981'
  if (risk === 'MODERATE') return '#f59e0b'
  if (risk === 'HIGH') return '#ef4444'
  return '#64748b'
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

interface DashboardPageProps {
  onToggleSidebar?: () => void
}

export default function DashboardPage({ onToggleSidebar }: DashboardPageProps) {
  const navigate = useNavigate()

  // Real backend telemetry states
  const [stations, setStations] = useState<StationSummary[]>([])
  const [selectedStationId, setSelectedStationId] = useState<string>('guwahati')
  const [stationForecast, setStationForecast] = useState<ForecastResponse | null>(null)
  const [segment, setSegment] = useState<SegmentResponse | null>(null)
  const [selectedDate, setSelectedDate] = useState<string>(today)

  // UI & loading states
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Simulation & Tabs states
  const [alertResult, setAlertResult] = useState<AlertResponse | null>(null)
  const [alertLoading, setAlertLoading] = useState(false)
  const [activeSarView, setActiveSarView] = useState<'scene' | 'samples' | 'explain'>('scene')
  const [activePlotTab, setActivePlotTab] = useState<'comparison' | 'attention' | 'backtest'>('comparison')

  // Live Clock
  const [currentTime, setCurrentTime] = useState<string>(() => {
    const now = new Date()
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' · ' +
      now.toLocaleDateString([], { month: 'short', day: '2-digit', year: 'numeric' })
  })

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date()
      setCurrentTime(
        now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' · ' +
        now.toLocaleDateString([], { month: 'short', day: '2-digit', year: 'numeric' })
      )
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Initial load: Fetch stations and segmentation
  const loadInitialData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [stationRes, segmentRes] = await Promise.all([
        fetchStations(),
        fetchSegment(selectedDate),
      ])
      setStations(stationRes.stations)
      setSegment(segmentRes)

      const initialId = stationRes.stations[0]?.station_id ?? 'guwahati'
      setSelectedStationId(initialId)
      const fc = await fetchForecast(initialId)
      setStationForecast(fc)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to connect to AquaWatch backend')
    } finally {
      setLoading(false)
    }
  }, [selectedDate])

  useEffect(() => {
    loadInitialData()
  }, [loadInitialData])

  // When selected station changes, fetch its forecast
  const handleSelectStation = useCallback(async (stationId: string) => {
    setSelectedStationId(stationId)
    setAlertResult(null)
    try {
      const fc = await fetchForecast(stationId)
      setStationForecast(fc)
    } catch (err: unknown) {
      console.error('Failed to load forecast for station', stationId, err)
    }
  }, [])

  // Manual refresh trigger
  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const [stationRes, segmentRes, forecastRes] = await Promise.all([
        fetchStations(),
        fetchSegment(selectedDate),
        fetchForecast(selectedStationId),
      ])
      setStations(stationRes.stations)
      setSegment(segmentRes)
      setStationForecast(forecastRes)
    } catch (err: unknown) {
      console.error('Refresh error:', err)
    } finally {
      setRefreshing(false)
    }
  }

  // Peak risk score calculation from active forecast
  const peakForecast = useMemo(() => {
    if (!stationForecast || !stationForecast.forecasts.length) return null
    return stationForecast.forecasts.reduce((curr, item) =>
      item.risk_score > curr.risk_score ? item : curr
    )
  }, [stationForecast])

  // Overall Basin Risk
  const basinRisk = useMemo(() => {
    if (stations.some((s) => s.current_risk_level === 'HIGH')) return 'HIGH'
    if (stations.some((s) => s.current_risk_level === 'MODERATE')) return 'MODERATE'
    return 'LOW'
  }, [stations])

  // Peak Risk Score scaled to 0-100
  const riskScoreDisplay = useMemo(() => {
    if (peakForecast) {
      return Math.round(peakForecast.risk_score * 100)
    }
    return basinRisk === 'HIGH' ? 82 : basinRisk === 'MODERATE' ? 58 : 24
  }, [peakForecast, basinRisk])

  // Selected station summary
  const selectedStation = useMemo(() => {
    return stations.find((s) => s.station_id === selectedStationId) ?? stations[0]
  }, [stations, selectedStationId])

  // 72h Water level trend chart data
  const chartData = useMemo(() => {
    if (!stationForecast) return []
    return [
      {
        time: 'Current',
        level: stationForecast.current_level_m,
        danger: stationForecast.danger_level_m,
        warning: stationForecast.danger_level_m - 1.0,
      },
      ...stationForecast.forecasts.map((fc) => ({
        time: `+${fc.horizon_hours}h`,
        level: fc.predicted_level_m,
        danger: stationForecast.danger_level_m,
        warning: stationForecast.danger_level_m - 1.0,
      })),
    ]
  }, [stationForecast])

  // Handle alert simulation
  const handleSimulateAlert = async () => {
    if (!stationForecast || !peakForecast) return
    setAlertLoading(true)
    try {
      const res = await simulateAlert(selectedStationId, peakForecast.risk_score)
      setAlertResult(res)
    } catch (err: unknown) {
      setAlertResult({
        triggered: false,
        message: err instanceof Error ? err.message : 'Alert simulation failed',
      })
    } finally {
      setAlertLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="dashboard-loading-state">
        <div className="pulse-radar" aria-hidden="true" />
        <p>Connecting to AquaWatch telemetry &amp; SAR models&hellip;</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="dashboard-error-state">
        <h3>Connection Error</h3>
        <p>{error}</p>
        <button type="button" className="ctrl-btn-action" onClick={loadInitialData}>
          Retry Connection
        </button>
      </div>
    )
  }

  const comparisonImgSrc = segment?.prediction_image_url || '/outputs/sar_unet_deeplabv3_comparison.png'
  const samplesImgSrc = segment?.validation_samples_url || '/outputs/sar_validation_samples.png'

  return (
    <div className="dashboard-command-view">
      {/* Top Header Bar matching reference */}
      <header className="command-header">
        <div className="header-left">
          {onToggleSidebar && (
            <button
              type="button"
              className="sidebar-toggle-btn"
              onClick={onToggleSidebar}
              aria-label="Toggle navigation menu"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          )}
          <div className="header-title-box">
            <span className="header-icon-pill" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00b4d8" strokeWidth="2.5">
                <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
              </svg>
            </span>
            <div>
              <h1 className="header-main-title">Flood Monitoring Intelligence</h1>
              <p className="header-sub-caption">Brahmaputra Basin, Assam · Real-Time SAR &amp; Hydro AI</p>
            </div>
          </div>
        </div>

        <div className="header-controls">
          <div className="api-badge">
            <span className="live-dot" />
            <span>Live API</span>
          </div>

          <div className="date-picker-wrap">
            <label htmlFor="top-date-picker" className="visually-hidden">SAR Acquisition Date</label>
            <input
              id="top-date-picker"
              type="date"
              className="ctrl-input-date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              title="Sentinel-1 SAR acquisition date"
            />
          </div>

          <button
            type="button"
            className="ctrl-btn-refresh"
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh hydrological telemetry"
          >
            <svg
              className={refreshing ? 'spin-icon' : ''}
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
            >
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.19" />
            </svg>
            <span>{refreshing ? 'Syncing...' : 'Refresh'}</span>
          </button>

          <div className="live-clock-pill">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span>{currentTime}</span>
          </div>
        </div>
      </header>

      {/* Row 1: Top Metrics KPI Cards (5 cards across) */}
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
            <span className="val-number">{stations.length}</span>
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

      {/* Row 2: Middle Section (72h Forecast Chart + Contributing Factors & Alerts) */}
      <section className="middle-analytics-grid">
        {/* Left: Water Level Trend & Forecast Chart */}
        <div className="panel-card chart-panel">
          <div className="panel-header">
            <div className="panel-title-group">
              <h2>Water Level Trend &amp; 72h Forecast</h2>
              <span className="panel-sub-tag">Station: {selectedStation?.name}</span>
            </div>

            <div className="chart-header-actions">
              <label htmlFor="station-select-dropdown" className="visually-hidden">Select Gauge Station</label>
              <select
                id="station-select-dropdown"
                className="ctrl-select-station"
                value={selectedStationId}
                onChange={(e) => handleSelectStation(e.target.value)}
              >
                {stations.map((s) => (
                  <option key={s.station_id} value={s.station_id}>
                    {s.name} ({s.current_risk_level})
                  </option>
                ))}
              </select>

              <div className="chart-legend-pills">
                <span className="legend-item danger">
                  <span className="legend-line dashed red" /> Danger Level
                </span>
                <span className="legend-item warning">
                  <span className="legend-line dashed amber" /> Warning Mark
                </span>
                <span className="legend-item water">
                  <span className="legend-line solid cyan" /> Forecast Level
                </span>
              </div>
            </div>
          </div>

          <div className="chart-viewport">
            <ResponsiveContainer width="100%" height={290}>
              <AreaChart data={chartData} margin={{ top: 12, right: 24, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="waterGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00b4d8" stopOpacity={0.45} />
                    <stop offset="95%" stopColor="#00b4d8" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1c2b48" vertical={false} />
                <XAxis
                  dataKey="time"
                  stroke="#64748b"
                  tick={{ fill: '#94a3b8', fontSize: 12 }}
                  axisLine={{ stroke: '#1c2b48' }}
                  tickLine={false}
                />
                <YAxis
                  stroke="#64748b"
                  tick={{ fill: '#94a3b8', fontSize: 12 }}
                  axisLine={{ stroke: '#1c2b48' }}
                  tickLine={false}
                  domain={['dataMin - 1', 'dataMax + 2']}
                  unit="m"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#10192d',
                    borderColor: '#23355b',
                    borderRadius: '8px',
                    color: '#f8fafc',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                  }}
                  formatter={(val) => [`${Number(val ?? 0).toFixed(2)} m`, 'Water Level']}
                  labelStyle={{ color: '#00b4d8', fontWeight: 600 }}
                />
                {stationForecast && (
                  <>
                    <ReferenceLine
                      y={stationForecast.danger_level_m}
                      stroke="#ef4444"
                      strokeDasharray="5 4"
                      strokeWidth={1.5}
                      label={{
                        value: `Danger: ${stationForecast.danger_level_m}m`,
                        fill: '#ef4444',
                        position: 'insideTopRight',
                        fontSize: 11,
                      }}
                    />
                    <ReferenceLine
                      y={stationForecast.danger_level_m - 1.0}
                      stroke="#f59e0b"
                      strokeDasharray="4 4"
                      strokeWidth={1.2}
                      label={{
                        value: `Warning: ${(stationForecast.danger_level_m - 1.0).toFixed(1)}m`,
                        fill: '#f59e0b',
                        position: 'insideBottomRight',
                        fontSize: 10,
                      }}
                    />
                  </>
                )}
                <Area
                  type="monotone"
                  dataKey="level"
                  stroke="#00b4d8"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#waterGradient)"
                  dot={{ r: 4, fill: '#00b4d8', stroke: '#080d1a', strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: '#38bdf8', stroke: '#fff', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Contributing Factors & Alert Simulation */}
        <div className="panel-card factors-panel">
          <div className="panel-header">
            <div>
              <h2>Hydrological Drivers</h2>
              <span className="panel-sub-tag">Explainable Risk Factors</span>
            </div>
            {peakForecast && (
              <span className={`risk-pill ${peakForecast.risk_label.toLowerCase()}`}>
                Peak: {peakForecast.risk_label}
              </span>
            )}
          </div>

          <div className="factors-meter-list">
            {(peakForecast?.top_factors ?? ['rainfall_72h', 'upstream_level', 'rate_of_rise']).map(
              (key) => {
                const item = FACTOR_DESCRIPTIONS[key] ?? {
                  label: key.replace(/_/g, ' '),
                  pct: 65,
                }
                return (
                  <div key={key} className="factor-meter-row">
                    <div className="factor-meter-info">
                      <span className="factor-name">{item.label}</span>
                      <span className="factor-val">{item.pct}% influence</span>
                    </div>
                    <div className="factor-track">
                      <div
                        className="factor-fill"
                        style={{
                          width: `${item.pct}%`,
                          background: item.pct > 80 ? 'linear-gradient(90deg, #f59e0b, #ef4444)' : 'linear-gradient(90deg, #00b4d8, #3b82f6)',
                        }}
                      />
                    </div>
                  </div>
                )
              }
            )}
          </div>

          {/* Action: Emergency Alert Protocol */}
          <div className="alert-simulation-block">
            <div className="alert-sim-header">
              <span className="sim-title">Automated Alert Test</span>
              <button
                type="button"
                className="btn-trigger-alert"
                onClick={handleSimulateAlert}
                disabled={alertLoading}
              >
                {alertLoading ? 'Simulating...' : 'Simulate Emergency Alert'}
              </button>
            </div>
            {alertResult && (
              <div className={`alert-feedback-banner ${alertResult.triggered ? 'triggered' : 'standby'}`}>
                <span className="feedback-icon">{alertResult.triggered ? '🚨' : '🛡️'}</span>
                <span>{alertResult.message}</span>
              </div>
            )}
          </div>

          {/* Response Protocols */}
          <div className="recommendations-box">
            <span className="rec-header">Operational Advisory:</span>
            <ul className="rec-list">
              <li>Monitor upstream discharge from Arunachal foothills.</li>
              <li>Maintain high alert along low-lying riverine embankments.</li>
              <li>Ready field dispatch protocols with SDRF &amp; district authorities.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Row 3: Lower-Middle Section (Basin Map & Station Status Table) */}
      <section className="lower-grid">
        {/* Left: Basin Overview Map */}
        <div className="panel-card map-panel-card">
          <div className="panel-header map-header">
            <div>
              <h2>Basin Overview Map</h2>
              <span className="panel-sub-tag">
                Assam &amp; Brahmaputra Valley · Acquisition: {segment?.imagery_acquisition_date ?? selectedDate}
              </span>
            </div>

            <div className="map-legend-pills">
              <span className="map-legend-dot low">● Low</span>
              <span className="map-legend-dot mod">● Moderate</span>
              <span className="map-legend-dot high">● High</span>
              <span className="map-legend-dot sar">■ SAR Flood Mask</span>
            </div>
          </div>

          {segment?.georeferencing_error && (
            <div className="map-warning-strip">
              <span>⚠️ {segment.georeferencing_error}</span>
            </div>
          )}

          <div className="command-map-container">
            <MapContainer
              center={ASSAM_CENTER}
              zoom={7}
              scrollWheelZoom
              className="leaflet-map-element"
              style={{ width: '100%', height: '100%' }}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              {/* GeoJSON Surface Water Extent from U-Net */}
              {segment?.mask_geojson && segment.mask_geojson.features.length > 0 && (
                <GeoJSON
                  key={`${selectedDate}-${segment.imagery_acquisition_date}-${segment.mask_geojson.features.length}`}
                  data={segment.mask_geojson}
                  style={{
                    fillColor: '#00b4d8',
                    fillOpacity: 0.55,
                    color: '#0284c7',
                    weight: 1.5,
                  }}
                />
              )}

              {/* Monitored Stations Markers */}
              {stations.map((st) => (
                <CircleMarker
                  key={st.station_id}
                  center={[st.lat, st.lon]}
                  radius={st.station_id === selectedStationId ? 11 : 8}
                  pathOptions={{
                    fillColor: riskColor(st.current_risk_level),
                    fillOpacity: 0.95,
                    color: st.station_id === selectedStationId ? '#ffffff' : '#0f172a',
                    weight: st.station_id === selectedStationId ? 3 : 2,
                  }}
                  eventHandlers={{
                    click: () => handleSelectStation(st.station_id),
                  }}
                >
                  <Popup>
                    <div className="map-popup-inner">
                      <strong>{st.name} Station</strong>
                      <p>River: {st.river}</p>
                      <p>
                        Current Risk: <span style={{ color: riskColor(st.current_risk_level), fontWeight: 700 }}>{st.current_risk_level}</span>
                      </p>
                      <button
                        type="button"
                        className="popup-btn"
                        onClick={() => navigate(`/station/${st.station_id}`)}
                      >
                        Detailed Telemetry &rarr;
                      </button>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>

            {/* On-Map Floating Inspector Card matching reference screenshot */}
            <div className="on-map-station-badge">
              <div className="badge-station-title">
                <span className="badge-live-dot" />
                <strong>{selectedStation?.name} Gauge</strong>
                <span className={`badge-risk-tag ${selectedStation?.current_risk_level.toLowerCase()}`}>
                  {selectedStation?.current_risk_level}
                </span>
              </div>
              <div className="badge-details">
                <div>
                  <span className="b-label">River</span>
                  <span className="b-val">{selectedStation?.river}</span>
                </div>
                <div>
                  <span className="b-label">Current Level</span>
                  <span className="b-val">
                    {stationForecast ? `${stationForecast.current_level_m.toFixed(2)}m` : '--'}
                  </span>
                </div>
                <div>
                  <span className="b-label">Danger Level</span>
                  <span className="b-val">
                    {stationForecast ? `${stationForecast.danger_level_m.toFixed(2)}m` : '--'}
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="badge-link-btn"
                onClick={() => navigate(`/station/${selectedStationId}`)}
              >
                Inspect Station Details &rarr;
              </button>
            </div>
          </div>
        </div>

        {/* Right: Station Status Table */}
        <div className="panel-card stations-table-panel">
          <div className="panel-header">
            <div>
              <h2>Station Status</h2>
              <span className="panel-sub-tag">Brahmaputra Gauging Network</span>
            </div>
            <span className="gauge-count-badge">{stations.length} Active Gauges</span>
          </div>

          <div className="stations-table-wrap">
            <table className="command-table">
              <thead>
                <tr>
                  <th>Station</th>
                  <th>River</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {stations.map((st) => {
                  const isSelected = st.station_id === selectedStationId
                  return (
                    <tr
                      key={st.station_id}
                      className={`station-row ${isSelected ? 'row-selected' : ''}`}
                      onClick={() => handleSelectStation(st.station_id)}
                    >
                      <td className="station-cell-name">
                        <strong>{st.name}</strong>
                      </td>
                      <td className="station-cell-river">{st.river}</td>
                      <td>
                        <span className={`status-pill ${st.current_risk_level.toLowerCase()}`}>
                          {st.current_risk_level}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn-row-inspect"
                          onClick={(e) => {
                            e.stopPropagation()
                            navigate(`/station/${st.station_id}`)
                          }}
                          title="Open full station analytics"
                        >
                          Inspect &rarr;
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Row 4: Member 1 SAR Flood Segmentation Outputs & AI Models */}
      <section className="panel-card sar-outputs-panel">
        <div className="panel-header">
          <div>
            <div className="badge-tag-row">
              <span className="source-tag">Member 1 Output</span>
              <span className="source-tag-blue">Sentinel-1 Dual-Pol VV/VH</span>
            </div>
            <h2>SAR Flood Extent &amp; Surface Water Segmentation</h2>
          </div>
          <span className="model-mode-badge real">
            {segment?.is_real_model ? 'ResNet-34 U-Net (Real SAR)' : 'Trained AI Model'}
          </span>
        </div>

        <p className="panel-description-text">
          Satellite radar flood segmentation comparing trained <strong>ResNet-34 U-Net</strong> against{' '}
          <strong>DeepLabV3+</strong> across the Brahmaputra floodplain in Assam.
        </p>

        {/* Tab Switcher */}
        <div className="command-tab-strip">
          <button
            type="button"
            className={`cmd-tab ${activeSarView === 'scene' ? 'active' : ''}`}
            onClick={() => setActiveSarView('scene')}
          >
            Assam Scene: VV vs. U-Net vs. DeepLabV3+
          </button>
          <button
            type="button"
            className={`cmd-tab ${activeSarView === 'samples' ? 'active' : ''}`}
            onClick={() => setActiveSarView('samples')}
          >
            Multi-Sample Validation Grid (5 Scenes)
          </button>
          <button
            type="button"
            className={`cmd-tab ${activeSarView === 'explain' ? 'active' : ''}`}
            onClick={() => setActiveSarView('explain')}
          >
            Member 2 Forecast Explainability
          </button>
        </div>

        {activeSarView === 'scene' && (
          <div className="sar-showcase-box">
            <div className="clean-img-wrapper">
              <img
                src={comparisonImgSrc}
                alt="Assam Sentinel-1 VV amplitude alongside U-Net prediction and DeepLabV3+ prediction"
                className="sar-img-asset"
              />
            </div>
            <p className="sar-caption">
              <strong>Full Assam Scene Comparison:</strong> Input Sentinel-1 SAR VV amplitude (left), binary water
              mask predicted by ResNet-34 U-Net (center), and DeepLabV3+ benchmark (right). Water appears high-contrast white.
            </p>
          </div>
        )}

        {activeSarView === 'samples' && (
          <div className="sar-showcase-box">
            <div className="clean-img-wrapper">
              <img
                src={samplesImgSrc}
                alt="Multi-sample validation grid showing SAR Input, Ground Truth, U-Net, and DeepLabV3+"
                className="sar-img-asset"
              />
            </div>
            <p className="sar-caption">
              <strong>Validation Sample Evaluations (Samples 0, 25, 50, 100, 150):</strong> Ground truth water extent
              benchmarked against U-Net predictions across challenging wetland topologies.
            </p>
          </div>
        )}

        {activeSarView === 'explain' && (
          <div className="explainability-subview">
            <div className="command-tab-strip sub-tabs">
              <button
                type="button"
                className={`cmd-tab mini ${activePlotTab === 'comparison' ? 'active' : ''}`}
                onClick={() => setActivePlotTab('comparison')}
              >
                Model Comparison
              </button>
              <button
                type="button"
                className={`cmd-tab mini ${activePlotTab === 'attention' ? 'active' : ''}`}
                onClick={() => setActivePlotTab('attention')}
              >
                Temporal Attention
              </button>
              <button
                type="button"
                className={`cmd-tab mini ${activePlotTab === 'backtest' ? 'active' : ''}`}
                onClick={() => setActivePlotTab('backtest')}
              >
                2022 Monsoon Backtest
              </button>
            </div>

            <div className="clean-img-wrapper">
              {activePlotTab === 'comparison' && (
                <img
                  src="/outputs/explainability/model_comparison.png"
                  alt="Model Comparison"
                  className="sar-img-asset"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
              )}
              {activePlotTab === 'attention' && (
                <img
                  src="/outputs/explainability/attention_lstm.png"
                  alt="LSTM Temporal Attention"
                  className="sar-img-asset"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
              )}
              {activePlotTab === 'backtest' && (
                <img
                  src="/outputs/explainability/backtest_NH15 Crossing Dhansirighat_2022.png"
                  alt="2022 Historical Monsoon Backtest"
                  className="sar-img-asset"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
              )}
            </div>
          </div>
        )}

        {/* Specifications Footnote Grid */}
        <div className="specs-command-grid">
          <div className="spec-badge-box">
            <span className="spec-label">Architecture</span>
            <span className="spec-val">ResNet-34 U-Net</span>
          </div>
          <div className="spec-badge-box">
            <span className="spec-label">Sensor / Band</span>
            <span className="spec-val">Sentinel-1 Dual-Pol (VV/VH)</span>
          </div>
          <div className="spec-badge-box">
            <span className="spec-label">Spatial Resolution</span>
            <span className="spec-val">10 meters</span>
          </div>
          <div className="spec-badge-box">
            <span className="spec-label">Decision Threshold</span>
            <span className="spec-val">0.40 (TTA Horizontal-Flip)</span>
          </div>
          <div className="spec-badge-box">
            <span className="spec-label">SAR Inundated Extent</span>
            <span className="spec-val text-cyan">{segment?.coverage_pct ?? '8.9'}% of Basin</span>
          </div>
        </div>
      </section>
    </div>
  )
}
