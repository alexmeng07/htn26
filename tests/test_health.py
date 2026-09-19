"""GET /health is what we check before every demo run."""

from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


def test_health_reports_every_service():
    body = client.get("/health").json()
    assert set(body["services"]) == {"omni", "openai", "elevenlabs", "baseten", "mongodb"}


def test_health_never_raises_when_keys_are_missing():
    body = client.get("/health").json()
    assert isinstance(body["ok"], bool)


def test_scene_route_serves_the_active_pack():
    body = client.get("/scene").json()
    assert body["scene_id"]
    assert "thresholds" in body
