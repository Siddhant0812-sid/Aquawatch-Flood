interface DashboardHeaderProps {
  onToggleSidebar?: () => void
  selectedDate: string
  onDateChange: (date: string) => void
  onRefresh: () => void
  refreshing: boolean
  currentTime: string
}

export default function DashboardHeader({
  onToggleSidebar,
  selectedDate,
  onDateChange,
  onRefresh,
  refreshing,
  currentTime,
}: DashboardHeaderProps) {
  return (
    <header className="command-header">
      <div className="header-left">
        {onToggleSidebar && (
          <button
            type="button"
            className="sidebar-toggle-btn"
            onClick={onToggleSidebar}
            aria-label="Toggle navigation menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        )}
        <div className="header-title-box">
          <span className="header-icon-pill" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00b4d8" strokeWidth="2.5">
              <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
            </svg>
          </span>
          <div>
            <h1 className="header-main-title">Flood Monitoring Intelligence</h1>
            <p className="header-sub-caption">Brahmaputra Basin, Assam · Real-Time SAR &amp; Hydro AI</p>
          </div>
        </div>
      </div>

      <div className="header-controls">
        <div className="api-badge">
          <span className="live-dot" />
          <span>Live API</span>
        </div>

        <div className="date-picker-wrap">
          <label htmlFor="top-date-picker" className="visually-hidden">SAR Acquisition Date</label>
          <input
            id="top-date-picker"
            type="date"
            className="ctrl-input-date"
            value={selectedDate}
            onChange={(e) => onDateChange(e.target.value)}
            title="Sentinel-1 SAR acquisition date"
          />
        </div>

        <button
          type="button"
          className="ctrl-btn-refresh"
          onClick={onRefresh}
          disabled={refreshing}
          title="Refresh hydrological telemetry"
        >
          <svg
            className={refreshing ? 'spin-icon' : ''}
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
          >
            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.19" />
          </svg>
          <span>{refreshing ? 'Syncing...' : 'Refresh'}</span>
        </button>

        <div className="live-clock-pill">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span>{currentTime}</span>
        </div>
      </div>
    </header>
  )
}

