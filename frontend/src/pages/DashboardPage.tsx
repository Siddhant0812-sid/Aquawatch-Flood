import { useCallback, useEffect, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Popup, TileLayer } from 'react-leaflet'
import { useNavigate } from 'react-router-dom'
import { fetchSegment, fetchStations } from '../api/client'
import type { SegmentResponse, StationSummary } from '../api/client'

const ASSAM_CENTER: [number, number] = [26.5, 92.5]

function riskColor(risk: string): string {
  if (risk === 'LOW') return '#16a34a'
  if (risk === 'MODERATE') return '#d97706'
  if (risk === 'HIGH') return '#dc2626'
  return '#64748b'
}

function overallRisk(stations: StationSummary[]): string {
  if (stations.some((station) => station.current_risk_level === 'HIGH')) return 'HIGH'
  if (stations.some((station) => station.current_risk_level === 'MODERATE')) return 'MODERATE'
  return 'LOW'
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [stations, setStations] = useState<StationSummary[]>([])
  const [segment, setSegment] = useState<SegmentResponse | null>(null)
  const [selectedDate, setSelectedDate] = useState(today)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [activePlotTab, setActivePlotTab] = useState<'comparison' | 'attention' | 'backtest'>('comparison')

  const loadDashboard = useCallback(() => {
    let active = true
    setLoading(true)
    setRefreshing(true)
    setError(null)
    Promise.all([fetchStations(), fetchSegment(selectedDate)])
      .then(([stationResponse, segmentResponse]) => {
        if (!active) return
        setStations(stationResponse.stations)
        setSegment(segmentResponse)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Unable to load dashboard')
      })
      .finally(() => {
        if (active) {
          setLoading(false)
          setRefreshing(false)
        }
      })
    return () => {
      active = false
    }
  }, [selectedDate])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  if (loading) return <div className="loading">Loading dashboard&hellip;</div>
  if (error) return <div className="error-state">Failed to load dashboard: {error}</div>

  const basinRisk = overallRisk(stations)

  return (
    <div className="dashboard-wrapper">
      <div className="dashboard">
        <section className="map-panel" aria-label="Flood extent map">
          <div className="date-control">
            <label htmlFor="segment-date">Imagery date</label>
            <input
              id="segment-date"
              type="date"
              value={selectedDate}
              onChange={(event) => setSelectedDate(event.target.value)}
            />
            {segment && (
              <span className="imagery-note">
                Acquisition: {segment.imagery_acquisition_date} &middot; Coverage: {segment.coverage_pct}% &middot; Sentinel-1 SAR Dual-Pol
              </span>
            )}
            <button className="btn btn-secondary" type="button" onClick={loadDashboard} disabled={refreshing}>
              {refreshing ? 'Refreshing\u2026' : 'Refresh'}
            </button>
          </div>
          <div className="map-container">
            <MapContainer center={ASSAM_CENTER} zoom={7} scrollWheelZoom>
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {segment && (
                <GeoJSON
                  data={segment.mask_geojson}
                  style={{ fillColor: '#2563eb', fillOpacity: 0.35, color: '#1d4ed8', weight: 1.5 }}
                />
              )}
              {stations.map((station) => (
                <CircleMarker
                  key={station.station_id}
                  center={[station.lat, station.lon]}
                  radius={9}
                  pathOptions={{
                    fillColor: riskColor(station.current_risk_level),
                    fillOpacity: 0.9,
                    color: '#fff',
                    weight: 2,
                  }}
                  eventHandlers={{ click: () => navigate(`/station/${station.station_id}`) }}
                >
                  <Popup>
                    <strong>{station.name}</strong>
                    <br />
                    River: {station.river}
                    <br />
                    Risk Level: {station.current_risk_level}
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>
        </section>

        <aside className="sidebar">
          <div className="risk-summary">
            <strong>Overall basin risk</strong>
            <span className={`risk-badge ${basinRisk.toLowerCase()}`}>
              <span className="dot" />
              {basinRisk}
            </span>
          </div>
          <section className="card">
            <h2>Monitoring stations</h2>
            <ul className="station-list">
              {stations.map((station) => (
                <li
                  key={station.station_id}
                  className="station-item"
                  onClick={() => navigate(`/station/${station.station_id}`)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') navigate(`/station/${station.station_id}`)
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <div>
                    <h3>{station.name}</h3>
                    <p>{station.river}</p>
                  </div>
                  <span className={`risk-badge ${station.current_risk_level.toLowerCase()}`}>
                    <span className="dot" />
                    {station.current_risk_level}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      {/* AI Model Outputs & Evaluation Section Directly On Dashboard */}
      <section className="card dashboard-models-section">
        <div className="section-header">
          <span className="source-tag">AI Model Outputs</span>
          <h2>Integrated Model Results &amp; Visual Explainability</h2>
        </div>
        <p className="description">
          Outputs produced by <strong>Member 1 (SAR U-Net Segmentation)</strong> and{' '}
          <strong>Member 2 (Multi-Horizon Hydrological Forecasting)</strong>:
        </p>

        <div className="models-overview-grid">
          <div className="model-summary-box">
            <h3>Member 1: SAR Flood Segmentation (U-Net)</h3>
            <p>
              Deep learning binary surface water segmentation running on Sentinel-1 SAR Dual-Pol (VV/VH) imagery.
            </p>
            <div className="mini-stats">
              <div className="mini-stat">
                <span className="stat-num">ResNet-34</span>
                <span className="stat-desc">Encoder Backbone</span>
              </div>
              <div className="mini-stat">
                <span className="stat-num">10m</span>
                <span className="stat-desc">Resolution</span>
              </div>
              <div className="mini-stat">
                <span className="stat-num">{segment ? `${segment.coverage_pct}%` : 'N/A'}</span>
                <span className="stat-desc">Inundated Area</span>
              </div>
            </div>
          </div>

          <div className="model-summary-box">
            <h3>Member 2: Multi-Horizon Forecasting (LSTM)</h3>
            <p>
              Stacked 2-layer LSTM trained on 72-hour historical water levels, rolling rainfall, rate of rise, and soil moisture.
            </p>
            <div className="mini-stats">
              <div className="mini-stat">
                <span className="stat-num">24h / 48h / 72h</span>
                <span className="stat-desc">Lead Horizons</span>
              </div>
              <div className="mini-stat">
                <span className="stat-num">60</span>
                <span className="stat-desc">Input Features</span>
              </div>
              <div className="mini-stat">
                <span className="stat-num">0.22m</span>
                <span className="stat-desc">48h MAE</span>
              </div>
            </div>
          </div>
        </div>

        {/* Explainability & Artifact Viewer directly on dashboard */}
        <div className="artifact-viewer">
          <h3>Member 2 Training Artifacts &amp; Visual Plots</h3>
          <div className="tab-buttons">
            <button
              type="button"
              className={`tab-btn ${activePlotTab === 'comparison' ? 'active' : ''}`}
              onClick={() => setActivePlotTab('comparison')}
            >
              Model Comparison Chart
            </button>
            <button
              type="button"
              className={`tab-btn ${activePlotTab === 'attention' ? 'active' : ''}`}
              onClick={() => setActivePlotTab('attention')}
            >
              Temporal Attention Weights
            </button>
            <button
              type="button"
              className={`tab-btn ${activePlotTab === 'backtest' ? 'active' : ''}`}
              onClick={() => setActivePlotTab('backtest')}
            >
              2022 Monsoon Backtest
            </button>
          </div>

          <div className="plot-display">
            {activePlotTab === 'comparison' && (
              <div className="plot-container">
                <img
                  src="/outputs/explainability/model_comparison.png"
                  alt="Model Comparison (ARIMA vs LSTM vs TFT-Lite)"
                  className="eval-img"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
                <p className="caption">
                  <strong>Model Comparison:</strong> Evaluates MAE and RMSE across 24h, 48h, and 72h horizons. The
                  LSTM model achieves balanced accuracy across operational flood lead times.
                </p>
              </div>
            )}

            {activePlotTab === 'attention' && (
              <div className="plot-container">
                <img
                  src="/outputs/explainability/attention_lstm.png"
                  alt="LSTM Temporal Attention Weights"
                  className="eval-img"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
                <p className="caption">
                  <strong>Temporal Attention Weights:</strong> Highlights which past hours across the 72-hour sliding
                  window had highest influence. Weight clusters around past 24h&ndash;48h rainfall bursts.
                </p>
              </div>
            )}

            {activePlotTab === 'backtest' && (
              <div className="plot-container">
                <img
                  src="/outputs/explainability/backtest_NH15 Crossing Dhansirighat_2022.png"
                  alt="2022 Historical Monsoon Backtest"
                  className="eval-img"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
                <p className="caption">
                  <strong>Historical Backtest (2022 Assam Monsoon):</strong> Evaluates forecast predictions against the
                  historic 2022 flood crest, verifying 48 hours of advance warning prior to breaching danger levels.
                </p>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
