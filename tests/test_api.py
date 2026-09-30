from fastapi.testclient import TestClient

from main import app

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

    invalid = client.get('/segment?date=invalid')
    assert invalid.status_code == 400
    assert invalid.json()['error'] == 'invalid_date'


def test_alert_validation():
    response = client.post('/simulate-alert', json={'station_id': 'guwahati', 'risk_score': 0.8})
    assert response.status_code == 200
    body = response.json()
    assert body['triggered'] is True

    bad = client.post('/simulate-alert', json={'station_id': 'guwahati', 'risk_score': 2.0})
    assert bad.status_code == 400
    assert bad.json()['error'] == 'invalid_risk_score'
