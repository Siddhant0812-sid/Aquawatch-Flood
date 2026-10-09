# Technical Requirements Document (TRD)

## AquaWatch — Flood Mapping & Forecasting, Assam/Brahmaputra Basin

| Field | Detail |
|---|---|
| Document version | 1.0 |
| Related documents | PRD (AquaWatch_PRD_Assam.md), Implementation Guide, README |
| Architecture note | Simplified — no persistent database, no deployment/containerization layer. Everything runs locally, in-memory, for development and demo. |

---

## 1. Purpose

This document specifies the technical requirements needed to implement AquaWatch as defined in the PRD: exact technology choices, model specifications, API contracts, performance targets, and quality requirements. Where the PRD says *what* the system must do, this document says *how* it will be built.

---

## 2. Technology Stack

| Layer | Technology | Version (recommended) |
|---|---|---|
| Language | Python | 3.10+ |
| Deep learning | PyTorch | 2.x |
| Satellite data access | Google Earth Engine Python API (`earthengine-api`) | latest |
| Geospatial raster I/O | `rasterio`, `numpy` | latest stable |
| Tabular data | `pandas` | latest stable |
| Classical time-series baseline | `statsmodels` (ARIMA) | latest stable |
| Backend API | FastAPI + `uvicorn` | latest stable |
| Frontend | React + Leaflet (`react-leaflet`) | React 18+ |
| Charts | Recharts or Chart.js | latest stable |
| No database | — | in-memory Python objects / local files only |
| No containerization | — | run directly via `uvicorn` / `npm start` |

---

## 3. System Components — Technical Specification

### 3.1 Data Ingestion Module
- **Sentinel-1 SAR pull:** via Earth Engine `ImageCollection('COPERNICUS/S1_GRD')`, filtered to Assam bounding box `[89.7, 24.1, 96.0, 28.2]`, IW mode, VV+VH polarization.
- **Rainfall ingestion:** reads local CSV/XLSX files (Assam CWC Telemetry, IMD subdivision data) via `pandas.read_csv` / `read_excel`.
- **Water level ingestion:** reads the Assam Department Telemetry CSV/XLSX (columns confirmed: `Station`, `River`, `Basin`, `Latitude`, `Longitude`, `Data Acquisition Time`, `River Water Level Telemetry Hourly (meter)`, etc.).
- **Output:** cleaned `pandas.DataFrame` objects held in memory for the current session; no write-back to a persistent store.

### 3.2 Segmentation Module
- **Baseline model:** SAR intensity thresholding on the VH band (`threshold ≈ -17.5 dB`, tunable per calibration against MMFlood).
- **Advanced model:** U-Net, 2-class output (flood / non-flood), input channels = 2 (VV, VH), encoder-decoder with skip connections as specified in the Implementation Guide.
- **Comparison model:** DeepLabV3+ (atrous convolutions) — optional, for the architecture comparison study.
- **Training data:** MMFlood (primary), Sen1Floods11 (secondary benchmark).
- **Output format:** binary mask array (`H x W`, uint8) plus a GeoJSON polygon conversion for map overlay.

### 3.3 Forecasting Module
- **Baseline model:** ARIMA per station, fit on water-level series alone.
- **Advanced model:** LSTM, 2-layer, hidden size 64, input features = `[rain_24h, rain_72h, level_rate_of_rise, water_level_m]`, output = risk score/level prediction at 24h/48h/72h horizons.
- **Comparison model:** Temporal Fusion Transformer — optional, for the architecture comparison study and attention-based explainability.
- **Output format:** JSON object `{station_id, horizon_hours, predicted_level_m, risk_score}`.

### 3.4 Backend API Module
- **Framework:** FastAPI, single-process, run with `uvicorn main:app --reload`.
- **State management:** models loaded once at process startup into memory; most recent inference results cached in a plain Python `dict` (in-memory only, cleared on restart — acceptable given no persistence requirement).
- **CORS:** enabled for all origins during development (`allow_origins=["*"]`) since frontend and backend run on different local ports.

### 3.5 Frontend Module
- **Framework:** React (function components + hooks).
- **Map:** Leaflet via `react-leaflet`, with an `ImageOverlay` layer for the flood mask and `Marker`/`CircleMarker` for water-level stations.
- **Charts:** Recharts line chart for the 72-hour forecast trend.
- **Data fetching:** native `fetch()` calls to the FastAPI endpoints (see API Contract section below).

---

## 4. API Contract

| Endpoint | Method | Request Params | Response |
|---|---|---|---|
| `/segment` | GET | `date` (ISO string) | `{ "mask_geojson": {...}, "date": "...", "coverage_pct": 0.0 }` |
| `/forecast` | GET | `station_id` (string) | `{ "station_id": "...", "forecasts": [{"horizon_hours": 24, "predicted_level_m": 0.0, "risk_score": 0.0}, ...] }` |
| `/stations` | GET | — | `[{ "station_id": "...", "name": "...", "lat": 0.0, "lon": 0.0 }, ...]` |
| `/health` | GET | — | `{ "status": "ok" }` |

Full request/response schemas are defined in `BACKEND_SCHEMA.md`.

---

## 5. Non-Functional / Performance Requirements

| Requirement | Target |
|---|---|
| Segmentation inference time | < 2 minutes per SAR tile on a single GPU (Colab-tier acceptable) |
| Forecast inference time | < 5 seconds per station (lightweight LSTM) |
| Dashboard load time | < 3 seconds on a standard laptop/browser |
| Data freshness | Rainfall/water-level data refreshed per available telemetry update (hourly source data; polling frequency configurable) |
| Missing data handling | Linear interpolation for gaps < 6 hours; flagged as "data gap" in the UI for longer gaps |
| Model reproducibility | Fixed random seeds for train/val/test splits; report exact split methodology (time/location-based, not random) |

---

## 6. Testing Requirements

| Test Type | Scope |
|---|---|
| Unit tests | Preprocessing functions (SAR normalization, feature engineering), API request/response validation |
| Model evaluation | IoU/F1 for segmentation on MMFlood held-out test set; RMSE/MAE for forecasting on held-out Assam water-level data |
| Integration test | End-to-end: real Assam SAR tile → segmentation → mask rendered on dashboard; real Assam rainfall/water-level → forecast → chart rendered on dashboard |
| Historical backtest | At least one known past Assam flood event, checked against the forecasting model's retrospective output |

---

## 7. Security & Data Handling

- No personal/private data is processed — all inputs are public satellite and government hydrological/meteorological data.
- No authentication layer required for the local demo (single-user, local-only access).
- Earth Engine credentials handled via the standard `ee.Authenticate()` flow; credentials are not committed to source control (`.gitignore` the token file).

---

## 8. Known Technical Constraints

- Sentinel-1 revisit time (6–12 days) limits true real-time updates — documented explicitly in the PRD and UI (see UI/UX Design doc for how this is communicated to the user).
- No persistent storage means results do not survive a backend restart — acceptable for a single-session academic demo; explicitly out of scope per PRD Section 4.
- MMFlood/Sen1Floods11 may not contain Assam-specific flood events — segmentation model is trained generically and applied/evaluated specifically on Assam imagery (transfer approach, documented in PRD Section 15).

---
*Companion to AquaWatch_PRD_Assam.md, IMPLEMENTATION_GUIDE.md, UI_UX_DESIGN.md, BACKEND_SCHEMA.md, and APP_FLOW.md.*
