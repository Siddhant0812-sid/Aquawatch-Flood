import type { StationSummary } from '../../api/client'

interface StationTablePanelProps {
  stations: StationSummary[]
  selectedStationId: string
  onSelectStation: (stationId: string) => void
  onInspectStation: (stationId: string) => void
}

export default function StationTablePanel({
  stations,
  selectedStationId,
  onSelectStation,
  onInspectStation,
}: StationTablePanelProps) {
  return (
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
                  onClick={() => onSelectStation(st.station_id)}
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
                        onInspectStation(st.station_id)
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
  )
}

