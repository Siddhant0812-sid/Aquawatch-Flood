import { useEffect, useState } from 'react'
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

  useEffect(() => {
    let active = true
    setLoading(true)
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
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [selectedDate])

  if (loading) return <div className="loading">Loading dashboard…</div>
  if (error) return <div className="error-state">Failed to load dashboard: {error}</div>

  const basinRisk = overallRisk(stations)
  return (
    <div className="dashboard">
      <section className="map-panel" aria-label="Flood extent map">
        <div className="date-control">
          <label htmlFor="segment-date">Imagery date</label>
          <input id="segment-date" type="date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} />
          {segment && <span className="imagery-note">Acquisition: {segment.imagery_acquisition_date} · Coverage: {segment.coverage_pct}% · Sentinel-1 revisit is approximately 6–12 days</span>}
        </div>
        <div className="map-container">
          <MapContainer center={ASSAM_CENTER} zoom={7} scrollWheelZoom>
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {segment && <GeoJSON data={segment.mask_geojson} style={{ fillColor: '#2563eb', fillOpacity: 0.35, color: '#1d4ed8', weight: 1.5 }} />}
            {stations.map((station) => (
              <CircleMarker key={station.station_id} center={[station.lat, station.lon]} radius={9} pathOptions={{ fillColor: riskColor(station.current_risk_level), fillOpacity: 0.9, color: '#fff', weight: 2 }} eventHandlers={{ click: () => navigate(`/station/${station.station_id}`) }}>
                <Popup><strong>{station.name}</strong><br />Risk: {station.current_risk_level}</Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>
      </section>
      <aside className="sidebar">
        <div className="risk-summary"><strong>Overall basin risk</strong><span className={`risk-badge ${basinRisk.toLowerCase()}`}><span className="dot" />{basinRisk}</span></div>
        <section className="card">
          <h2>Monitoring stations</h2>
          <ul className="station-list">
            {stations.map((station) => (
              <li key={station.station_id} className="station-item" onClick={() => navigate(`/station/${station.station_id}`)}>
                <div><h3>{station.name}</h3><p>{station.river}</p></div>
                <span className={`risk-badge ${station.current_risk_level.toLowerCase()}`}><span className="dot" />{station.current_risk_level}</span>
              </li>
            ))}
          </ul>
        </section>
      </aside>
    </div>
  )
}
