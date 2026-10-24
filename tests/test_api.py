import os
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

_TEST_DB_DIR = tempfile.mkdtemp(prefix="safemap-test-")
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_TEST_DB_DIR) / "test.db").as_posix()

from main import app
from app.database import engine
from app.scoring import score_category
import pytest


@pytest.fixture(scope="session", autouse=True)
def clean_test_database():
    yield
    engine.dispose()
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


def test_health_and_static_frontend():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert "SafeMap" in client.get("/").text
        assert "SAFEMAP_API_BASE" in client.get("/app.js").text
        assert client.get("/style.css").status_code == 200


def test_locations_and_missing_location():
    with TestClient(app) as client:
        locations = client.get("/api/locations").json()
        assert locations and all(row["is_demo"] for row in locations)
        assert client.get("/api/locations/999999").status_code == 404
        safety = client.get("/api/safety/" + str(locations[0]["id"])).json()
        assert safety["status"] == "provisional"
        assert safety["data_label"] == "sample/demo inputs"


def test_safety_score_missing_data_and_boundaries():
    with TestClient(app) as client:
        insufficient = client.post("/api/safety/calculate", json={"lighting_quality": 100}).json()
        assert insufficient["status"] == "insufficient_data"
        low = client.post("/api/safety/calculate", json={"lighting_quality": 0, "incident_count": 8, "emergency_proximity": 0, "crowd_activity": 0, "safety_feedback": 0}).json()
        high = client.post("/api/safety/calculate", json={"lighting_quality": 100, "incident_count": 0, "emergency_proximity": 100, "crowd_activity": 100, "safety_feedback": 100}).json()
        assert low["safety_score"] == 0
        assert high["safety_score"] == 100
        assert client.post("/api/safety/calculate", json={"lighting_quality": 101}).status_code == 422
        assert client.get("/api/search", params={"q": "x"}).status_code == 422
        assert [score_category(value) for value in (0, 49, 50, 74, 75, 100)] == [
            "Requires Caution", "Requires Caution", "Moderate", "Moderate", "Safe", "Safe"
        ]


def test_report_validation_retrieval_and_list():
    with TestClient(app) as client:
        response = client.post("/api/reports", json={"title": "Test road hazard", "latitude": 26.9, "longitude": 75.8, "incident_type": "Road Hazard", "description": "Demo test report", "severity": 2})
        assert response.status_code == 201
        report = response.json()
        assert report["is_demo"] is False
        detail = client.get(f"/api/reports/{report['id']}").json()
        assert detail["title"] == "Test road hazard"
        assert detail["description"] == "Demo test report"
        assert any(r["id"] == report["id"] for r in client.get("/api/reports").json())
        assert client.get("/api/reports", params={"category": "Road Hazard", "skip": 0, "limit": 1}).status_code == 200
        assert client.post("/api/reports", json={"title": "Bad report", "latitude": 0, "longitude": 0, "incident_type": "Unknown", "description": "bad"}).status_code == 422
        assert client.post("/api/reports", json={"title": "Bad report", "latitude": 91, "longitude": 0, "incident_type": "Road Hazard", "description": "a"}).status_code == 422


def test_nearby_facilities_and_sos_validation():
    with TestClient(app) as client:
        nearby = client.get("/api/facilities/nearby", params={"latitude": 26.9124, "longitude": 75.7873, "radius_km": 10})
        assert nearby.status_code == 200 and nearby.json()
        assert nearby.json()[0]["distance_km"] >= 0
        zones = client.get("/api/locations/nearby", params={"latitude": 26.9124, "longitude": 75.7873}).json()
        assert zones and zones[0]["distance_km"] == 0
        assert client.post("/api/sos", json={"latitude": 200, "longitude": 0}).status_code == 422
        response = client.post("/api/sos", json={"latitude": 26.9, "longitude": 75.8})
        assert response.status_code == 201
        assert response.json()["status"] == "recorded_locally"


def test_report_not_found():
    with TestClient(app) as client:
        assert client.get("/api/reports/999999").status_code == 404
