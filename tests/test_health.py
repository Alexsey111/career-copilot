from fastapi.testclient import TestClient

from app.main import app


def test_healthcheck() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_liveness() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "career-copilot",
        "status": "ok",
    }
