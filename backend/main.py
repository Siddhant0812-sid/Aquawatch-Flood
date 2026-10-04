import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

try:
    from .model_service import ModelService
except ImportError:  # supports `uvicorn main:app` from backend/
    from model_service import ModelService

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "False").lower() in ("true", "1", "yes")
USE_MOCK_MODELS = os.getenv("USE_MOCK_MODELS", "False").lower() in ("true", "1", "yes")

app = FastAPI(title="AquaWatch Flood API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIONS = [
    {"station_id": "dibrugarh", "name": "Dibrugarh", "river": "Brahmaputra", "lat": 27.4728, "lon": 94.9120, "danger_level_m": 94.5},
    {"station_id": "jorhat", "name": "Jorhat", "river": "Brahmaputra", "lat": 26.7509, "lon": 94.2037, "danger_level_m": 86.0},
    {"station_id": "tezpur", "name": "Tezpur", "river": "Brahmaputra", "lat": 26.6338, "lon": 92.8013, "danger_level_m": 64.5},
    {"station_id": "guwahati", "name": "Guwahati", "river": "Brahmaputra", "lat": 26.1445, "lon": 91.7362, "danger_level_m": 49.5},
    {"station_id": "dhubri", "name": "Dhubri", "river": "Brahmaputra", "lat": 26.0220, "lon": 89.9870, "danger_level_m": 28.5},
]
MODEL_SERVICE = ModelService(PROJECT_ROOT, STATIONS, USE_MOCK_MODELS)


def get_risk_label(score: float) -> str:
    if score < 0.4:
        return "LOW"
    if score < 0.7:
        return "MODERATE"
    return "HIGH"


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        error = detail.get("error", "error")
        message = detail.get("detail", "Request failed")
    else:
        error = "error"
        message = str(detail)
    return JSONResponse(status_code=exc.status_code, content={"error": error, "detail": message})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stations")
def get_stations():
    stations_out = []
    for station in STATIONS:
        mock_score = (len(station["name"]) * 0.1) % 1.0
        stations_out.append(
            {
                "station_id": station["station_id"],
                "name": station["name"],
                "river": station["river"],
                "lat": station["lat"],
                "lon": station["lon"],
                "current_risk_level": get_risk_label(mock_score),
            }
        )
    return {"stations": stations_out}


@app.get("/segment")
def get_segment(date: str):
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_date", "detail": "Invalid date format, use YYYY-MM-DD"},
        ) from exc

    try:
        return MODEL_SERVICE.segment(date)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "model_or_input_not_found", "detail": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "inference_error", "detail": f"Segmentation inference failed: {exc}"},
        ) from exc


@app.get("/forecast")
def get_forecast(station_id: str):
    station = next((item for item in STATIONS if item["station_id"] == station_id), None)
    if not station:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "detail": f"Station {station_id} not found"},
        )

    try:
        return MODEL_SERVICE.forecast(station)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "model_or_input_not_found", "detail": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "forecast_error", "detail": f"Forecast inference failed: {exc}"},
        ) from exc


class AlertRequest(BaseModel):
    station_id: str
    risk_score: float


@app.post("/simulate-alert")
def simulate_alert(req: AlertRequest):
    station = next((item for item in STATIONS if item["station_id"] == req.station_id), None)
    if not station:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "detail": f"Station {req.station_id} not found"},
        )

    if not 0.0 <= req.risk_score <= 1.0:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_risk_score", "detail": "Risk score must be between 0.0 and 1.0"},
        )

    triggered = req.risk_score >= 0.7
    label = get_risk_label(req.risk_score)

    if triggered:
        message = f"Emergency Alert: {label} risk triggered at {station['name']} gauge"
    else:
        message = f"No emergency threshold breach detected at {station['name']} gauge"

    return {"triggered": triggered, "message": message}


@app.get("/evaluation-summary")
def get_evaluation_summary():
    comparison_file = PROJECT_ROOT / "outputs" / "explainability" / "model_comparison.csv"
    metrics = []
    if comparison_file.exists():
        import csv
        with open(comparison_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    metrics.append({
                        "model": row.get("model", ""),
                        "horizon_h": int(row.get("horizon_h", 0)),
                        "mae": round(float(row.get("MAE", 0.0)), 4),
                        "rmse": round(float(row.get("RMSE", 0.0)), 4),
                    })
                except (ValueError, TypeError):
                    continue

    return {
        "metrics": metrics,
        "segmentation": {
            "model": "ResNet-34 U-Net",
            "backbone": "ResNet34 (ImageNet pretrained encoder)",
            "input_channels": 2,
            "bands": ["VV", "VH (Sentinel-1 SAR)"],
            "resolution_m": 10.0,
            "window_size": 256,
            "stride": 64,
            "threshold": 0.40,
            "target": "Binary surface water / flood extent"
        },
        "artifacts": {
            "model_comparison_plot": "/outputs/explainability/model_comparison.png",
            "attention_lstm_plot": "/outputs/explainability/attention_lstm.png",
            "attention_tft_plot": "/outputs/explainability/attention_tft-lite.png",
            "backtest_plot": "/outputs/explainability/backtest_NH15 Crossing Dhansirighat_2022.png",
        }
    }


# Static mount for prediction images
PREDICTIONS_DIR = PROJECT_ROOT / "data" / "outputs" / "predictions"
PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/predictions", StaticFiles(directory=PREDICTIONS_DIR), name="predictions")

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
if OUTPUTS_DIR.exists():
    app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
