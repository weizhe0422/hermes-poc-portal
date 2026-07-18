"""Bundle-defined T-M1 Controller lifecycle black-box cases."""

from __future__ import annotations

from typing import Any

import pytest

from controller_e2e.api import ControllerClient, ValidatedResponse
from controller_e2e.cases import RuntimeCase
from controller_e2e.config import RunnerConfig
from controller_e2e.contracts import ContractBundle
from controller_e2e.errors import (
    EnvironmentBlocker,
    ExpectedResultMismatch,
    require_equal,
)
from controller_e2e.polling import BoundedPoller


def _instance_response(
    response: ValidatedResponse,
    expected_status: int,
    label: str,
) -> dict[str, Any]:
    require_equal(response.status_code, expected_status, f"{label} HTTP status")
    if not isinstance(response.payload, dict):
        raise ExpectedResultMismatch(f"{label} did not return an AgentInstance object")
    return response.payload


def _successful_instance(response: ValidatedResponse, label: str) -> dict[str, Any]:
    return _instance_response(response, 200, label)


def _wait_for_state(
    client: ControllerClient,
    poller: BoundedPoller,
    instance_id: str,
    expected_state: str,
    timeout_seconds: float,
    allowed_intermediate_states: frozenset[str],
) -> dict[str, Any]:
    def fetch() -> dict[str, Any]:
        response = client.get_instance(instance_id)
        if response.status_code == 503:
            # getManagedInstance explicitly contracts a schema-valid 503 while
            # Docker, Hermes, or the LLM probe is temporarily unavailable.
            return {
                "_transient_http_status": 503,
                "_transient_error": response.payload,
            }
        instance = _successful_instance(response, f"poll {instance_id}")
        require_equal(
            instance.get("instance_id"),
            instance_id,
            f"poll {instance_id} instance_id",
        )
        return instance

    def terminal_failure(instance: dict[str, Any]) -> str | None:
        state = instance.get("state")
        if state is None and instance.get("_transient_http_status") == 503:
            return None
        if state == "ERROR" and state != expected_state:
            return (
                f"state={state}, "
                f"last_error_code={instance.get('last_error_code')}"
            )
        if state != expected_state and state not in allowed_intermediate_states:
            return f"illegal intermediate state={state!r}"
        return None

    result = poller.until(
        fetch=fetch,
        accepted=lambda instance: instance.get("state") == expected_state,
        timeout_seconds=timeout_seconds,
        description=f"{instance_id} reaching {expected_state}",
        terminal_failure=terminal_failure,
    )
    return result.value


@pytest.mark.case(
    test_case_id="RUNTIME-001",
    requirement_ids=("RT-01", "RT-02"),
    critical=True,
)
def test_runtime_001_reports_stopped_managed_instance(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    response = controller_client.get_instance(instance_id)
    instance = _instance_response(
        response,
        runtime_case.expected["http_status"],
        "RUNTIME-001",
    )
    require_equal(instance["instance_id"], instance_id, "RUNTIME-001 instance_id")
    require_equal(instance["state"], runtime_case.expected["state"], "RUNTIME-001 state")
    require_equal(
        instance["container_status"],
        runtime_case.expected["container_status"],
        "RUNTIME-001 container_status",
    )


@pytest.mark.case(
    test_case_id="RUNTIME-003",
    requirement_ids=("RT-03", "RT-09"),
    critical=True,
)
def test_runtime_003_starts_stopped_instance_to_healthy(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
    poller: BoundedPoller,
    runner_config: RunnerConfig,
    contracts: ContractBundle,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    accepted = controller_client.start_instance(instance_id)
    require_equal(
        accepted.status_code,
        runtime_case.expected["accepted_status"],
        "RUNTIME-003 accepted HTTP status",
    )
    accepted_instance = _instance_response(
        accepted,
        runtime_case.expected["accepted_status"],
        "RUNTIME-003 accepted response",
    )
    require_equal(
        accepted_instance.get("instance_id"),
        instance_id,
        "RUNTIME-003 accepted instance_id",
    )
    require_equal(
        accepted_instance.get("state"),
        "STARTING",
        "RUNTIME-003 START_REQUESTED transition",
    )
    final = _wait_for_state(
        controller_client,
        poller,
        instance_id,
        runtime_case.expected["final_state"],
        runner_config.start_deadline_seconds,
        frozenset({"STARTING", "UNHEALTHY"}),
    )
    require_equal(
        final["hermes_status"],
        runtime_case.expected["hermes_status"],
        "RUNTIME-003 hermes_status",
    )
    require_equal(
        final["llm_status"],
        runtime_case.expected["llm_status"],
        "RUNTIME-003 llm_status",
    )
    contracts.assert_healthy_contract(final)


@pytest.mark.case(
    test_case_id="RUNTIME-006",
    requirement_ids=("RT-06",),
    critical=True,
    assumptions=(
        "The managed-instance registry is the only contracted black-box evidence that no duplicate instance was created.",
    ),
)
def test_runtime_006_start_is_idempotent_when_healthy(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
    contracts: ContractBundle,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    before = _successful_instance(
        controller_client.get_instance(instance_id), "RUNTIME-006 precondition"
    )
    require_equal(before["state"], "HEALTHY", "RUNTIME-006 precondition state")
    before_list = controller_client.list_instances()
    require_equal(before_list.status_code, 200, "RUNTIME-006 list-before HTTP status")
    before_ids = sorted(instance["instance_id"] for instance in before_list.payload)

    response = controller_client.start_instance(instance_id)
    require_equal(
        response.status_code,
        runtime_case.expected["http_status"],
        "RUNTIME-006 HTTP status",
    )
    require_equal(
        response.payload["state"],
        runtime_case.expected["final_state"],
        "RUNTIME-006 final state",
    )
    require_equal(
        response.payload["instance_id"],
        instance_id,
        "RUNTIME-006 response instance_id",
    )
    contracts.assert_healthy_contract(response.payload)

    after_list = controller_client.list_instances()
    require_equal(after_list.status_code, 200, "RUNTIME-006 list-after HTTP status")
    after_ids = sorted(instance["instance_id"] for instance in after_list.payload)
    require_equal(after_ids, before_ids, "RUNTIME-006 managed instance registry")
    require_equal(
        after_ids.count(instance_id),
        1,
        "RUNTIME-006 requested instance occurrence count",
    )


@pytest.mark.case(
    test_case_id="RUNTIME-014",
    requirement_ids=("RT-05", "NF-05"),
    critical=True,
    assumptions=(
        "The hermes-fixture-persistent health probe becomes AVAILABLE after restart only when its volume marker remains present.",
    ),
)
def test_runtime_014_restart_preserves_marker_gated_fixture(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
    poller: BoundedPoller,
    runner_config: RunnerConfig,
    contracts: ContractBundle,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    before = _successful_instance(
        controller_client.get_instance(instance_id), "RUNTIME-014 precondition"
    )
    restartable_states = contracts.event_source_states("RESTART_REQUESTED")
    if before["state"] not in restartable_states:
        raise EnvironmentBlocker(
            f"RUNTIME-014 fixture must begin in one of {restartable_states}; "
            f"received {before['state']!r}"
        )

    accepted = controller_client.restart_instance(instance_id)
    declared_success = contracts.success_statuses("restartManagedInstance")
    require_equal(
        declared_success,
        (202,),
        "Controller OpenAPI Restart success statuses",
    )
    require_equal(
        accepted.status_code,
        declared_success[0],
        "RUNTIME-014 accepted HTTP status",
    )
    accepted_instance = _instance_response(
        accepted,
        declared_success[0],
        "RUNTIME-014 accepted response",
    )
    require_equal(
        accepted_instance.get("instance_id"),
        instance_id,
        "RUNTIME-014 accepted instance_id",
    )
    require_equal(
        accepted_instance.get("state"),
        "STOPPING",
        "RUNTIME-014 RESTART_REQUESTED transition",
    )
    final = _wait_for_state(
        controller_client,
        poller,
        instance_id,
        runtime_case.expected["final_state"],
        runner_config.restart_deadline_seconds,
        frozenset({"STOPPING", "STOPPED", "STARTING", "UNHEALTHY"}),
    )
    contracts.assert_healthy_contract(final)
