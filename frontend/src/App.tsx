import { NavLink, Route, Routes } from 'react-router-dom'
import './App.css'
import DashboardPage from './pages/DashboardPage'
import StationDetailPage from './pages/StationDetailPage'
import AboutPage from './pages/AboutPage'

function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Brahmaputra Basin</p>
          <h1>AquaWatch Flood Dashboard</h1>
          <p className="app-subtitle">Mock-data situational awareness for Assam flood risk</p>
        </div>
        <span className="mode-badge">Demo mode</span>
      </header>

      <nav className="main-nav" aria-label="Main navigation">
        <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          Dashboard
        </NavLink>
        <NavLink to="/about" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          About / Data Sources
        </NavLink>
      </nav>

      <main className="page-shell">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/station/:stationId" element={<StationDetailPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="*" element={<DashboardPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
