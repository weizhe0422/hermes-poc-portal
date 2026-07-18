"""Health endpoint 契約測試（portal-api.yaml HealthResponse／error-response schema）。"""

from fastapi.testclient import TestClient


def test_liveness_returns_200_status_only(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}


def test_readiness_ok_with_working_database(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "OK"}


def test_correlation_id_header_roundtrip(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Correlation-Id": "test-cid-001"})
    assert response.headers["X-Correlation-Id"] == "test-cid-001"
