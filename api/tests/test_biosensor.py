def test_biosensor_contaminated_payload(client, auth_headers):
    r = client.post(
        "/api/v1/biosensor/readings",
        headers=auth_headers,
        json={
            "device_id": "sensor-0001",
            "crop_name": "coffee",
            "farm_id": 1,
            "batch_id": "batch-A",
            "payload": {
                "ochratoxin_A_ppb": 3.6,
                "moisture_pct": 13.8,
                "temperature_c": 24.0,
                "humidity_pct": 65.0,
            },
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["threat_level"] in ("warning", "critical")
    assert any(t["code"] == "ochratoxin_A_ppb" for t in body["threats"])
    assert body["risk_score"] > 0


def test_biosensor_clean_payload(client, auth_headers):
    r = client.post(
        "/api/v1/biosensor/readings",
        headers=auth_headers,
        json={
            "device_id": "sensor-0002",
            "crop_name": "maize",
            "payload": {"aflatoxin_B1_ppb": 4.0, "moisture_pct": 11.0},
        },
    )
    assert r.status_code == 201
    assert r.json()["threat_level"] == "safe"
    assert r.json()["threats"] == []


def test_biosensor_series(client, auth_headers):
    for i in range(3):
        client.post(
            "/api/v1/biosensor/readings",
            headers=auth_headers,
            json={
                "device_id": "sensor-0003",
                "crop_name": "coffee",
                "payload": {"moisture_pct": 11.0 + i},
            },
        )
    r = client.get("/api/v1/biosensor/series?device_id=sensor-0003", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["readings"]) == 3
