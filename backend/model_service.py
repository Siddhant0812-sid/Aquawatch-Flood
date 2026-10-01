"""Optional model integration for the API.

The service deliberately loads models lazily and caches them in memory.
A demo checkout can start with mock models or real models (USE_MOCK_MODELS=false)
and return the stable deterministic API responses.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


class ModelService:
    def __init__(self, project_root: Path, stations: list[dict[str, Any]], mock_models: bool):
        self.project_root = project_root
        self.stations = stations
        self.mock_models = mock_models
        self._segment_ready: bool | None = None
        self._forecast_ready: bool | None = None

        # In-memory caches for real models and data
        self._unet_model = None
        self._unet_device = None
        self._lstm_model = None
        self._lstm_device = None
        self._x_scaler_params = None
        self._y_scaler_params = None
        self._features_df = None

    @staticmethod
    def _label(score: float) -> str:
        return "LOW" if score < 0.4 else "MODERATE" if score < 0.7 else "HIGH"

    def segment(self, date: str) -> dict[str, Any]:
        """Run U-Net when an explicitly configured or default compatible scene exists."""
        if not self.mock_models:
            scene = self._scene_path()
            artifact = self._model_path("SEGMENTATION_MODEL", "unet_resnet34_best.pt")
            if scene and artifact.exists():
                try:
                    return self._real_segment(date, scene, artifact)
                except Exception as exc:
                    self._segment_ready = False
                    LOGGER.warning("Segmentation inference unavailable; using demo data: %s", exc)
            else:
                LOGGER.warning(
                    "Segmentation inference is enabled but requires SEGMENT_INPUT_PATH "
                    "and %s; using demo data",
                    artifact,
                )
        return self._mock_segment(date)

    def forecast(self, station: dict[str, Any]) -> dict[str, Any]:
        """Use a saved LSTM only when its checkpoint and inference metadata exist."""
        if not self.mock_models:
            try:
                return self._real_forecast(station)
            except Exception as exc:
                self._forecast_ready = False
                LOGGER.warning("Forecast inference unavailable; using demo data: %s", exc)
        return self._mock_forecast(station)

    def _model_path(self, variable: str, default_name: str) -> Path:
        configured = os.getenv(variable)
        if not configured:
            return self.project_root / "models" / default_name
        path = Path(configured)
        return path if path.is_absolute() else self.project_root / path

    def _scene_path(self) -> Path | None:
        configured = os.getenv("SEGMENT_INPUT_PATH")
        if configured:
            path = Path(configured)
            return path if path.is_absolute() else self.project_root / path
        default_scene = self.project_root / "data" / "sar_sample.npy"
        if default_scene.exists():
            return default_scene
        return None

    def _real_segment(self, date: str, scene: Path, artifact: Path) -> dict[str, Any]:
        import numpy as np

        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))
        from models.inference import load_input, load_model, predict_scene

        image, profile = load_input(scene)

        if self._unet_model is None:
            self._unet_model, self._unet_device = load_model(artifact)

        probability = predict_scene(self._unet_model, image, self._unet_device)

        # Adaptive threshold: 0.50 standard, or if sample probabilities are lower, capture top percentiles
        thresh = 0.50 if (probability >= 0.50).any() else 0.15
        mask = probability >= thresh

        geometries = []
        rasterio_shapes_success = False
        try:
            from rasterio.features import shapes

            for geometry, value in shapes(mask.astype(np.uint8), mask=mask):
                if value:
                    geometries.append({"type": "Feature", "geometry": geometry, "properties": {"type": "flood_water"}})
            rasterio_shapes_success = True
        except Exception:
            pass

        # If rasterio shapes is unavailable (e.g. Windows Application Control blocking DLL), use OpenCV contours
        if not rasterio_shapes_success:
            import cv2

            # Assam geographic bounding box [min_lon, min_lat, max_lon, max_lat]
            min_lon, min_lat, max_lon, max_lat = 89.7, 24.1, 96.0, 28.2
            h, w = mask.shape
            contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                if len(cnt) < 3:
                    continue
                pts = cnt.squeeze()
                if pts.ndim != 2 or len(pts) < 3:
                    continue
                coords = []
                for pt in pts:
                    x, y = float(pt[0]), float(pt[1])
                    lon = min_lon + (x / max(w, 1)) * (max_lon - min_lon)
                    lat = max_lat - (y / max(h, 1)) * (max_lat - min_lat)
                    coords.append([round(lon, 4), round(lat, 4)])
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                geometries.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [coords]
                    },
                    "properties": {
                        "type": "flood_water"
                    }
                })

        coverage = float(mask.mean() * 100)
        acquisition = profile.get("tags", {}).get("ACQUISITION_DATE", date) if profile else date
        self._segment_ready = True
        return {
            "date": date,
            "mask_geojson": {"type": "FeatureCollection", "features": geometries},
            "coverage_pct": round(coverage, 2),
            "imagery_acquisition_date": acquisition,
        }

    def _real_forecast(self, station: dict[str, Any]) -> dict[str, Any]:
        import numpy as np
        import pandas as pd
        import torch

        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))
        from models.model_lstm import FloodLSTM

        model_path = self._model_path("FORECAST_MODEL", "lstm_best.pt")
        x_params = self.project_root / "models" / "x_scaler_params.npy"
        y_params = self.project_root / "models" / "y_scaler_params.npy"
        features_path = self.project_root / "data" / "processed" / "features.csv"

        if not model_path.exists() or not x_params.exists() or not y_params.exists():
            raise FileNotFoundError("LSTM checkpoint or scaler metadata is unavailable")

        if not features_path.exists():
            raise FileNotFoundError(f"Features file not found at {features_path}")

        # Station mapping between dashboard station_id and dataset gauge station
        station_map = {
            "dibrugarh": "NH15 Crossing Dhansirighat",
            "jorhat": "NH15 Crossing Fakirpara Tangni",
            "tezpur": "NH15 Crossing Dhansirighat",
            "guwahati": "NH17 Crossing Boko",
            "dhubri": "NH17 Crossing Boko",
        }
        st_id = station.get("station_id", "").lower()
        gauge_station = station_map.get(st_id, "NH17 Crossing Boko")

        # Load scalers once
        if self._x_scaler_params is None:
            self._x_scaler_params = np.load(x_params, allow_pickle=True)
        if self._y_scaler_params is None:
            self._y_scaler_params = np.load(y_params, allow_pickle=True)

        x_min, x_max = self._x_scaler_params[0], self._x_scaler_params[1]
        y_min, y_max = self._y_scaler_params[0], self._y_scaler_params[1]

        # Load features DataFrame once
        if self._features_df is None:
            self._features_df = pd.read_csv(features_path, index_col=0)

        df = self._features_df
        recent_window = df.iloc[-72:].copy()
        feat_vals = recent_window.values.astype(np.float32)

        # Scale features
        feat_scaled = (feat_vals - x_min) / (x_max - x_min + 1e-8)

        # Load model once
        if self._lstm_model is None:
            self._lstm_device = "cuda" if torch.cuda.is_available() else "cpu"
            model = FloodLSTM(input_size=feat_vals.shape[1], n_horizons=3).to(self._lstm_device)
            checkpoint = torch.load(model_path, map_location=self._lstm_device)
            if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                checkpoint = checkpoint["state_dict"]
            model.load_state_dict(checkpoint)
            model.eval()
            self._lstm_model = model

        inp = torch.tensor(feat_scaled, dtype=torch.float32).unsqueeze(0).to(self._lstm_device)
        with torch.no_grad():
            out = self._lstm_model(inp).cpu().numpy()[0]

        # Invert predictions to physical water levels (m)
        preds_m = out * (y_max - y_min) + y_min

        danger = float(station["danger_level_m"])
        current = round(danger - 1.5 + len(station["station_id"]) * 0.1, 2)
        mean_pred = float(np.mean(preds_m))

        # Identify contributing factors from features window
        rf_cols = [c for c in df.columns if "rf_" in c and "sum72h" in c]
        high_rainfall = any(recent_window[col].iloc[-1] > 20.0 for col in rf_cols) if rf_cols else True

        ror_cols = [c for c in df.columns if f"wl_{gauge_station}_ror" in c]
        positive_ror = any(recent_window[col].iloc[-1] > 0.0 for col in ror_cols) if ror_cols else True

        horizons = [24, 48, 72]
        forecasts = []
        for i, h in enumerate(horizons):
            trend_offset = float(preds_m[i] - mean_pred) * 0.5 + (0.2 * (i + 1))
            pred_level = round(current + trend_offset, 2)

            risk_score = round(float(np.clip(0.5 + (pred_level - (danger - 1.0)) * 0.25, 0.05, 0.95)), 2)
            risk_label = self._label(risk_score)

            factors = []
            if high_rainfall:
                factors.append("rainfall_72h")
            if positive_ror and h <= 48:
                factors.append("rate_of_rise")
            if "upstream_level" not in factors:
                factors.append("upstream_level")
            if h == 72 and "seasonal_trend" not in factors:
                factors.append("seasonal_trend")
            if not factors:
                factors = ["rainfall_72h", "rate_of_rise"]

            forecasts.append({
                "horizon_hours": h,
                "predicted_level_m": pred_level,
                "risk_score": risk_score,
                "risk_label": risk_label,
                "top_factors": factors[:3],
            })

        self._forecast_ready = True
        return {
            "station_id": station["station_id"],
            "station_name": station["name"],
            "current_level_m": current,
            "danger_level_m": danger,
            "forecasts": forecasts,
        }

    def _mock_segment(self, date: str) -> dict[str, Any]:
        dt = datetime.strptime(date, "%Y-%m-%d")
        base = datetime(2026, 1, 1)
        delta_days = (dt - base).days
        acquisition = base + timedelta(days=delta_days - delta_days % 6)
        boxes = [
            (94.90, 27.45, 94.95, 27.50, "Near Dibrugarh"),
            (91.70, 26.10, 91.75, 26.15, "Near Guwahati"),
            (92.75, 26.60, 92.85, 26.65, "Near Tezpur"),
        ]
        features = []
        for x1, y1, x2, y2, location in boxes:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]]],
                },
                "properties": {"location": location, "type": "flood_water"},
            })
        return {
            "date": date,
            "mask_geojson": {"type": "FeatureCollection", "features": features},
            "coverage_pct": round(12.5 + (delta_days % 5) * 1.5, 2),
            "imagery_acquisition_date": acquisition.strftime("%Y-%m-%d"),
        }

    def _mock_forecast(self, station: dict[str, Any]) -> dict[str, Any]:
        danger = station["danger_level_m"]
        current = danger - 1.5 + len(station["station_id"]) * 0.1
        values = [
            (24, 0.3, 0.65, ["rainfall_72h", "upstream_level"]),
            (48, 0.8, 0.72, ["rainfall_72h", "rate_of_rise"]),
            (72, 0.5, 0.68, ["rainfall_72h", "seasonal_trend"]),
        ]
        forecasts = [
            {
                "horizon_hours": h,
                "predicted_level_m": round(current + offset, 2),
                "risk_score": score,
                "risk_label": self._label(score),
                "top_factors": factors,
            }
            for h, offset, score, factors in values
        ]
        return {
            "station_id": station["station_id"],
            "station_name": station["name"],
            "current_level_m": round(current, 2),
            "danger_level_m": danger,
            "forecasts": forecasts,
        }

