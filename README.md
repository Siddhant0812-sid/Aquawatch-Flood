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
AquaWatch Flood/
├── backend/
│   ├── main.py                  # FastAPI server, endpoints, and static mounts
│   ├── model_service.py         # Model integration (lazy cache, U-Net TTA, LSTM)
│   ├── requirements.txt         # Backend Python dependencies
│   └── tests/test_api.py        # Focused unit and integration tests
├── data/
│   ├── assam_sample.tif         # Georeferenced 2-band Sentinel-1 SAR GeoTIFF (VV/VH)
│   ├── sar_sample.npy           # Dual-pol SAR numpy array fallback
│   ├── raw_rainfall_cwc_assam.csv
│   ├── raw_water_level_assam.csv
│   └── processed/               # Cleaned hourly features for forecasting
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Application shell and route configuration
│   │   ├── api/client.ts        # Typed API client and response interfaces
│   │   └── pages/
│   │       ├── DashboardPage.tsx       # Live map, stations, and U-Net output panel
│   │       ├── ModelEvaluationPage.tsx # Benchmark metrics and explainability plots
│   │       ├── StationDetailPage.tsx   # 72h forecast chart and alert simulation
│   │       └── AboutPage.tsx           # Technical architecture and data sources
│   ├── package.json
│   └── vite.config.ts           # Development server with /api, /outputs, /predictions proxy
├── models/
│   ├── inference.py             # U-Net sliding window, TTA, and panel generator
│   ├── unet_resnet34_best.pt    # Trained U-Net checkpoint (~98 MB)
│   ├── model_lstm.py            # PyTorch LSTM forecasting architecture
│   ├── lstm_best.pt             # Trained multi-horizon LSTM checkpoint
│   └── x_scaler_params.npy      # Feature normalization metadata
├── outputs/
│   └── explainability/          # Model comparison CSV, attention and backtest plots
└── test_pipeline.py             # Verification script for models and pipeline
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
   pip install -r backend/requirements.txt
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
