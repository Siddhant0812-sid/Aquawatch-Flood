import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  fetchForecast,
  fetchSegment,
  fetchStations,
  simulateAlert,
} from '../api/client'
import type {
  AlertResponse,
  ForecastResponse,
  SegmentResponse,
  StationSummary,
} from '../api/client'
import DashboardHeader from '../components/dashboard/DashboardHeader'
import KpiMetricsRow from '../components/dashboard/KpiMetricsRow'
import ForecastChartPanel from '../components/dashboard/ForecastChartPanel'
import HydrologicalDriversPanel from '../components/dashboard/HydrologicalDriversPanel'
import BasinMapPanel from '../components/dashboard/BasinMapPanel'
import StationTablePanel from '../components/dashboard/StationTablePanel'
import SarShowcasePanel from '../components/dashboard/SarShowcasePanel'

function riskColor(risk: string): string {
  if (risk === 'LOW') return '#10b981'
  if (risk === 'MODERATE') return '#f59e0b'
  if (risk === 'HIGH') return '#ef4444'
  return '#64748b'
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

interface DashboardPageProps {
  onToggleSidebar?: () => void
}

export default function DashboardPage({ onToggleSidebar }: DashboardPageProps) {
  const navigate = useNavigate()

  // Real backend telemetry states
  const [stations, setStations] = useState<StationSummary[]>([])
  const [selectedStationId, setSelectedStationId] = useState<string>('guwahati')
  const [stationForecast, setStationForecast] = useState<ForecastResponse | null>(null)
  const [segment, setSegment] = useState<SegmentResponse | null>(null)
  const [selectedDate, setSelectedDate] = useState<string>(today)

  // UI & loading states
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Simulation & Tabs states
  const [alertResult, setAlertResult] = useState<AlertResponse | null>(null)
  const [alertLoading, setAlertLoading] = useState(false)
  const [activeSarView, setActiveSarView] = useState<'scene' | 'samples' | 'explain'>('scene')
  const [activePlotTab, setActivePlotTab] = useState<'comparison' | 'attention' | 'backtest'>('comparison')

  // Live Clock
  const [currentTime, setCurrentTime] = useState<string>(() => {
    const now = new Date()
    return (
      now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) +
      ' · ' +
      now.toLocaleDateString([], { month: 'short', day: '2-digit', year: 'numeric' })
    )
  })

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date()
      setCurrentTime(
        now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) +
          ' · ' +
          now.toLocaleDateString([], { month: 'short', day: '2-digit', year: 'numeric' })
      )
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  // Initial load: Fetch stations, segmentation, and initial forecast
  const loadInitialData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [stationRes, segmentRes] = await Promise.all([
        fetchStations(),
        fetchSegment(selectedDate),
      ])
      setStations(stationRes.stations)
      setSegment(segmentRes)

      const initialId = stationRes.stations[0]?.station_id ?? 'guwahati'
      setSelectedStationId(initialId)
      const fc = await fetchForecast(initialId)
      setStationForecast(fc)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to connect to AquaWatch backend')
    } finally {
      setLoading(false)
    }
  }, [selectedDate])

  useEffect(() => {
    let isSubscribed = true
    const fetchData = async () => {
      try {
        const [stationRes, segmentRes] = await Promise.all([
          fetchStations(),
          fetchSegment(selectedDate),
        ])
        if (!isSubscribed) return
        setStations(stationRes.stations)
        setSegment(segmentRes)

        const initialId = stationRes.stations[0]?.station_id ?? 'guwahati'
        setSelectedStationId(initialId)
        const fc = await fetchForecast(initialId)
        if (!isSubscribed) return
        setStationForecast(fc)
      } catch (err: unknown) {
        if (!isSubscribed) return
        setError(err instanceof Error ? err.message : 'Failed to connect to AquaWatch backend')
      } finally {
        if (isSubscribed) {
          setLoading(false)
        }
      }
    }
    fetchData()
    return () => {
      isSubscribed = false
    }
  }, [selectedDate])

  // When selected station changes, fetch its forecast
  const handleSelectStation = useCallback(async (stationId: string) => {
    setSelectedStationId(stationId)
    setAlertResult(null)
    try {
      const fc = await fetchForecast(stationId)
      setStationForecast(fc)
    } catch (err: unknown) {
      console.error('Failed to load forecast for station', stationId, err)
    }
  }, [])

  // Manual refresh trigger
  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const [stationRes, segmentRes, forecastRes] = await Promise.all([
        fetchStations(),
        fetchSegment(selectedDate),
        fetchForecast(selectedStationId),
      ])
      setStations(stationRes.stations)
      setSegment(segmentRes)
      setStationForecast(forecastRes)
    } catch (err: unknown) {
      console.error('Refresh error:', err)
    } finally {
      setRefreshing(false)
    }
  };

  // Peak forecast calculation
  const peakForecast = useMemo(() => {
    if (!stationForecast || !stationForecast.forecasts.length) return null
    return stationForecast.forecasts.reduce((curr, item) =>
      item.risk_score > curr.risk_score ? item : curr
    )
  }, [stationForecast])

  // Overall Basin Risk
  const basinRisk = useMemo(() => {
    if (stations.some((s) => s.current_risk_level === 'HIGH')) return 'HIGH'
    if (stations.some((s) => s.current_risk_level === 'MODERATE')) return 'MODERATE'
    return 'LOW'
  }, [stations])

  // Peak Risk Score scaled to 0-100
  const riskScoreDisplay = useMemo(() => {
    if (peakForecast) {
      return Math.round(peakForecast.risk_score * 100)
    }
    return basinRisk === 'HIGH' ? 82 : basinRisk === 'MODERATE' ? 58 : 24
  }, [peakForecast, basinRisk])

  // Selected station summary
  const selectedStation = useMemo(() => {
    return stations.find((s) => s.station_id === selectedStationId) ?? stations[0]
  }, [stations, selectedStationId])

  // 72h Water level trend chart data
  const chartData = useMemo(() => {
    if (!stationForecast) return []
    return [
      {
        time: 'Current',
        level: stationForecast.current_level_m,
        danger: stationForecast.danger_level_m,
        warning: stationForecast.danger_level_m - 1.0,
      },
      ...stationForecast.forecasts.map((fc) => ({
        time: `+${fc.horizon_hours}h`,
        level: fc.predicted_level_m,
        danger: stationForecast.danger_level_m,
        warning: stationForecast.danger_level_m - 1.0,
      })),
    ]
  }, [stationForecast])

  // Handle alert simulation
  const handleSimulateAlert = async () => {
    if (!stationForecast || !peakForecast) return
    setAlertLoading(true)
    try {
      const res = await simulateAlert(selectedStationId, peakForecast.risk_score)
      setAlertResult(res)
    } catch (err: unknown) {
      setAlertResult({
        triggered: false,
        message: err instanceof Error ? err.message : 'Alert simulation failed',
      })
    } finally {
      setAlertLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="dashboard-loading-state">
        <div className="pulse-radar" aria-hidden="true" />
        <p>Connecting to AquaWatch telemetry &amp; SAR models&hellip;</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="dashboard-error-state">
        <h3>Connection Error</h3>
        <p>{error}</p>
        <button type="button" className="ctrl-btn-action" onClick={loadInitialData}>
          Retry Connection
        </button>
      </div>
    )
  }

  const comparisonImgSrc = segment?.prediction_image_url || '/outputs/sar_unet_deeplabv3_comparison.png'
  const samplesImgSrc = segment?.validation_samples_url || '/outputs/sar_validation_samples.png'

  return (
    <div className="dashboard-command-view">
      {/* 1. Header Navigation & Controls */}
      <DashboardHeader
        onToggleSidebar={onToggleSidebar}
        selectedDate={selectedDate}
        onDateChange={setSelectedDate}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        currentTime={currentTime}
      />

      {/* 2. Top Metrics KPI Cards */}
      <KpiMetricsRow
        stationForecast={stationForecast}
        selectedStation={selectedStation}
        segment={segment}
        basinRisk={basinRisk}
        riskScoreDisplay={riskScoreDisplay}
        stationsCount={stations.length}
        riskColor={riskColor}
      />

      {/* 3. Middle Grid: 72h Forecast Chart + Hydrological Drivers */}
      <section className="middle-analytics-grid">
        <ForecastChartPanel
          selectedStation={selectedStation}
          selectedStationId={selectedStationId}
          onSelectStation={handleSelectStation}
          stations={stations}
          chartData={chartData}
          stationForecast={stationForecast}
        />

        <HydrologicalDriversPanel
          peakForecast={peakForecast}
          onSimulateAlert={handleSimulateAlert}
          alertLoading={alertLoading}
          alertResult={alertResult}
        />
      </section>

      {/* 4. Lower Grid: Basin Overview Map & Station Table */}
      <section className="lower-grid">
        <BasinMapPanel
          segment={segment}
          selectedDate={selectedDate}
          stations={stations}
          selectedStationId={selectedStationId}
          onSelectStation={handleSelectStation}
          selectedStation={selectedStation}
          stationForecast={stationForecast}
          onInspectStation={(id) => navigate(`/station/${id}`)}
          riskColor={riskColor}
        />

        <StationTablePanel
          stations={stations}
          selectedStationId={selectedStationId}
          onSelectStation={handleSelectStation}
          onInspectStation={(id) => navigate(`/station/${id}`)}
        />
      </section>

      {/* 5. SAR Flood Segmentation & Model Specifications */}
      <SarShowcasePanel
        segment={segment}
        activeSarView={activeSarView}
        setActiveSarView={setActiveSarView}
        activePlotTab={activePlotTab}
        setActivePlotTab={setActivePlotTab}
        comparisonImgSrc={comparisonImgSrc}
        samplesImgSrc={samplesImgSrc}
      />
    </div>
  )
}
