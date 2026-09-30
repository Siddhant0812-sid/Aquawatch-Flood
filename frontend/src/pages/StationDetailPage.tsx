import { useEffect, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchForecast, simulateAlert } from '../api/client'
import type { AlertResponse, ForecastResponse } from '../api/client'

const FACTOR_LABELS: Record<string, string> = {
  rainfall_72h: '72-hour rainfall',
  upstream_level: 'Upstream water level',
  rate_of_rise: 'Rate of rise',
  seasonal_trend: 'Seasonal trend',
}

export default function StationDetailPage() {
  const { stationId } = useParams<{ stationId: string }>()
  const navigate = useNavigate()
  const [forecast, setForecast] = useState<ForecastResponse | null>(null)
  const [alert, setAlert] = useState<AlertResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [alertLoading, setAlertLoading] = useState(false)

  useEffect(() => {
    if (!stationId) {
      setError('Station ID is missing')
      setLoading(false)
      return
    }

    let active = true
    setLoading(true)
    setError(null)
    fetchForecast(stationId)
      .then((result) => {
        if (active) setForecast(result)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Unable to load forecast')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [stationId])

  if (loading) return <div className="loading">Loading station forecast…</div>
  if (error || !forecast) {
    return <div className="error-state">Failed to load station: {error ?? 'Station not found'}</div>
  }

  const peak = forecast.forecasts.reduce((current, item) =>
    item.risk_score > current.risk_score ? item : current,
  )
  const chartData = [
    { hour: 'Now', level: forecast.current_level_m },
    ...forecast.forecasts.map((item) => ({
      hour: `${item.horizon_hours}h`,
      level: item.predicted_level_m,
    })),
  ]

  async function handleAlert() {
    if (!stationId) return
    setAlertLoading(true)
    try {
      setAlert(await simulateAlert(stationId, peak.risk_score))
    } catch (reason: unknown) {
      setAlert({
        triggered: false,
        message: reason instanceof Error ? reason.message : 'Unable to simulate alert',
      })
    } finally {
      setAlertLoading(false)
    }
  }

  return (
    <div className="station-detail">
      <button className="back-link" type="button" onClick={() => navigate('/')}>
        ← Back to dashboard
      </button>

      <div className="station-header">
        <div>
          <h1>{forecast.station_name} station</h1>
          <p className="meta">River: Brahmaputra</p>
        </div>
        <span className={`risk-badge ${peak.risk_label.toLowerCase()}`}>
          <span className="dot" />
          Peak risk: {peak.risk_label}
        </span>
      </div>

      <section className="card level-info">
        <div className="stat">
          <span className="label">Current level</span>
          <span className="value">{forecast.current_level_m.toFixed(2)} m</span>
        </div>
        <div className="stat">
          <span className="label">Danger level</span>
          <span className="value danger">{forecast.danger_level_m.toFixed(2)} m</span>
        </div>
        <div className="stat">
          <span className="label">Peak risk score</span>
          <span className="value">{peak.risk_score.toFixed(2)}</span>
        </div>
      </section>

      <section className="card">
        <h2>72-hour forecast</h2>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis />
              <Tooltip
                formatter={(value) => [
                  `${Number(value ?? 0).toFixed(2)} m`,
                  'Water level',
                ]}
              />
              <ReferenceLine
                y={forecast.danger_level_m}
                stroke="#dc2626"
                strokeDasharray="6 4"
                label="Danger level"
              />
              <Line
                type="monotone"
                dataKey="level"
                stroke="#2563eb"
                strokeWidth={3}
                dot
                name="Water level"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="card">
        <h2>Contributing factors</h2>
        <ul className="factors-list">
          {peak.top_factors.map((factor, index) => (
            <li className="factor-item" key={factor}>
              <span className="bar" style={{ width: `${90 - index * 20}px` }} />
              <span>{FACTOR_LABELS[factor] ?? factor}</span>
              <span>{index === 0 ? 'High influence' : 'Moderate influence'}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2>Simulated alert</h2>
        <p className="meta">Demo action only. No real notification will be sent.</p>
        <button className="btn btn-warning" type="button" onClick={handleAlert} disabled={alertLoading}>
          {alertLoading ? 'Sending…' : 'Simulate alert'}
        </button>
        {alert && (
          <div className={`alert-banner ${alert.triggered ? 'triggered' : 'not-triggered'}`}>
            {alert.message}
          </div>
        )}
      </section>
    </div>
  )
}
