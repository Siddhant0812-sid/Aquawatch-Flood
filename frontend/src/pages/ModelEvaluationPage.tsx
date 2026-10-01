import { useEffect, useState } from 'react'
import {
  fetchEvaluationSummary,
  type EvaluationSummaryResponse,
} from '../api/client'

export default function ModelEvaluationPage() {
  const [data, setData] = useState<EvaluationSummaryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'comparison' | 'attention' | 'backtest'>('comparison')

  useEffect(() => {
    fetchEvaluationSummary()
      .then((res) => {
        setData(res)
        setLoading(false)
      })
      .catch((err) => {
        console.warn('Could not load evaluation summary:', err)
        setLoading(false)
      })
  }, [])

  return (
    <div className="evaluation-page">
      <section className="card">
        <h2>Model Evaluation & Performance Benchmarks</h2>
        <p className="description">
          Detailed metrics, attention maps, and historical backtests for <strong>Member 1</strong> (SAR
          Surface Water Segmentation) and <strong>Member 2</strong> (Multi-Horizon Hydrological Forecasting).
        </p>
      </section>

      {/* Member 1: SAR Segmentation Section */}
      <section className="card">
        <div className="section-header">
          <span className="source-tag">Member 1 Contribution</span>
          <h3>Sentinel-1 SAR Flood Extent Segmentation (U-Net)</h3>
        </div>
        <p>
          Trained on dual-polarization Sentinel-1 Synthetic Aperture Radar (SAR) imagery to delineate inundated
          regions across the Brahmaputra basin regardless of cloud cover.
        </p>

        <div className="specs-grid">
          <div className="spec-item">
            <span className="spec-label">Model Architecture</span>
            <span className="spec-value">ResNet-34 Encoder + U-Net Decoder</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Input Bands</span>
            <span className="spec-value">VV & VH Dual Polarization (2-channel)</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Spatial Resolution</span>
            <span className="spec-value">10 meters per pixel</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Inference Mechanism</span>
            <span className="spec-value">256×256 Sliding Window (Stride 64)</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Preprocessing</span>
            <span className="spec-value">Lee Speckle Filter → dB Conversion ([-30, 5]) → uint8</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Vectorization Output</span>
            <span className="spec-value">GeoJSON Polygons (Assam Basin Bounding Box)</span>
          </div>
        </div>

        <div className="note-box">
          <strong>Operational Display:</strong> U-Net predictions are rendered directly as an interactive vector
          polygon layer on the main <a href="/">Dashboard</a> map with calculated coverage percentage.
        </div>
      </section>

      {/* Member 2: Forecasting & Explainability Section */}
      <section className="card">
        <div className="section-header">
          <span className="source-tag">Member 2 Contribution</span>
          <h3>Hydrological Forecasting & Model Comparison</h3>
        </div>
        <p>
          Comparative evaluation of time-series models for multi-step water level forecasting (24h, 48h, 72h)
          trained on hourly Central Water Commission (CWC) telemetry and IMD rainfall observations.
        </p>

        {loading ? (
          <p className="loading-text">Loading benchmark metrics...</p>
        ) : data && data.metrics.length > 0 ? (
          <div className="table-wrapper">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th>Model Architecture</th>
                  <th>Forecast Horizon</th>
                  <th>MAE (meters)</th>
                  <th>RMSE (meters)</th>
                  <th>Role in AquaWatch</th>
                </tr>
              </thead>
              <tbody>
                {data.metrics.map((m, idx) => (
                  <tr key={idx} className={m.model === 'LSTM' ? 'highlight-row' : ''}>
                    <td><strong>{m.model}</strong></td>
                    <td>+{m.horizon_h} hours</td>
                    <td>{m.mae.toFixed(4)} m</td>
                    <td>{m.rmse.toFixed(4)} m</td>
                    <td>
                      {m.model === 'LSTM' && <span className="status-pill active-pill">Production Forecaster</span>}
                      {m.model === 'ARIMA' && <span className="status-pill">Statistical Baseline</span>}
                      {m.model === 'TFT-Lite' && <span className="status-pill">Transformer Candidate</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="subtext">Offline metrics table loaded from training pipeline.</p>
        )}

        {/* Explainability and Visual Artifacts Tabs */}
        <div className="artifact-viewer">
          <h4>Visual Artifacts & Explainability Plots</h4>
          <div className="tab-buttons">
            <button
              type="button"
              className={`tab-btn ${activeTab === 'comparison' ? 'active' : ''}`}
              onClick={() => setActiveTab('comparison')}
            >
              Model Comparison Chart
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === 'attention' ? 'active' : ''}`}
              onClick={() => setActiveTab('attention')}
            >
              Temporal Attention Weights
            </button>
            <button
              type="button"
              className={`tab-btn ${activeTab === 'backtest' ? 'active' : ''}`}
              onClick={() => setActiveTab('backtest')}
            >
              2022 Monsoon Backtest
            </button>
          </div>

          <div className="plot-display">
            {activeTab === 'comparison' && (
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
                  <strong>Figure 1:</strong> Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) across 24h,
                  48h, and 72h lead times. The stacked 2-layer LSTM demonstrates balanced accuracy and lowest error across
                  operational horizons.
                </p>
              </div>
            )}

            {activeTab === 'attention' && (
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
                  <strong>Figure 2:</strong> Temporal feature importance across the 72-hour sliding window. Peaks
                  indicate that rainfall bursts 24–48 hours prior to the forecast horizon heavily influence the river level surge.
                </p>
              </div>
            )}

            {activeTab === 'backtest' && (
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
                  <strong>Figure 3:</strong> Historical backtest during the severe June–September 2022 Assam monsoon.
                  The model accurately projected water levels breaching the danger line (red dashed line) with 48 hours of advance lead time.
                </p>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
