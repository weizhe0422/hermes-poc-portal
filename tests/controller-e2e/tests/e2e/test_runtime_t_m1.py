"""Bundle-defined T-M1 Controller lifecycle black-box cases."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
from typing import Any

import pytest

from controller_e2e.api import ControllerClient, ValidatedResponse
from controller_e2e.cases import RuntimeCase
from controller_e2e.config import RunnerConfig
from controller_e2e.contracts import ContractBundle
from controller_e2e.errors import (
    ContractViolation,
    EnvironmentBlocker,
    ExpectedResultMismatch,
    require,
    require_equal,
    require_forbidden_values_absent,
)
from controller_e2e.polling import BoundedPoller, OrderedStatePath


def _instance_response(
    response: ValidatedResponse,
    expected_status: int,
    label: str,
) -> dict[str, Any]:
    require_equal(response.status_code, expected_status, f"{label} HTTP status")
    if not isinstance(response.payload, dict):
        raise ExpectedResultMismatch(f"{label} did not return a JSON object")
    return response.payload


def _successful_instance(response: ValidatedResponse, label: str) -> dict[str, Any]:
    return _instance_response(response, 200, label)


def _require_precondition_state(
    instance: dict[str, Any],
    expected_state: str,
    label: str,
) -> None:
    if instance.get("state") != expected_state:
        raise EnvironmentBlocker(
            f"{label} requires state={expected_state}, "
            f"received {instance.get('state')!r}"
        )


def _operation(instance: dict[str, Any], label: str) -> dict[str, Any]:
    operation = instance.get("operation")
    if not isinstance(operation, dict):
        raise ExpectedResultMismatch(f"{label} did not contain an operation object")
    return operation


def _accepted_lifecycle_instance(
    response: ValidatedResponse,
    runtime_case: RuntimeCase,
    label: str,
) -> dict[str, Any]:
    expected = runtime_case.expected
    instance = _instance_response(response, expected["accepted_status"], label)
    require_equal(
        instance.get("instance_id"),
        runtime_case.input["instance_id"],
        f"{label} instance_id",
    )
    require_equal(
        instance.get("state"),
        expected["accepted_state"],
        f"{label} state",
    )
    operation = _operation(instance, label)
    require_equal(
        operation.get("action"),
        expected["operation_action"],
        f"{label} operation.action",
    )
    if "operation_id_present" in expected:
        require_equal(
            "operation_id" in operation,
            expected["operation_id_present"],
            f"{label} operation_id presence",
        )
    return instance


def _invoke_lifecycle(
    client: ControllerClient,
    action: str,
    instance_id: str,
) -> ValidatedResponse:
    operations = {
        "START": client.start_instance,
        "STOP": client.stop_instance,
        "RESTART": client.restart_instance,
    }
    try:
        operation = operations[action]
    except KeyError as exc:
        raise ContractViolation(
            f"Frozen runtime case requests unsupported lifecycle action {action!r}"
        ) from exc
    return operation(instance_id)


def _wait_for_state(
    client: ControllerClient,
    poller: BoundedPoller,
    instance_id: str,
    expected_state: str,
    timeout_seconds: float,
    state_path: OrderedStatePath,
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
        if instance.get("state") != "ERROR":
            state_path.observe(instance.get("state"), f"poll {instance_id}")
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
    before = _successful_instance(
        controller_client.get_instance(instance_id), "RUNTIME-003 precondition"
    )
    _require_precondition_state(before, "STOPPED", "RUNTIME-003 precondition")
    accepted = _invoke_lifecycle(
        controller_client,
        runtime_case.input["action"],
        instance_id,
    )
    accepted_instance = _accepted_lifecycle_instance(
        accepted,
        runtime_case,
        "RUNTIME-003 accepted response",
    )
    start_path = OrderedStatePath(
        (
            runtime_case.expected["accepted_state"],
            "UNHEALTHY",
            runtime_case.expected["final_state"],
        )
    )
    start_path.observe(accepted_instance.get("state"), "RUNTIME-003 accepted response")
    final = _wait_for_state(
        controller_client,
        poller,
        instance_id,
        runtime_case.expected["final_state"],
        runner_config.start_deadline_seconds,
        start_path,
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
    test_case_id="RUNTIME-004",
    requirement_ids=("RT-04",),
    critical=True,
    assumptions=(
        "The outer isolated-Engine evidence verifies stable container identity, preserved volumes, and one Stop transition.",
    ),
)
def test_runtime_004_stops_healthy_instance_without_removal(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
    poller: BoundedPoller,
    runner_config: RunnerConfig,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    before = _successful_instance(
        controller_client.get_instance(instance_id), "RUNTIME-004 precondition"
    )
    _require_precondition_state(before, "HEALTHY", "RUNTIME-004 precondition")

    accepted = _invoke_lifecycle(
        controller_client,
        runtime_case.input["action"],
        instance_id,
    )
    accepted_instance = _accepted_lifecycle_instance(
        accepted,
        runtime_case,
        "RUNTIME-004 accepted response",
    )
    stop_path = OrderedStatePath(
        (
            runtime_case.expected["accepted_state"],
            runtime_case.expected["final_state"],
        )
    )
    stop_path.observe(accepted_instance["state"], "RUNTIME-004 accepted response")
    final = _wait_for_state(
        controller_client,
        poller,
        instance_id,
        runtime_case.expected["final_state"],
        runner_config.stop_timeout_seconds + runner_config.deadline_grace_seconds,
        stop_path,
    )
    require_equal(final["instance_id"], instance_id, "RUNTIME-004 final instance_id")


@pytest.mark.case(
    test_case_id="RUNTIME-005",
    requirement_ids=("RT-05",),
    critical=True,
    assumptions=(
        "The outer isolated-Engine evidence verifies stable container identity, preserved volumes, and exactly one Restart sequence.",
    ),
)
def test_runtime_005_restarts_healthy_instance_once(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
    poller: BoundedPoller,
    runner_config: RunnerConfig,
    contracts: ContractBundle,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    before = _successful_instance(
        controller_client.get_instance(instance_id), "RUNTIME-005 precondition"
    )
    _require_precondition_state(before, "HEALTHY", "RUNTIME-005 precondition")

    accepted = _invoke_lifecycle(
        controller_client,
        runtime_case.input["action"],
        instance_id,
    )
    accepted_instance = _accepted_lifecycle_instance(
        accepted,
        runtime_case,
        "RUNTIME-005 accepted response",
    )
    restart_path = OrderedStatePath(
        (
            runtime_case.expected["accepted_state"],
            "STOPPED",
            "STARTING",
            "UNHEALTHY",
            runtime_case.expected["final_state"],
        )
    )
    restart_path.observe(accepted_instance["state"], "RUNTIME-005 accepted response")
    final = _wait_for_state(
        controller_client,
        poller,
        instance_id,
        runtime_case.expected["final_state"],
        runner_config.restart_deadline_seconds,
        restart_path,
    )
    require_equal(final["instance_id"], instance_id, "RUNTIME-005 final instance_id")
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
    _require_precondition_state(before, "HEALTHY", "RUNTIME-006 precondition")
    before_list = controller_client.list_instances()
    require_equal(before_list.status_code, 200, "RUNTIME-006 list-before HTTP status")
    before_ids = sorted(instance["instance_id"] for instance in before_list.payload)

    response = _invoke_lifecycle(
        controller_client,
        runtime_case.input["action"],
        instance_id,
    )
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
    test_case_id="RUNTIME-007",
    requirement_ids=("RT-06",),
    critical=True,
    assumptions=(
        "The outer isolated-Engine evidence verifies that the idempotent Stop emitted no Stop or removal event.",
    ),
)
def test_runtime_007_stop_is_idempotent_when_stopped(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    before = _successful_instance(
        controller_client.get_instance(instance_id), "RUNTIME-007 precondition"
    )
    _require_precondition_state(before, "STOPPED", "RUNTIME-007 precondition")
    before_list = controller_client.list_instances()
    require_equal(before_list.status_code, 200, "RUNTIME-007 list-before HTTP status")
    before_ids = sorted(instance["instance_id"] for instance in before_list.payload)

    response = _invoke_lifecycle(
        controller_client,
        runtime_case.input["action"],
        instance_id,
    )
    final = _instance_response(
        response,
        runtime_case.expected["http_status"],
        "RUNTIME-007 response",
    )
    require_equal(
        final["state"],
        runtime_case.expected["final_state"],
        "RUNTIME-007 final state",
    )
    require_equal(final["instance_id"], instance_id, "RUNTIME-007 instance_id")

    after_list = controller_client.list_instances()
    require_equal(after_list.status_code, 200, "RUNTIME-007 list-after HTTP status")
    after_ids = sorted(instance["instance_id"] for instance in after_list.payload)
    require_equal(after_ids, before_ids, "RUNTIME-007 managed instance registry")
    require_equal(
        after_ids.count(instance_id),
        1,
        "RUNTIME-007 requested instance occurrence count",
    )


@pytest.mark.case(
    test_case_id="RUNTIME-008",
    requirement_ids=("RT-07",),
    critical=True,
    assumptions=(
        "The outer isolated-Engine evidence verifies that only the accepted lifecycle operation reached Docker.",
    ),
)
def test_runtime_008_serializes_parallel_lifecycle_actions(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
    contracts: ContractBundle,
    runner_config: RunnerConfig,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    before = _successful_instance(
        controller_client.get_instance(instance_id), "RUNTIME-008 precondition"
    )
    _require_precondition_state(before, "STOPPED", "RUNTIME-008 precondition")
    actions = tuple(runtime_case.input["parallel_actions"])
    require(len(actions) == 2, "RUNTIME-008 requires exactly two parallel actions")
    barrier = Barrier(len(actions))

    def invoke(action: str) -> tuple[str, ValidatedResponse]:
        barrier.wait()
        return action, _invoke_lifecycle(controller_client, action, instance_id)

    with ThreadPoolExecutor(max_workers=len(actions)) as executor:
        futures = [executor.submit(invoke, action) for action in actions]
        observations = [future.result() for future in futures]

    successful = [
        (action, response)
        for action, response in observations
        if response.status_code < 300
    ]
    expected_successes = (
        1 if runtime_case.expected["one_operation_accepted"] is True else 0
    )
    require_equal(
        len(successful),
        expected_successes,
        "RUNTIME-008 accepted operation count",
    )
    winning_action, winning_response = successful[0]
    (runner_config.results_dir / "engine-context.json").write_text(
        json.dumps(
            {
                "test_case_id": runtime_case.case_id,
                "winning_action": winning_action,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    winning_contract = contracts.lifecycle_request_outcome(
        "STOPPED", winning_action
    )
    winning_instance = _instance_response(
        winning_response,
        winning_contract["http_status"],
        f"RUNTIME-008 accepted {winning_action} response",
    )
    require_equal(
        winning_instance.get("state"),
        winning_contract["state"],
        f"RUNTIME-008 accepted {winning_action} state",
    )
    if winning_contract["operation_action"] is not None:
        require_equal(
            _operation(
                winning_instance, f"RUNTIME-008 accepted {winning_action} response"
            ).get("action"),
            winning_contract["operation_action"],
            f"RUNTIME-008 accepted {winning_action} operation.action",
        )
    conflicts = [
        response
        for _, response in observations
        if response.status_code == runtime_case.expected["conflict_http_status"]
    ]
    require_equal(len(conflicts), 1, "RUNTIME-008 conflict response count")
    require_equal(
        conflicts[0].payload["error_code"],
        runtime_case.expected["one_error_code"],
        "RUNTIME-008 conflict error_code",
    )


@pytest.mark.case(
    test_case_id="RUNTIME-009",
    requirement_ids=("RT-08",),
    critical=True,
)
def test_runtime_009_reports_start_timeout_as_resource_state(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
    poller: BoundedPoller,
    runner_config: RunnerConfig,
    contracts: ContractBundle,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    before = _successful_instance(
        controller_client.get_instance(instance_id), "RUNTIME-009 precondition"
    )
    _require_precondition_state(before, "STOPPED", "RUNTIME-009 precondition")
    accepted = _invoke_lifecycle(
        controller_client,
        runtime_case.input["action"],
        instance_id,
    )
    accepted_instance = _instance_response(
        accepted,
        runtime_case.expected["initial_http_status"],
        "RUNTIME-009 accepted response",
    )
    require_equal(
        accepted_instance["instance_id"],
        instance_id,
        "RUNTIME-009 accepted instance_id",
    )
    start_path = OrderedStatePath((accepted_instance["state"],))
    final = _wait_for_state(
        controller_client,
        poller,
        instance_id,
        runtime_case.expected["final_state"],
        runner_config.start_deadline_seconds,
        start_path,
    )

    resource_field = contracts.resource_state_error_field(
        expected_key="error_code",
        error_code=runtime_case.expected["error_code"],
    )
    require_equal(
        final.get(resource_field),
        runtime_case.expected["error_code"],
        "RUNTIME-009 resource-state error code",
    )


@pytest.mark.case(
    test_case_id="RUNTIME-012",
    requirement_ids=("RT-10", "RT-11"),
    critical=True,
    assumptions=(
        "The outer isolated-Engine evidence verifies the unmanaged fixture remained running and was not removed.",
    ),
)
def test_runtime_012_refuses_to_stop_unmanaged_fixture(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
) -> None:
    response = _invoke_lifecycle(
        controller_client,
        runtime_case.input["action"],
        runtime_case.input["instance_id"],
    )
    error = _instance_response(
        response,
        runtime_case.expected["http_status"],
        "RUNTIME-012 response",
    )
    require_equal(
        error["error_code"],
        runtime_case.expected["error_code"],
        "RUNTIME-012 error_code",
    )


@pytest.mark.case(
    test_case_id="RUNTIME-013",
    requirement_ids=("RT-13", "NF-03"),
    critical=True,
)
def test_runtime_013_redacts_forbidden_secret_from_logs(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    response = controller_client.get_instance_logs(
        instance_id,
        tail=runtime_case.input["tail"],
    )
    logs = _instance_response(
        response,
        runtime_case.expected["http_status"],
        "RUNTIME-013 response",
    )
    require_equal(logs["instance_id"], instance_id, "RUNTIME-013 instance_id")
    require_equal(
        logs["redacted"],
        runtime_case.expected["redacted"],
        "RUNTIME-013 redacted",
    )
    serialized = json.dumps(logs, ensure_ascii=False, sort_keys=True)
    require_forbidden_values_absent(
        serialized, runtime_case.forbidden, "RUNTIME-013 response"
    )


@pytest.mark.case(
    test_case_id="RUNTIME-014",
    requirement_ids=("RT-05",),
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

    accepted = _invoke_lifecycle(
        controller_client,
        runtime_case.input["action"],
        instance_id,
    )
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
    # The 202 response body is schema-bound, while the Bundle freezes only the
    # final HEALTHY state. The bounded observations and Engine events below
    # prove the Restart transition without inventing an accepted-body state.
    restart_path = OrderedStatePath(
        (
            "STOPPING",
            "STOPPED",
            "STARTING",
            "UNHEALTHY",
            runtime_case.expected["final_state"],
        )
    )
    restart_path.observe(
        accepted_instance.get("state"), "RUNTIME-014 accepted response"
    )
    final = _wait_for_state(
        controller_client,
        poller,
        instance_id,
        runtime_case.expected["final_state"],
        runner_config.restart_deadline_seconds,
        restart_path,
    )
    contracts.assert_healthy_contract(final)


@pytest.mark.case(
    test_case_id="RUNTIME-017",
    requirement_ids=("RT-06",),
    critical=True,
    assumptions=(
        "The first Restart request establishes the frozen case precondition; outer isolated-Engine evidence verifies both API requests produced only one Restart sequence.",
    ),
)
def test_runtime_017_reuses_running_restart_operation(
    runtime_case: RuntimeCase,
    controller_client: ControllerClient,
    poller: BoundedPoller,
    runner_config: RunnerConfig,
    contracts: ContractBundle,
) -> None:
    instance_id = runtime_case.input["instance_id"]
    expected_states = tuple(runtime_case.expected["state"])

    def accepted_restart(response: ValidatedResponse, label: str) -> dict[str, Any]:
        instance = _instance_response(
            response,
            runtime_case.expected["http_status"],
            label,
        )
        require_equal(instance["instance_id"], instance_id, f"{label} instance_id")
        require(
            instance["state"] in expected_states,
            f"{label} state: expected one of {expected_states!r}, "
            f"received {instance['state']!r}",
        )
        operation = _operation(instance, label)
        require_equal(
            operation["action"],
            runtime_case.expected["operation_action"],
            f"{label} operation.action",
        )
        return instance

    first = accepted_restart(
        _invoke_lifecycle(
            controller_client,
            runtime_case.input["action"],
            instance_id,
        ),
        "RUNTIME-017 precondition Restart",
    )
    repeated = accepted_restart(
        _invoke_lifecycle(
            controller_client,
            runtime_case.input["action"],
            instance_id,
        ),
        "RUNTIME-017 repeated Restart",
    )
    first_operation = _operation(first, "RUNTIME-017 precondition Restart")
    repeated_operation = _operation(repeated, "RUNTIME-017 repeated Restart")
    if runtime_case.expected["same_operation_id"] is True:
        require_equal(
            repeated_operation["operation_id"],
            first_operation["operation_id"],
            "RUNTIME-017 operation_id",
        )
    else:
        require(
            repeated_operation["operation_id"] != first_operation["operation_id"],
            "RUNTIME-017 operation_id unexpectedly remained the same",
        )

    restart_path = OrderedStatePath(
        (
            expected_states[0],
            "STOPPED",
            *expected_states[1:],
            "UNHEALTHY",
            runtime_case.expected["final_state"],
        )
    )
    restart_path.observe(first["state"], "RUNTIME-017 precondition Restart")
    restart_path.observe(repeated["state"], "RUNTIME-017 repeated Restart")
    final = _wait_for_state(
        controller_client,
        poller,
        instance_id,
        runtime_case.expected["final_state"],
        runner_config.restart_deadline_seconds,
        restart_path,
    )
    contracts.assert_healthy_contract(final)
