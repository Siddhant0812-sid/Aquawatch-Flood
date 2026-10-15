# AquaWatch Flood

AquaWatch is an integrated local application for flood awareness and emergency monitoring in Assam and the Brahmaputra basin. It combines a FastAPI backend with a React, Leaflet, and Recharts frontend to display:

- **Sentinel-1 SAR flood extent mapping** (real ResNet-34 U-Net inference with horizontal-flip test-time augmentation, georeferenced GeoJSON map polygons, and side-by-side VV vs. flood mask imagery);
- **Five Brahmaputra monitoring stations** and their operational risk levels;
- **24-hour, 48-hour, and 72-hour hydrological forecasts** driven by stacked multi-horizon LSTMs with 60 engineered features;
- **Forecast contributing factors** (72h rainfall sums, rate of rise, upstream levels);
- **Dedicated model evaluation & explainability tab** showing ARIMA vs. LSTM vs. TFT-Lite benchmarks, temporal attention weights, and the historic 2022 Assam monsoon backtest; and
- **Automated emergency alert simulation** testing danger-threshold protocols.

---

## 1. Project Structure

```text
AquaWatch/
├── backend/
│   ├── main.py                  # FastAPI Server (Endpoints: /health, /stations, /segment, /forecast, /simulate-alert)
│   ├── model_service.py         # In-Memory Model Cache & Leaflet GeoJSON Vectorizer
│   └── tests/
│       └── test_api.py          # API Endpoint & Integration Test Suite
│
├── models/                      # Deep Learning & ML Engines
│   ├── inference.py             # Sentinel-1 SAR U-Net Inference Engine (TTA & Sliding Window)
│   ├── model_lstm.py            # Multi-Horizon Hydrological Forecasting Engine (24h/48h/72h)
│   ├── feature_engineering.py   # Hydrological Lag & Cumulative Rainfall Transformers
│   ├── explainability.py        # Temporal Attention Maps & Monsoon Backtest Generator
│   ├── unet_resnet34_best.pt    # Serialized U-Net Flood Extent Checkpoint (~98 MB)
│   ├── lstm_best.pt             # Serialized Stacked LSTM Forecaster Checkpoint
│   └── scaler_params.npy        # Standardized Feature Normalization Scalers
│
├── frontend/                    # React + Leaflet Command Center Dashboard
│   ├── src/
│   │   ├── components/          # Modular UI Panels (Basin Map, 72h Chart, KPI Row, SAR Showcase)
│   │   ├── pages/               # Main Views (Dashboard, Station Detail, Evaluation, About)
│   │   └── api/client.ts        # Typed API Connector
│   └── package.json             # Frontend Toolchain & Scripts
│
├── data/                        # Curated Telemetry & Geospatial Assets
│   ├── assam_sample.tif         # Dual-Pol Sentinel-1 SAR Satellite Scene (10m VV/VH)
│   └── processed/               # CWC Water Level Telemetry & IMD Rainfall Series
│
├── outputs/                     # Benchmark Metrics, Comparison Curves & Backtests
│   └── explainability/          # Model Comparison, Attention Heatmaps, Backtest Plots
│
├── run_all.py                   # Master Pipeline Runner (Data Prep → Training → Evaluation)
└── requirements.txt             # Python Dependencies
```

---

## 2. Configuration (`.env`)

Copy `.env.example` to `.env` to configure the application:

```bash
# Model Execution Mode
USE_MOCK_DATA=false
USE_MOCK_MODELS=false

# SAR Segmentation Configuration
SEGMENTATION_MODEL=models/unet_resnet34_best.pt
SEGMENT_INPUT_PATH=data/assam_sample.tif

# Hydrological Forecasting Configuration
FORECAST_MODEL=models/lstm_best.pt

# Server Ports
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
```

### Segmentation Details & Assumptions
- **Input Bands**: 2-band GeoTIFF with Band 1 = VV and Band 2 = VH.
- **Normalization**: Scales uint8 `[0, 255]` to `[-1.0, 1.0]` via `(x / 255.0 - 0.5) / 0.5`.
- **Sliding Window**: 256-pixel window with stride 64.
- **Test-Time Augmentation (TTA)**: Horizontal flip augmentation (infers original and horizontally flipped scene, flips back, and averages probabilities).
- **Threshold**: Binary flood mask generated at probability `0.40`.
- **Georeferencing**: Preserves the GeoTIFF affine transform and projects coordinates to WGS84 (`EPSG:4326`) for Leaflet display. If an unreferenced scene is passed, the prediction PNG is still served while a clear warning note is returned for map polygons.
- **Output Image**: Generates a side-by-side composite panel (Sentinel-1 VV amplitude alongside the predicted flood mask) saved to `data/outputs/predictions/` and served via `/predictions/...`.

---

## 3. Step-by-Step Setup from Scratch

To run the application, open two separate terminals from the project root:

### Terminal 1: Backend Setup & Server (Port 8000)

1. **Activate or create your Python virtual environment**:
   ```powershell
   # If creating a fresh venv:
   python -m venv .venv
   
   # Activate:
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install backend dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Verify the models and pipeline (Optional but recommended)**:
   ```powershell
   python test_pipeline.py
   python -m pytest backend/tests/test_api.py -v
   ```

4. **Start the FastAPI backend with Uvicorn**:
   ```powershell
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *The backend API will start at `http://127.0.0.1:8000`.*

---

### Terminal 2: Frontend Setup & Server (Port 5173)

1. **Install Node packages**:
   ```powershell
   cd frontend
   npm install
   ```

2. **Start the Vite development server**:
   ```powershell
   npm run dev
   ```
   *The React dashboard will be running at `http://127.0.0.1:5173`.*
   *All API calls (`/api`, `/outputs`, `/predictions`) are automatically proxied to the backend on port 8000.*

---

## 4. API Endpoints

- `GET /health` — Health check status.
- `GET /stations` — List Brahmaputra basin gauge stations and current risk levels.
- `GET /segment?date=YYYY-MM-DD` — Real U-Net flood segmentation (GeoJSON polygons, coverage percentage, actual acquisition date, and prediction image URL).
- `GET /forecast?station_id=<id>` — 24h, 48h, 72h LSTM water-level forecasts and risk factors.
- `GET /evaluation-summary` — Model comparison metrics and explainability plot paths.
- `GET /predictions/<filename>` — Static serving of generated U-Net side-by-side panels.
- `POST /simulate-alert` — Emergency alert threshold testing.
