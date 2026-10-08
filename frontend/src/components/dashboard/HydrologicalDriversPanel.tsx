import type { AlertResponse, ForecastPoint } from '../../api/client'

const FACTOR_DESCRIPTIONS: Record<string, { label: string; pct: number }> = {
  rainfall_72h: { label: '72h Rainfall Accumulation', pct: 92 },
  upstream_level: { label: 'Upstream River Surge', pct: 85 },
  rate_of_rise: { label: 'Rate of River Stage Rise', pct: 74 },
  seasonal_trend: { label: 'Seasonal Monsoon Trend', pct: 58 },
}

interface HydrologicalDriversPanelProps {
  peakForecast: ForecastPoint | null
  onSimulateAlert: () => void
  alertLoading: boolean
  alertResult: AlertResponse | null
}

export default function HydrologicalDriversPanel({
  peakForecast,
  onSimulateAlert,
  alertLoading,
  alertResult,
}: HydrologicalDriversPanelProps) {
  return (
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
          (key: string) => {
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
                      background:
                        item.pct > 80
                          ? 'linear-gradient(90deg, #f59e0b, #ef4444)'
                          : 'linear-gradient(90deg, #00b4d8, #3b82f6)',
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
            onClick={onSimulateAlert}
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
  )
}
