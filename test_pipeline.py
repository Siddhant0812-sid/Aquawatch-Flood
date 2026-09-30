"""Smoke tests for the Member 1/2 adapters and data pipeline."""

import unittest
from pathlib import Path

from models.data_pipeline import generate_synthetic_rainfall, generate_synthetic_water_level
from backend.model_service import ModelService


class TestPipeline(unittest.TestCase):
    """Keep model-adapter startup checks independent of heavyweight training."""

    def test_member_two_inputs_are_available(self):
        water_level = generate_synthetic_water_level()
        rainfall = generate_synthetic_rainfall()
        self.assertEqual(list(water_level.columns), list(rainfall.columns))
        self.assertGreater(len(water_level), 0)
        self.assertGreater(len(rainfall), 0)

    def test_backend_uses_deterministic_adapter_without_training(self):
        stations = [{
            "station_id": "guwahati",
            "name": "Guwahati",
            "danger_level_m": 49.5,
        }]
        service = ModelService(Path(__file__).resolve().parent, stations, mock_models=True)
        first = service.forecast(stations[0])
        second = service.forecast(stations[0])
        self.assertEqual(first, second)
        self.assertEqual(
            [item["horizon_hours"] for item in first["forecasts"]],
            [24, 48, 72],
        )

    def test_real_unet_segmentation(self):
        stations = [{"station_id": "guwahati", "name": "Guwahati", "danger_level_m": 49.5}]
        service = ModelService(Path(__file__).resolve().parent, stations, mock_models=False)
        result = service.segment("2026-07-30")
        self.assertEqual(result["date"], "2026-07-30")
        self.assertIn("mask_geojson", result)
        self.assertEqual(result["mask_geojson"]["type"], "FeatureCollection")
        self.assertIn("coverage_pct", result)
        self.assertIn("imagery_acquisition_date", result)

    def test_real_lstm_forecasting(self):
        stations = [{"station_id": "guwahati", "name": "Guwahati", "danger_level_m": 49.5}]
        service = ModelService(Path(__file__).resolve().parent, stations, mock_models=False)
        result = service.forecast(stations[0])
        self.assertEqual(result["station_id"], "guwahati")
        self.assertEqual(len(result["forecasts"]), 3)
        self.assertEqual([f["horizon_hours"] for f in result["forecasts"]], [24, 48, 72])
        for f in result["forecasts"]:
            self.assertIn("predicted_level_m", f)
            self.assertIn("risk_score", f)
            self.assertIn(f["risk_label"], ["LOW", "MODERATE", "HIGH"])
            self.assertTrue(len(f["top_factors"]) >= 1)


if __name__ == "__main__":
    unittest.main()
