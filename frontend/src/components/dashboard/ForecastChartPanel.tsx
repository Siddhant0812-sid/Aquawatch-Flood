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
import type { ForecastResponse, StationSummary } from '../../api/client'

interface ForecastChartPanelProps {
  selectedStation?: StationSummary
  selectedStationId: string
  onSelectStation: (stationId: string) => void
  stations: StationSummary[]
  chartData: Array<{ time: string; level: number; danger: number; warning: number }>
  stationForecast: ForecastResponse | null
}

export default function ForecastChartPanel({
  selectedStation,
  selectedStationId,
  onSelectStation,
  stations,
  chartData,
  stationForecast,
}: ForecastChartPanelProps) {
  return (
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
            onChange={(e) => onSelectStation(e.target.value)}
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
  )
}

