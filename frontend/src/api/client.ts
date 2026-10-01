const API_BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null) as
      | { error?: string; detail?: string }
      | null
    throw new Error(body?.detail ?? body?.error ?? `Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

export type RiskLabel = 'LOW' | 'MODERATE' | 'HIGH'

export interface StationSummary {
  station_id: string
  name: string
  river: string
  lat: number
  lon: number
  current_risk_level: RiskLabel
}

export interface SegmentResponse {
  date: string
  mask_geojson: GeoJSON.FeatureCollection
  coverage_pct: number
  imagery_acquisition_date: string
}

export interface ForecastPoint {
  horizon_hours: number
  predicted_level_m: number
  risk_score: number
  risk_label: RiskLabel
  top_factors: string[]
}

export interface ForecastResponse {
  station_id: string
  station_name: string
  current_level_m: number
  danger_level_m: number
  forecasts: ForecastPoint[]
}

export interface AlertResponse {
  triggered: boolean
  message: string
}

export interface ModelMetric {
  model: string
  horizon_h: number
  mae: number
  rmse: number
}

export interface SegmentationSpecs {
  model: string
  backbone: string
  input_channels: number
  bands: string[]
  resolution_m: number
  window_size: number
  stride: number
  threshold: number
  target: string
}

export interface EvaluationSummaryResponse {
  metrics: ModelMetric[]
  segmentation: SegmentationSpecs
  artifacts: {
    model_comparison_plot: string
    attention_lstm_plot: string
    attention_tft_plot: string
    backtest_plot: string
  }
}

export function fetchStations(): Promise<{ stations: StationSummary[] }> {
  return request('/stations')
}

export function fetchSegment(date: string): Promise<SegmentResponse> {
  return request(`/segment?date=${encodeURIComponent(date)}`)
}

export function fetchForecast(stationId: string): Promise<ForecastResponse> {
  return request(`/forecast?station_id=${encodeURIComponent(stationId)}`)
}

export function simulateAlert(stationId: string, riskScore: number): Promise<AlertResponse> {
  return request('/simulate-alert', {
    method: 'POST',
    body: JSON.stringify({ station_id: stationId, risk_score: riskScore }),
  })
}

export function fetchHealth(): Promise<{ status: string }> {
  return request('/health')
}

export function fetchEvaluationSummary(): Promise<EvaluationSummaryResponse> {
  return request('/evaluation-summary')
}