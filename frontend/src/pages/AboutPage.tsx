export default function AboutPage() {
  return (
    <div className="about-page">
      <h1>About AquaWatch</h1>
      <p>AquaWatch is a local Assam flood mapping and short-term risk forecasting demo for the Brahmaputra basin.</p>
      <section className="card">
        <h2>How to use this demo</h2>
        <ol className="steps-list">
          <li>Choose an imagery date on the dashboard to inspect the mock flood overlay.</li>
          <li>Select a station marker or station card to open its 72-hour forecast.</li>
          <li>Use the simulated alert button to demonstrate the alert flow.</li>
        </ol>
      </section>
      <section className="card"><h2>Data sources and use</h2><table><thead><tr><th>Source</th><th>Use</th></tr></thead><tbody><tr><td>Sentinel-1 SAR</td><td>Flood extent mapping and acquisition-date context.</td></tr><tr><td>CWC / IMD rainfall</td><td>Rainfall features for forecasting.</td></tr><tr><td>Assam State Disaster Management / CWC</td><td>River-level monitoring and danger thresholds.</td></tr><tr><td>MMFlood and Sen1Floods11</td><td>Future segmentation training and evaluation.</td></tr><tr><td>OpenStreetMap</td><td>Map tiles and geographic context.</td></tr></tbody></table></section>
      <section className="card"><h2>Limitations</h2><div className="limitation"><strong>Mock mode:</strong> This local demo uses deterministic mock data.</div><div className="limitation"><strong>Satellite revisit:</strong> Sentinel-1 imagery is not real-time; the acquisition date is shown separately.</div><div className="limitation"><strong>Simulated alerts:</strong> No SMS, email, or push notification is sent.</div><div className="limitation"><strong>No persistence:</strong> Runtime results are held in memory and reset when the backend restarts.</div></section>
    </div>
  )
}
