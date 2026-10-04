from pathlib import Path
from fastapi.testclient import TestClient

try:
    from backend.main import app, MODEL_SERVICE
except ModuleNotFoundError:
    from main import app, MODEL_SERVICE

client = TestClient(app)


def test_health_endpoint():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_station_list_and_forecast():
    stations = client.get('/stations')
    assert stations.status_code == 200
    data = stations.json()['stations']
    assert len(data) >= 1
    first = data[0]
    assert 'station_id' in first

    forecast = client.get(f"/forecast?station_id={first['station_id']}")
    assert forecast.status_code == 200
    body = forecast.json()
    assert body['station_id'] == first['station_id']
    assert len(body['forecasts']) == 3


def test_segment_and_error_shapes():
    response = client.get('/segment?date=2026-07-30')
    assert response.status_code == 200
    payload = response.json()
    assert payload['date'] == '2026-07-30'
    assert 'mask_geojson' in payload
    assert 'imagery_acquisition_date' in payload

    invalid = client.get('/segment?date=invalid')
    assert invalid.status_code == 400
    assert invalid.json()['error'] == 'invalid_date'


def test_model_service_is_deterministic_in_mock_mode():
    first = MODEL_SERVICE._mock_segment('2026-07-30')
    second = MODEL_SERVICE._mock_segment('2026-07-30')
    assert first == second
    assert first['prediction_image_url'] is None
    assert first['is_real_model'] is False

    forecast = MODEL_SERVICE._mock_forecast(
        {'station_id': 'guwahati', 'name': 'Guwahati', 'danger_level_m': 49.5}
    )
    assert [p['horizon_hours'] for p in forecast['forecasts']] == [24, 48, 72]


def test_segment_prediction_image_and_static_serving():
    response = client.get('/segment?date=2026-07-30')
    assert response.status_code == 200
    payload = response.json()

    # In real mode with assam_sample.tif or sar_sample.npy, prediction_image_url is returned
    img_url = payload.get('prediction_image_url')
    assert img_url is not None
    assert img_url.startswith('/predictions/')

    # Verify PNG is reachable via static mount and valid image content
    img_resp = client.get(img_url)
    assert img_resp.status_code == 200
    assert 'image/png' in img_resp.headers.get('content-type', '')
    assert len(img_resp.content) > 1000  # Non-trivial PNG file


def test_real_mode_missing_scene_raises_actionable_error(monkeypatch):
    monkeypatch.setenv('SEGMENT_INPUT_PATH', 'data/non_existent_scene.tif')
    response = client.get('/segment?date=2026-07-30')
    # Real mode must NOT silently fall back to mock data
    assert response.status_code == 404
    body = response.json()
    assert body['error'] == 'model_or_input_not_found'
    assert 'non_existent_scene.tif' in body['detail']


def test_alert_validation():
    response = client.post('/simulate-alert', json={'station_id': 'guwahati', 'risk_score': 0.8})
    assert response.status_code == 200
    body = response.json()
    assert body['triggered'] is True

    bad = client.post('/simulate-alert', json={'station_id': 'guwahati', 'risk_score': 2.0})
    assert bad.status_code == 400
    assert bad.json()['error'] == 'invalid_risk_score'
