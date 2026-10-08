import type { SegmentResponse } from '../../api/client'

interface SarShowcasePanelProps {
  segment: SegmentResponse | null
  activeSarView: 'scene' | 'samples' | 'explain'
  setActiveSarView: (view: 'scene' | 'samples' | 'explain') => void
  activePlotTab: 'comparison' | 'attention' | 'backtest'
  setActivePlotTab: (tab: 'comparison' | 'attention' | 'backtest') => void
  comparisonImgSrc: string
  samplesImgSrc: string
}

export default function SarShowcasePanel({
  segment,
  activeSarView,
  setActiveSarView,
  activePlotTab,
  setActivePlotTab,
  comparisonImgSrc,
  samplesImgSrc,
}: SarShowcasePanelProps) {
  return (
    <section className="panel-card sar-outputs-panel">
      <div className="panel-header">
        <div>
          <div className="badge-tag-row">
            <span className="source-tag">SAR Analysis</span>
            <span className="source-tag-blue">Sentinel-1 Dual-Pol VV/VH</span>
          </div>
          <h2>SAR Flood Extent &amp; Surface Water Segmentation</h2>
        </div>
        <span className="model-mode-badge real">
          {segment?.is_real_model ? 'ResNet-34 U-Net (Real SAR)' : 'Trained AI Model'}
        </span>
      </div>

      <p className="panel-description-text">
        Satellite radar flood segmentation comparing trained <strong>ResNet-34 U-Net</strong> against{' '}
        <strong>DeepLabV3+</strong> across the Brahmaputra floodplain in Assam.
      </p>

      {/* Tab Switcher */}
      <div className="command-tab-strip">
        <button
          type="button"
          className={`cmd-tab ${activeSarView === 'scene' ? 'active' : ''}`}
          onClick={() => setActiveSarView('scene')}
        >
          Assam Scene: VV vs. U-Net vs. DeepLabV3+
        </button>
        <button
          type="button"
          className={`cmd-tab ${activeSarView === 'samples' ? 'active' : ''}`}
          onClick={() => setActiveSarView('samples')}
        >
          Multi-Sample Validation Grid (5 Scenes)
        </button>
        <button
          type="button"
          className={`cmd-tab ${activeSarView === 'explain' ? 'active' : ''}`}
          onClick={() => setActiveSarView('explain')}
        >
          Forecast Explainability
        </button>
      </div>

      {activeSarView === 'scene' && (
        <div className="sar-showcase-box">
          <div className="clean-img-wrapper">
            <img
              src={comparisonImgSrc}
              alt="Assam Sentinel-1 VV amplitude alongside U-Net prediction and DeepLabV3+ prediction"
              className="sar-img-asset"
            />
          </div>
          <p className="sar-caption">
            <strong>Full Assam Scene Comparison:</strong> Input Sentinel-1 SAR VV amplitude (left), binary water
            mask predicted by ResNet-34 U-Net (center), and DeepLabV3+ benchmark (right). Water appears high-contrast white.
          </p>
        </div>
      )}

      {activeSarView === 'samples' && (
        <div className="sar-showcase-box">
          <div className="clean-img-wrapper">
            <img
              src={samplesImgSrc}
              alt="Multi-sample validation grid showing SAR Input, Ground Truth, U-Net, and DeepLabV3+"
              className="sar-img-asset"
            />
          </div>
          <p className="sar-caption">
            <strong>Validation Sample Evaluations (Samples 0, 25, 50, 100, 150):</strong> Ground truth water extent
            benchmarked against U-Net predictions across challenging wetland topologies.
          </p>
        </div>
      )}

      {activeSarView === 'explain' && (
        <div className="explainability-subview">
          <div className="command-tab-strip sub-tabs">
            <button
              type="button"
              className={`cmd-tab mini ${activePlotTab === 'comparison' ? 'active' : ''}`}
              onClick={() => setActivePlotTab('comparison')}
            >
              Model Comparison
            </button>
            <button
              type="button"
              className={`cmd-tab mini ${activePlotTab === 'attention' ? 'active' : ''}`}
              onClick={() => setActivePlotTab('attention')}
            >
              Temporal Attention
            </button>
            <button
              type="button"
              className={`cmd-tab mini ${activePlotTab === 'backtest' ? 'active' : ''}`}
              onClick={() => setActivePlotTab('backtest')}
            >
              2022 Monsoon Backtest
            </button>
          </div>

          <div className="clean-img-wrapper">
            {activePlotTab === 'comparison' && (
              <img
                src="/outputs/explainability/model_comparison.png"
                alt="Model Comparison"
                className="sar-img-asset"
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                }}
              />
            )}
            {activePlotTab === 'attention' && (
              <img
                src="/outputs/explainability/attention_lstm.png"
                alt="LSTM Temporal Attention"
                className="sar-img-asset"
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                }}
              />
            )}
            {activePlotTab === 'backtest' && (
              <img
                src="/outputs/explainability/backtest_NH15 Crossing Dhansirighat_2022.png"
                alt="2022 Historical Monsoon Backtest"
                className="sar-img-asset"
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                }}
              />
            )}
          </div>
        </div>
      )}

      {/* Specifications Footnote Grid */}
      <div className="specs-command-grid">
        <div className="spec-badge-box">
          <span className="spec-label">Architecture</span>
          <span className="spec-val">ResNet-34 U-Net</span>
        </div>
        <div className="spec-badge-box">
          <span className="spec-label">Sensor / Band</span>
          <span className="spec-val">Sentinel-1 Dual-Pol (VV/VH)</span>
        </div>
        <div className="spec-badge-box">
          <span className="spec-label">Spatial Resolution</span>
          <span className="spec-val">10 meters</span>
        </div>
        <div className="spec-badge-box">
          <span className="spec-label">Decision Threshold</span>
          <span className="spec-val">0.40 (TTA Horizontal-Flip)</span>
        </div>
        <div className="spec-badge-box">
          <span className="spec-label">SAR Inundated Extent</span>
          <span className="spec-val text-cyan">{segment?.coverage_pct ?? '8.9'}% of Basin</span>
        </div>
      </div>
    </section>
  )
}

