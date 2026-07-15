import os

from fastapi.testclient import TestClient


def test_health_returns_ok() -> None:
    os.environ["DATABASE_URL"] = "sqlite://"
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"] == "TxLINE Sentinel"
    assert payload["database"] == "ok"
