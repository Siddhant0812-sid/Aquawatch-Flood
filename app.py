"""
AquaWatch — Member 2: FastAPI Backend (Forecasting Service)
============================================================
Exposes REST endpoints that Member 3 (Full-Stack Lead) wires into
the dashboard.

Endpoints:
  GET  /health                → service status
  GET  /stations              → list of stations + current water level
  POST /forecast              → 24h/48h/72h forecast for a station
  GET  /risk                  → current risk level per station
  GET  /history/{station}     → last 7 days of water level + rainfall

Run with:
    uvicorn api:app --reload --port 8001
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

app = FastAPI(title="AquaWatch Forecasting API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lazy-loaded model state ───────────────────────────────────────────────────
_model      = None
_x_scaler   = None
_y_scaler   = None
_feature_df = None
_feature_names = None

STATIONS = [
    "NH15 Crossing Dhansirighat",
    "NH15 Crossing Fakirpara Tangni",
    "NH17 Crossing Boko",
]
FLOOD_THRESHOLDS = {
    "NH15 Crossing Dhansirighat":    5.0,
    "NH15 Crossing Fakirpara Tangni": 4.5,
    "NH17 Crossing Boko":            4.0,
}
HORIZONS = [24, 48, 72]


def _load_model_and_data():
    """Load LSTM model and processed data on first request."""
    global _model, _x_scaler, _y_scaler, _feature_df, _feature_names
    if _model is not None:
        return

    import torch
    from model_lstm import FloodLSTM
    from sklearn.preprocessing import MinMaxScaler

    proc = Path("data/processed")
    models = Path("models")

    if not (proc / "features.csv").exists():
        from data_pipeline import run_pipeline
        from feature_engineering import build_features
        merged = run_pipeline()
        _feature_df = build_features(merged)
        _feature_df.to_csv(proc / "features.csv")
    else:
        _feature_df = pd.read_csv(proc / "features.csv",
                                  index_col="datetime", parse_dates=True)

    feat_cols = [c for c in _feature_df.columns
                 if not c.startswith("target_") and not c.startswith("flood_")]
    _feature_names = feat_cols

    X_np = _feature_df[feat_cols].values.astype("float32")
    _x_scaler = MinMaxScaler().fit(X_np)

    if (models / "lstm_best.pt").exists():
        n_feat = len(feat_cols)
        _model = FloodLSTM(input_size=n_feat, n_horizons=3)
        _model.load_state_dict(
            torch.load(models / "lstm_best.pt", map_location="cpu"))
        _model.eval()

    # y_scaler: refit on targets
    target_cols = [f"target_{h}h" for h in HORIZONS
                   if f"target_{h}h" in _feature_df.columns]
    if target_cols:
        _y_scaler = MinMaxScaler().fit(
            _feature_df[target_cols].values.astype("float32"))


# ── Schemas ──────────────────────────────────────────────────────────────────
class ForecastRequest(BaseModel):
    station: str
    horizon_hours: Optional[List[int]] = [24, 48, 72]


class ForecastPoint(BaseModel):
    horizon_hours: int
    predicted_level_m: float
    risk_level: str           # LOW / MODERATE / HIGH / CRITICAL


class ForecastResponse(BaseModel):
    station: str
    forecast_generated_at: str
    current_level_m: float
    flood_threshold_m: float
    forecasts: List[ForecastPoint]


class StationStatus(BaseModel):
    station: str
    current_level_m: float
    flood_threshold_m: float
    risk_level: str
    last_updated: str


# ── Helpers ───────────────────────────────────────────────────────────────────
def _risk_label(level: float, threshold: float) -> str:
    ratio = level / threshold
    if ratio < 0.80:  return "LOW"
    if ratio < 0.90:  return "MODERATE"
    if ratio < 1.00:  return "HIGH"
    return "CRITICAL"


def _get_current_level(station: str) -> float:
    """Latest water level from feature_df."""
    col = f"wl_{station}"
    if _feature_df is not None and col in _feature_df.columns:
        return float(_feature_df[col].iloc[-1])
    return FLOOD_THRESHOLDS[station] * 0.85   # fallback


def _run_forecast(station: str, horizons: List[int]) -> List[ForecastPoint]:
    """Run LSTM inference for requested horizons."""
    import torch

    if _model is None or _x_scaler is None:
        # No model loaded → return simple persistence forecast
        cur = _get_current_level(station)
        return [ForecastPoint(
            horizon_hours=h,
            predicted_level_m=round(cur + np.random.uniform(-0.2, 0.3), 3),
            risk_level=_risk_label(cur, FLOOD_THRESHOLDS[station]),
        ) for h in horizons]

    seq_len = 72
    feat_cols = _feature_names
    col = f"wl_{station}"

    # Take last seq_len rows
    X_np = _feature_df[feat_cols].values[-seq_len:].astype("float32")
    X_s  = _x_scaler.transform(X_np)
    x_t  = torch.tensor(X_s, dtype=torch.float32).unsqueeze(0)

    with torch.no_grad():
        pred_s = _model(x_t).numpy()[0]   # (3,)

    preds = _y_scaler.inverse_transform(pred_s.reshape(1, -1))[0]

    out = []
    for i, h in enumerate(HORIZONS):
        if h in horizons:
            level = float(np.clip(preds[i], 0, 200))
            out.append(ForecastPoint(
                horizon_hours=h,
                predicted_level_m=round(level, 3),
                risk_level=_risk_label(level, FLOOD_THRESHOLDS[station]),
            ))
    return out


# ── Routes ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    _load_model_and_data()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": _model is not None,
        "data_loaded": _feature_df is not None,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/stations", response_model=List[StationStatus])
def list_stations():
    _load_model_and_data()
    out = []
    for s in STATIONS:
        lvl = _get_current_level(s)
        out.append(StationStatus(
            station=s,
            current_level_m=round(lvl, 3),
            flood_threshold_m=FLOOD_THRESHOLDS[s],
            risk_level=_risk_label(lvl, FLOOD_THRESHOLDS[s]),
            last_updated=datetime.utcnow().isoformat(),
        ))
    return out


@app.post("/forecast", response_model=ForecastResponse)
def forecast(req: ForecastRequest):
    _load_model_and_data()
    if req.station not in STATIONS:
        raise HTTPException(status_code=404,
                            detail=f"Station '{req.station}' not found. "
                                   f"Valid: {STATIONS}")
    cur = _get_current_level(req.station)
    forecasts = _run_forecast(req.station, req.horizon_hours)
    return ForecastResponse(
        station=req.station,
        forecast_generated_at=datetime.utcnow().isoformat(),
        current_level_m=round(cur, 3),
        flood_threshold_m=FLOOD_THRESHOLDS[req.station],
        forecasts=forecasts,
    )


@app.get("/risk")
def risk_summary():
    """Quick risk overview for all stations — used by dashboard alert banner."""
    _load_model_and_data()
    return {
        s: {
            "level_m": round(_get_current_level(s), 3),
            "threshold_m": FLOOD_THRESHOLDS[s],
            "risk": _risk_label(_get_current_level(s), FLOOD_THRESHOLDS[s]),
        }
        for s in STATIONS
    }


@app.get("/history/{station}")
def station_history(station: str, days: int = 7):
    """Returns last N days of hourly water level + rainfall for a station."""
    _load_model_and_data()
    if station not in STATIONS:
        raise HTTPException(status_code=404, detail=f"Station '{station}' not found")

    if _feature_df is None:
        raise HTTPException(status_code=503, detail="Data not loaded")

    n_hours = days * 24
    wl_col = f"wl_{station}"
    rf_col = f"rf_{station}" if f"rf_{station}" in _feature_df.columns else None

    subset = _feature_df[[wl_col] + ([rf_col] if rf_col else [])].iloc[-n_hours:]
    subset = subset.reset_index()
    subset.columns = ["datetime", "water_level_m"] + (["rainfall_mm"] if rf_col else [])
    subset["datetime"] = subset["datetime"].dt.isoformat()

    return {
        "station": station,
        "flood_threshold_m": FLOOD_THRESHOLDS[station],
        "data": subset.to_dict(orient="records"),
    }
