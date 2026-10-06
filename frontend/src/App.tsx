import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import './App.css'
import DashboardPage from './pages/DashboardPage'
import StationDetailPage from './pages/StationDetailPage'
import ModelEvaluationPage from './pages/ModelEvaluationPage'
import AboutPage from './pages/AboutPage'

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Close sidebar on mobile resize
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 1024) setSidebarOpen(false)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div className="command-shell">
      {/* Mobile Drawer Backdrop */}
      {sidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Left Navigation Sidebar */}
      <aside className={`command-sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-logo-icon" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
              <path d="M7 14.5c1.5-1 3.5-1 5 0 1.5 1 3.5 1 5 0" />
            </svg>
          </div>
          <div className="brand-titles">
            <span className="brand-title">AquaWatch</span>
            <span className="brand-subtitle">Flood Intelligence</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            <span className="nav-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="7" height="7" rx="1.5" />
                <rect x="14" y="3" width="7" height="7" rx="1.5" />
                <rect x="14" y="14" width="7" height="7" rx="1.5" />
                <rect x="3" y="14" width="7" height="7" rx="1.5" />
              </svg>
            </span>
            <span>Dashboard</span>
          </NavLink>

          <NavLink
            to="/evaluation"
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            <span className="nav-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 3v18h18" />
                <path d="m19 9-5 5-4-4-3 3" />
              </svg>
            </span>
            <span>Model Evaluation</span>
          </NavLink>

          <NavLink
            to="/about"
            className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            <span className="nav-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 16v-4" />
                <path d="M12 8h.01" />
              </svg>
            </span>
            <span>About / Data Sources</span>
          </NavLink>
        </nav>

        {/* System Status Box matching reference screenshot */}
        <div className="sidebar-status-card">
          <div className="status-indicator-row">
            <span className="status-shield-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </span>
            <div>
              <span className="status-label-small">System Status</span>
              <strong className="status-title-text">Operational</strong>
            </div>
          </div>
          <p className="status-subtext">FastAPI &amp; ML Models Online</p>
        </div>
      </aside>

      {/* Main Workspace */}
      <div className="command-workspace">
        <main className="workspace-content">
          <Routes>
            <Route path="/" element={<DashboardPage onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />} />
            <Route path="/station/:stationId" element={<StationDetailPage />} />
            <Route path="/evaluation" element={<ModelEvaluationPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="*" element={<DashboardPage onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
