from __future__ import annotations

import pytest

from controller_e2e.contracts import ContractBundle
from controller_e2e.errors import ContractViolation


def agent_instance(**overrides):
    payload = {
        "instance_id": "hermes-fixture-001",
        "template_id": "synthetic-healthy",
        "state": "HEALTHY",
        "container_status": "RUNNING",
        "hermes_status": "AVAILABLE",
        "llm_status": "AVAILABLE",
        "versions": {
            "spec_version": "0.1.0",
            "portal_version": "0.1.0",
            "controller_version": "0.1.0",
            "hermes_image": "hermes-fixture@sha256:test",
            "model_name": "synthetic-model",
            "knowledge_version": "synthetic-v1",
            "skill_version": "synthetic-v1",
        },
        "updated_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def error_response(error_code="DOCKER_UNAVAILABLE", **overrides):
    payload = {
        "error_code": error_code,
        "message": "Docker服務目前無法使用。",
        "correlation_id": "test-correlation-id",
        "retryable": True,
    }
    payload.update(overrides)
    return payload


def test_validates_external_agent_instance_references(spec_root):
    contracts = ContractBundle(spec_root)

    contracts.validate_response("getManagedInstance", 200, agent_instance())
    contracts.validate_response("listManagedInstances", 200, [agent_instance()])


def test_rejects_missing_required_agent_instance_field(spec_root):
    contracts = ContractBundle(spec_root)
    payload = agent_instance()
    del payload["versions"]

    with pytest.raises(ContractViolation, match="versions"):
        contracts.validate_response("getManagedInstance", 200, payload)


def test_enforces_rfc3339_date_time(spec_root):
    contracts = ContractBundle(spec_root)

    with pytest.raises(ContractViolation, match="date-time"):
        contracts.validate_response(
            "getManagedInstance", 200, agent_instance(updated_at="not-a-date")
        )


def test_rejects_undeclared_status(spec_root):
    contracts = ContractBundle(spec_root)

    with pytest.raises(ContractViolation, match="undeclared HTTP status 418"):
        contracts.validate_response("getManagedInstance", 418, {})


def test_validates_error_response_against_error_catalog(spec_root):
    contracts = ContractBundle(spec_root)

    contracts.validate_response(
        "getManagedInstance", 503, error_response()
    )

    with pytest.raises(ContractViolation, match="requires HTTP 404"):
        contracts.validate_response(
            "getManagedInstance",
            503,
            error_response(
                "INSTANCE_NOT_FOUND",
                message="指定的Hermes Instance尚未建立。",
                retryable=False,
            ),
        )

    with pytest.raises(ContractViolation, match="retryable"):
        contracts.validate_response(
            "getManagedInstance", 503, error_response(retryable=False)
        )

    with pytest.raises(ContractViolation, match="forbidden error fields"):
        contracts.validate_response(
            "getManagedInstance",
            503,
            error_response(details={"stack_trace": "synthetic forbidden detail"}),
        )


def test_health_contract_is_read_from_state_machine(spec_root):
    contracts = ContractBundle(spec_root)
    contracts.assert_healthy_contract(agent_instance())

    with pytest.raises(ContractViolation, match="llm_status"):
        contracts.assert_healthy_contract(
            agent_instance(llm_status="UNAVAILABLE")
        )


def test_restart_success_status_comes_from_openapi(spec_root):
    contracts = ContractBundle(spec_root)

    assert contracts.success_statuses("restartManagedInstance") == (202,)
    assert contracts.event_source_states("RESTART_REQUESTED") == (
        "HEALTHY",
        "UNHEALTHY",
        "ERROR",
    )
