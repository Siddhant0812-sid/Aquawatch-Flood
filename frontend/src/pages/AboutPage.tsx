export default function AboutPage() {
  return (
    <div className="about-page">
      <h1>About AquaWatch</h1>
      <p>AquaWatch is an AI-powered flood extent mapping and multi-horizon water-level forecasting platform for the Brahmaputra basin in Assam.</p>
      <section className="card">
        <h2>How to use the platform</h2>
        <ol className="steps-list">
          <li>Select an imagery date on the dashboard to view the Sentinel-1 SAR flood extent overlay.</li>
          <li>Click any monitoring station marker or sidebar card to view its 24h, 48h, and 72h water-level forecast.</li>
          <li>Review contributing risk factors (recent rainfall, rate of rise, and soil saturation).</li>
          <li>Visit the Model Evaluation tab to inspect benchmark comparisons, attention weights, and backtest results.</li>
        </ol>
      </section>
      <section className="card">
        <h2>AI Models &amp; Data Sources</h2>
        <table>
          <thead>
            <tr>
              <th>Component / Source</th>
              <th>Technical Function</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>ResNet-34 U-Net</td>
              <td>Dual-polarization (VV/VH) Sentinel-1 SAR surface water segmentation at 10m spatial resolution.</td>
            </tr>
            <tr>
              <td>FloodLSTM</td>
              <td>Multi-horizon (24h, 48h, 72h) river level forecasting using stacked 2-layer LSTM with 60 engineered features.</td>
            </tr>
            <tr>
              <td>CWC River Telemetry</td>
              <td>Hourly gauge station water levels and danger threshold monitoring.</td>
            </tr>
            <tr>
              <td>IMD Rainfall Data</td>
              <td>Rolling cumulative rainfall (3h, 6h, 12h, 24h, 48h, 72h) and antecedent soil moisture proxies.</td>
            </tr>
            <tr>
              <td>OpenStreetMap</td>
              <td>Geographic context and basemap tile rendering.</td>
            </tr>
          </tbody>
        </table>
      </section>
      <section className="card">
        <h2>Operational Notes</h2>
        <div className="limitation">
          <strong>Satellite Revisit:</strong> Sentinel-1 SAR imagery is refreshed every 6 to 12 days; the satellite acquisition date is shown alongside each overlay.
        </div>
        <div className="limitation">
          <strong>Alert Simulations:</strong> The alert simulation tests emergency alert triggers based on danger level proximity.
        </div>
        <div className="limitation">
          <strong>In-Memory Serving:</strong> Models and recent feature windows are cached in memory for sub-second API responsiveness.
        </div>
      </section>
    </div>
  )
}
