import os
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "True").lower() in ("true", "1", "yes")
USE_MOCK_MODELS = os.getenv("USE_MOCK_MODELS", "True").lower() in ("true", "1", "yes")

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

    base_dt = datetime(2026, 1, 1)
    delta_days = (dt - base_dt).days
    acq_days = delta_days - (delta_days % 6)
    acq_dt = base_dt + timedelta(days=acq_days)

    mask_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[94.90, 27.45], [94.95, 27.45], [94.95, 27.50], [94.90, 27.50], [94.90, 27.45]]],
                },
                "properties": {"location": "Near Dibrugarh", "type": "flood_water"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[91.70, 26.10], [91.75, 26.10], [91.75, 26.15], [91.70, 26.15], [91.70, 26.10]]],
                },
                "properties": {"location": "Near Guwahati", "type": "flood_water"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[92.75, 26.60], [92.85, 26.60], [92.85, 26.65], [92.75, 26.65], [92.75, 26.60]]],
                },
                "properties": {"location": "Near Tezpur", "type": "flood_water"},
            },
        ],
    }

    return {
        "date": date,
        "mask_geojson": mask_geojson,
        "coverage_pct": round(12.5 + (delta_days % 5) * 1.5, 2),
        "imagery_acquisition_date": acq_dt.strftime("%Y-%m-%d"),
    }


@app.get("/forecast")
def get_forecast(station_id: str):
    station = next((item for item in STATIONS if item["station_id"] == station_id), None)
    if not station:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "detail": f"Station {station_id} not found"},
        )

    danger = station["danger_level_m"]
    current = danger - 1.5 + (len(station_id) * 0.1)

    forecasts = [
        {
            "horizon_hours": 24,
            "predicted_level_m": round(current + 0.3, 2),
            "risk_score": 0.65,
            "risk_label": get_risk_label(0.65),
            "top_factors": ["rainfall_72h", "upstream_level"],
        },
        {
            "horizon_hours": 48,
            "predicted_level_m": round(current + 0.8, 2),
            "risk_score": 0.72,
            "risk_label": get_risk_label(0.72),
            "top_factors": ["rainfall_72h", "rate_of_rise"],
        },
        {
            "horizon_hours": 72,
            "predicted_level_m": round(current + 0.5, 2),
            "risk_score": 0.68,
            "risk_label": get_risk_label(0.68),
            "top_factors": ["rainfall_72h", "seasonal_trend"],
        },
    ]

    return {
        "station_id": station_id,
        "station_name": station["name"],
        "current_level_m": round(current, 2),
        "danger_level_m": danger,
        "forecasts": forecasts,
    }


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
        message = f"Simulated alert: {label} risk at {station['name']} (demo only, no real notification sent)"
    else:
        message = f"No alert threshold crossed at {station['name']} (demo only, no real notification sent)"

    return {"triggered": triggered, "message": message}


if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
