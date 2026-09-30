"""Optional model integration for the API.

The service deliberately loads models lazily.  A demo checkout can therefore
start without PyTorch, raster inputs, or forecast checkpoints and still
return the stable deterministic API responses.
"""

from __future__ import annotations

import os
import logging
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

    @staticmethod
    def _label(score: float) -> str:
        return "LOW" if score < 0.4 else "MODERATE" if score < 0.7 else "HIGH"

    def segment(self, date: str) -> dict[str, Any]:
        """Run U-Net when an explicitly configured compatible scene exists."""
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
        if not configured:
            return None
        path = Path(configured)
        return path if path.is_absolute() else self.project_root / path

    def _real_segment(self, date: str, scene: Path, artifact: Path) -> dict[str, Any]:
        import numpy as np
        from rasterio.features import shapes

        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))
        from models.inference import load_input, load_model, predict_scene

        image, profile = load_input(scene)
        model, device = load_model(artifact)
        probability = predict_scene(model, image, device)
        mask = probability >= 0.5
        geometries = []
        for geometry, value in shapes(mask.astype(np.uint8), mask=mask):
            if value:
                geometries.append({"type": "Feature", "geometry": geometry, "properties": {"type": "flood_water"}})
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
        # Forecast checkpoints are not self-describing; require the companion
        # scaler files produced by model_lstm.py before attempting inference.
        model_path = self._model_path("FORECAST_MODEL", "lstm_best.pt")
        x_params = self.project_root / "models" / "x_scaler_params.npy"
        y_params = self.project_root / "models" / "y_scaler_params.npy"
        if not model_path.exists() or not x_params.exists() or not y_params.exists():
            raise FileNotFoundError("LSTM checkpoint or scaler metadata is unavailable")
        raise RuntimeError("No station feature mapping is available for this API station")

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
            features.append({"type": "Feature", "geometry": {"type": "Polygon",
                "coordinates": [[[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]]]},
                "properties": {"location": location, "type": "flood_water"}})
        return {"date": date, "mask_geojson": {"type": "FeatureCollection", "features": features},
                "coverage_pct": round(12.5 + (delta_days % 5) * 1.5, 2),
                "imagery_acquisition_date": acquisition.strftime("%Y-%m-%d")}

    def _mock_forecast(self, station: dict[str, Any]) -> dict[str, Any]:
        danger = station["danger_level_m"]
        current = danger - 1.5 + len(station["station_id"]) * 0.1
        values = [(24, 0.3, 0.65, ["rainfall_72h", "upstream_level"]),
                  (48, 0.8, 0.72, ["rainfall_72h", "rate_of_rise"]),
                  (72, 0.5, 0.68, ["rainfall_72h", "seasonal_trend"])]
        forecasts = [{"horizon_hours": h, "predicted_level_m": round(current + offset, 2),
                      "risk_score": score, "risk_label": self._label(score), "top_factors": factors}
                     for h, offset, score, factors in values]
        return {"station_id": station["station_id"], "station_name": station["name"],
                "current_level_m": round(current, 2), "danger_level_m": danger, "forecasts": forecasts}
