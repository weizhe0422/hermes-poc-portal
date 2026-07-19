from __future__ import annotations

import json

import httpx
import pytest

from controller_e2e.api import ControllerClient
from controller_e2e.artifacts import HttpTraceWriter
from controller_e2e.contracts import ContractBundle
from controller_e2e.errors import ContractViolation

from .test_contracts import agent_instance


def _client(spec_root, tmp_path, handler):
    return ControllerClient(
        base_url="http://controller-under-test:8090",
        timeout_seconds=1,
        contracts=ContractBundle(spec_root),
        trace=HttpTraceWriter(tmp_path, "UNIT-001"),
        transport=httpx.MockTransport(handler),
    )


def test_client_validates_response_and_writes_trace(spec_root, tmp_path):
    def handler(request):
        assert request.url.path == "/v1/instances/hermes-fixture-001"
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json=agent_instance(),
        )

    with _client(spec_root, tmp_path, handler) as client:
        response = client.get_instance("hermes-fixture-001")

    assert response.status_code == 200
    record = json.loads((tmp_path / "http-trace.jsonl").read_text().strip())
    assert record["contract_validation"] == "PASS"
    assert record["test_case_id"] == "UNIT-001"


def test_client_rejects_schema_invalid_json_response(spec_root, tmp_path):
    def handler(_request):
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"state": "HEALTHY"},
        )

    with _client(spec_root, tmp_path, handler) as client:
        with pytest.raises(ContractViolation, match="violates response schema"):
            client.get_instance("hermes-fixture-001")


def test_client_rejects_non_json_content_type(spec_root, tmp_path):
    def handler(_request):
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            text="not-json",
        )

    with _client(spec_root, tmp_path, handler) as client:
        with pytest.raises(ContractViolation, match="application/json"):
            client.get_instance("hermes-fixture-001")


def test_client_rejects_a_json_lookalike_media_type(spec_root, tmp_path):
    def handler(_request):
        return httpx.Response(
            200,
            headers={"content-type": "application/json-patch+json"},
            json=agent_instance(),
        )

    with _client(spec_root, tmp_path, handler) as client:
        with pytest.raises(ContractViolation, match="application/json"):
            client.get_instance("hermes-fixture-001")


def test_client_sends_frozen_tail_query_for_managed_logs(spec_root, tmp_path):
    def handler(request):
        assert request.url.path == "/v1/instances/hermes-fixture-secret/logs"
        assert request.url.params.get("tail") == "200"
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={
                "instance_id": "hermes-fixture-secret",
                "lines": ["token=[REDACTED]"],
                "redacted": True,
            },
        )

    with _client(spec_root, tmp_path, handler) as client:
        response = client.get_instance_logs("hermes-fixture-secret", tail=200)

    assert response.status_code == 200
