import { CircleMarker, GeoJSON, MapContainer, Popup, TileLayer } from 'react-leaflet'
import type { ForecastResponse, SegmentResponse, StationSummary } from '../../api/client'

const ASSAM_CENTER: [number, number] = [26.5, 92.8]

interface BasinMapPanelProps {
  segment: SegmentResponse | null
  selectedDate: string
  stations: StationSummary[]
  selectedStationId: string
  onSelectStation: (stationId: string) => void
  selectedStation?: StationSummary
  stationForecast: ForecastResponse | null
  onInspectStation: (stationId: string) => void
  riskColor: (risk: string) => string
}

export default function BasinMapPanel({
  segment,
  selectedDate,
  stations,
  selectedStationId,
  onSelectStation,
  selectedStation,
  stationForecast,
  onInspectStation,
  riskColor,
}: BasinMapPanelProps) {
  return (
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
                click: () => onSelectStation(st.station_id),
              }}
            >
              <Popup>
                <div className="map-popup-inner">
                  <strong>{st.name} Station</strong>
                  <p>River: {st.river}</p>
                  <p>
                    Current Risk:{' '}
                    <span style={{ color: riskColor(st.current_risk_level), fontWeight: 700 }}>
                      {st.current_risk_level}
                    </span>
                  </p>
                  <button
                    type="button"
                    className="popup-btn"
                    onClick={() => onInspectStation(st.station_id)}
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
            onClick={() => onInspectStation(selectedStationId)}
          >
            Inspect Station Details &rarr;
          </button>
        </div>
      </div>
    </div>
  )
}

