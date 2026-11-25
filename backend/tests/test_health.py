"""Automated tests for the health-check endpoint. Run with: pytest"""


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_root_points_to_docs(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"
