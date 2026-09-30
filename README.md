# AquaWatch Flood

AquaWatch is a local demo dashboard for flood awareness in Assam and the
Brahmaputra basin. It combines a FastAPI backend with a React, Leaflet, and
Recharts frontend to display:

- flood extent on a map (real U-Net inference when configured, otherwise deterministic demo data);
- five Brahmaputra monitoring stations and their risk levels;
- 24-hour, 48-hour, and 72-hour water-level forecasts;
- forecast contributing factors and danger-level reference lines; and
- a clearly labelled simulated alert action.

The application is intentionally mock-first. It does not require Earth Engine
credentials, a database, cloud deployment, or external model files to run the
demo. The API response contracts remain stable when model adapters are used.
When `USE_MOCK_MODELS=false`, the backend lazily attempts to use compatible
artifacts under `models/` and a scene selected by `SEGMENT_INPUT_PATH`.
Missing or incompatible artifacts are logged and use deterministic demo data;
models are never trained during backend startup.

## Project structure

```text
AquaWatch Flood/
├── backend/
│   ├── main.py              # Complete FastAPI backend and mock API
│   ├── requirements.txt     # Backend Python dependencies
│   └── tests/test_api.py    # Focused backend API tests
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Routes and application shell
│   │   ├── pages/           # Dashboard, station detail, and About views
│   │   └── api/client.ts    # Typed API client
│   └── package.json
├── data/                    # Local raw and processed inputs
├── models/                  # Forecasting and segmentation modules
├── .env.example             # Local configuration template
└── run_app.bat              # Windows backend launcher
```

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer and npm

The backend dependencies are listed in [backend/requirements.txt](backend/requirements.txt).
The frontend dependencies are listed in [frontend/package.json](frontend/package.json).

## Run the backend

From the repository root on Windows, create and activate a virtual environment
(recommended), then install the backend dependencies:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Alternatively, double-click [run_app.bat](run_app.bat). The API is available
at `http://127.0.0.1:8000`.

The backend is intentionally contained in the single
[backend/main.py](backend/main.py) entrypoint. It serves the API and, when a
production frontend build exists, can also serve `frontend/dist`.

The virtual environment is not technically mandatory, but it is strongly
recommended. It keeps FastAPI, Uvicorn, PyTorch, and the other project
packages isolated from other Python projects. If you do not want to use one,
run `python -m pip install -r backend/requirements.txt` from the repository
root instead.

## Run the frontend

Install frontend dependencies and start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` in a browser. The Vite proxy sends `/api/*`
requests to the backend at `http://127.0.0.1:8000`. The supported frontend
workflow is `npm install` followed by `npm run dev`.

To create a production frontend build:

```powershell
npm run build
```

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Backend readiness check |
| `GET` | `/stations` | Five station summaries and current risk labels |
| `GET` | `/segment?date=YYYY-MM-DD` | U-Net GeoJSON overlay when configured, otherwise demo overlay |
| `GET` | `/forecast?station_id=guwahati` | Current level and 24/48/72-hour forecast |
| `POST` | `/simulate-alert` | Demo alert action for a station and risk score |

Example requests:

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe "http://127.0.0.1:8000/forecast?station_id=guwahati"
curl.exe -X POST http://127.0.0.1:8000/simulate-alert `
  -H "Content-Type: application/json" `
  -d '{"station_id":"guwahati","risk_score":0.8}'
```

Invalid dates, unknown stations, and out-of-range risk scores return explicit
JSON errors with `error` and `detail` fields.

## Run tests

From the backend directory:

```powershell
cd backend
python -m pytest tests/test_api.py -q
```

From `frontend/`:

```powershell
npm run build
npm run lint
```

## Configuration and limitations

Copy [.env.example](.env.example) to `.env` when local overrides are needed.
The default configuration enables mock data and mock models.

This is a local demonstration system:

- mock data is deterministic and held in memory;
- Sentinel-1 imagery is represented by a mock overlay and is not real-time;
- the displayed imagery acquisition date may differ from the selected date;
- simulated alerts do not send SMS, email, or push notifications;
- there is no authentication, database, or cloud deployment layer; and
- Member 1's U-Net checkpoint is loaded only when `USE_MOCK_MODELS=false` and
  `SEGMENT_INPUT_PATH` points to a two-band `.tif`/`.tiff`/`.npy` scene;
- Member 2's training pipeline is available through `run_all.py`, but training
  is an explicit offline step and never runs as part of API startup; and
- the current dashboard station IDs are different from Member 2's training
  station names, so forecast requests use the stable demo adapter until a
  station mapping and inference metadata are produced.

## Run the Member 2 training pipeline

Training is intentionally separate from server startup. From the repository
root:

```powershell
python run_all.py
```

The script writes processed data, checkpoints, metrics, and explainability
outputs under `data/processed/`, `models/`, and `outputs/`. It can be run from
any directory because it normalizes paths to the repository root. After
training, restart the backend so it can discover compatible artifacts.

See [BACKEND_SCHEMA.md](BACKEND_SCHEMA.md),
[APP_FLOW.md](APP_FLOW.md), [TRD.md](TRD.md), and
[UI_UX_DESIGN.md](UI_UX_DESIGN.md) for the detailed requirements baseline.
