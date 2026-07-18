"""Health endpoint 契約測試（controller-api.yaml HealthResponse／error-response schema）。"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

HEALTH_FIELDS = {"status", "docker_status"}
ERROR_FIELDS = {"error_code", "message", "correlation_id", "retryable"}


def test_liveness_returns_200_with_contract_fields(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == HEALTH_FIELDS
    assert body["status"] == "OK"
    assert body["docker_status"] in {"AVAILABLE", "UNAVAILABLE"}


def test_liveness_stays_200_when_docker_down(
    client: TestClient, docker_client_mock: MagicMock
) -> None:
    docker_client_mock.ping.side_effect = Exception("engine down")
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["docker_status"] == "UNAVAILABLE"


def test_readiness_ok_when_docker_available(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "OK", "docker_status": "AVAILABLE"}


def test_readiness_503_docker_unavailable(
    client: TestClient, docker_client_mock: MagicMock
) -> None:
    docker_client_mock.ping.side_effect = Exception("engine down")
    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert ERROR_FIELDS <= set(body)
    assert body["error_code"] == "DOCKER_UNAVAILABLE"
    assert body["retryable"] is True
    assert body["correlation_id"]


def test_error_response_has_no_forbidden_fields(
    client: TestClient, docker_client_mock: MagicMock
) -> None:
    docker_client_mock.ping.side_effect = Exception("engine down")
    body = client.get("/health/ready").json()
    forbidden = {
        "stack_trace",
        "docker_socket_path",
        "secret",
        "token",
        "host_absolute_path",
        "raw_exception",
    }
    assert forbidden.isdisjoint(body)


def test_correlation_id_header_roundtrip(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Correlation-Id": "test-cid-001"})
    assert response.headers["X-Correlation-Id"] == "test-cid-001"
