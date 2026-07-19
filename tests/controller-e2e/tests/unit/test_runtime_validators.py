from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from threading import Barrier, BrokenBarrierError
from types import SimpleNamespace

import pytest

from controller_e2e.api import ValidatedResponse
from controller_e2e.cases import RuntimeCaseCatalog
from controller_e2e.contracts import ContractBundle
from controller_e2e.errors import ExpectedResultMismatch
from controller_e2e.polling import BoundedPoller
from tests.e2e import test_runtime_t_m1 as runtime_e2e

from .test_contracts import agent_instance, lifecycle_operation


def _response(
    operation_id: str,
    status_code: int,
    payload: object,
) -> ValidatedResponse:
    return ValidatedResponse(
        operation_id=operation_id,
        status_code=status_code,
        payload=payload,
        elapsed_seconds=0.0,
    )


class _Runtime008Client:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0
        self.parallel_overlap_observed = False
        self._request_barrier = Barrier(2)

    def _confirm_parallel_overlap(self) -> None:
        try:
            self._request_barrier.wait(timeout=2.0)
        except BrokenBarrierError as exc:
            raise AssertionError(
                "RUNTIME-008 lifecycle requests did not overlap"
            ) from exc
        self.parallel_overlap_observed = True

    def get_instance(self, _instance_id: str) -> ValidatedResponse:
        return _response(
            "getManagedInstance",
            200,
            agent_instance(
                state="STOPPED",
                container_status="STOPPED",
                hermes_status="UNAVAILABLE",
                llm_status="UNAVAILABLE",
            ),
        )

    def start_instance(self, _instance_id: str) -> ValidatedResponse:
        self._confirm_parallel_overlap()
        self.start_calls += 1
        return _response(
            "startManagedInstance",
            202,
            agent_instance(
                state="STARTING",
                operation=lifecycle_operation("START"),
            ),
        )

    def stop_instance(self, _instance_id: str) -> ValidatedResponse:
        self._confirm_parallel_overlap()
        self.stop_calls += 1
        return _response(
            "stopManagedInstance",
            409,
            {"error_code": "OPERATION_CONFLICT"},
        )

    def restart_instance(self, _instance_id: str) -> ValidatedResponse:
        raise AssertionError("RUNTIME-008 must not invoke Restart")


def test_runtime_008_validator_runs_each_parallel_request_once_without_retry(
    spec_root: Path,
    tmp_path: Path,
) -> None:
    runtime_case = RuntimeCaseCatalog(spec_root).get("RUNTIME-008")
    client = _Runtime008Client()

    runtime_e2e.test_runtime_008_serializes_parallel_lifecycle_actions(
        runtime_case=runtime_case,
        controller_client=client,
        contracts=ContractBundle(spec_root),
        runner_config=SimpleNamespace(results_dir=tmp_path),
    )

    assert client.start_calls == 1
    assert client.stop_calls == 1
    assert client.parallel_overlap_observed is True
    context = json.loads((tmp_path / "engine-context.json").read_text())
    assert context["accepted_actions"] == ["START"]
    assert context["winning_action"] == "START"


class _ObservedInstance(dict[str, object]):
    def __init__(self, events: list[str], **values: object) -> None:
        super().__init__(values)
        self._events = events

    def get(self, key: str, default: object = None) -> object:
        if key == "last_error_code":
            self._events.append("read:last_error_code")
        return super().get(key, default)


class _Runtime009Client:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.poll_count = 0

    def get_instance(self, _instance_id: str) -> ValidatedResponse:
        if not self.events:
            self.events.append("get:STOPPED")
            payload = agent_instance(
                instance_id="hermes-fixture-slow",
                state="STOPPED",
                container_status="STOPPED",
                hermes_status="UNAVAILABLE",
                llm_status="UNAVAILABLE",
            )
        else:
            self.poll_count += 1
            state = "STARTING" if self.poll_count == 1 else "ERROR"
            self.events.append(f"get:{state}")
            payload = _ObservedInstance(
                self.events,
                **agent_instance(
                    instance_id="hermes-fixture-slow",
                    state=state,
                    last_error_code=(
                        "RUNTIME_START_TIMEOUT" if state == "ERROR" else None
                    ),
                ),
            )
        return _response("getManagedInstance", 200, payload)

    def start_instance(self, _instance_id: str) -> ValidatedResponse:
        self.events.append("start")
        return _response(
            "startManagedInstance",
            202,
            agent_instance(
                instance_id="hermes-fixture-slow",
                state="STARTING",
                operation=lifecycle_operation("START"),
            ),
        )

    def stop_instance(self, _instance_id: str) -> ValidatedResponse:
        raise AssertionError("RUNTIME-009 must not invoke Stop")

    def restart_instance(self, _instance_id: str) -> ValidatedResponse:
        raise AssertionError("RUNTIME-009 must not invoke Restart")


def test_runtime_009_waits_for_error_before_reading_last_error_code(
    spec_root: Path,
) -> None:
    client = _Runtime009Client()

    runtime_e2e.test_runtime_009_reports_start_timeout_as_resource_state(
        runtime_case=RuntimeCaseCatalog(spec_root).get("RUNTIME-009"),
        controller_client=client,
        poller=BoundedPoller(
            initial_interval_seconds=0.001,
            max_interval_seconds=0.001,
            backoff_multiplier=1.0,
        ),
        runner_config=SimpleNamespace(start_deadline_seconds=1.0),
        contracts=ContractBundle(spec_root),
    )

    assert client.events.index("get:ERROR") < client.events.index(
        "read:last_error_code"
    )


class _Runtime017Client:
    def __init__(self, operation_ids: tuple[str, str]) -> None:
        self.operation_ids = operation_ids
        self.restart_calls = 0

    def restart_instance(self, _instance_id: str) -> ValidatedResponse:
        index = self.restart_calls
        self.restart_calls += 1
        state = "STOPPING" if index == 0 else "STARTING"
        operation = lifecycle_operation("RESTART")
        operation["operation_id"] = self.operation_ids[index]
        return _response(
            "restartManagedInstance",
            202,
            agent_instance(state=state, operation=operation),
        )

    def start_instance(self, _instance_id: str) -> ValidatedResponse:
        raise AssertionError("RUNTIME-017 must not invoke Start")

    def stop_instance(self, _instance_id: str) -> ValidatedResponse:
        raise AssertionError("RUNTIME-017 must not invoke Stop")

    def get_instance(self, _instance_id: str) -> ValidatedResponse:
        return _response("getManagedInstance", 200, agent_instance())


def _run_runtime_017(
    spec_root: Path,
    operation_ids: tuple[str, str],
) -> _Runtime017Client:
    client = _Runtime017Client(operation_ids)
    runtime_e2e.test_runtime_017_reuses_running_restart_operation(
        runtime_case=RuntimeCaseCatalog(spec_root).get("RUNTIME-017"),
        controller_client=client,
        poller=BoundedPoller(
            initial_interval_seconds=0.001,
            max_interval_seconds=0.001,
            backoff_multiplier=1.0,
        ),
        runner_config=SimpleNamespace(restart_deadline_seconds=1.0),
        contracts=ContractBundle(spec_root),
    )
    return client


def test_runtime_017_validator_requires_the_same_operation_id(spec_root: Path) -> None:
    client = _run_runtime_017(spec_root, ("operation-017", "operation-017"))

    assert client.restart_calls == 2
    assert len(set(client.operation_ids)) == 1


def test_runtime_017_validator_rejects_a_second_operation_id(spec_root: Path) -> None:
    with pytest.raises(ExpectedResultMismatch, match="RUNTIME-017 operation_id"):
        _run_runtime_017(spec_root, ("operation-017-a", "operation-017-b"))


def _write_fake_docker(path: Path) -> None:
    path.write_text(
        """#!/bin/sh
set -eu
command=$1
shift
case "$command" in
  ps)
    printf '%s\\n' hermes-fixture-001 hermes-fixture-persistent hermes-fixture-secret hermes-fixture-slow unmanaged-fixture-001
    ;;
  inspect)
    if [ "${1:-}" != --format ]; then exit 0; fi
    format=$2
    instance=$3
    case "$format" in
      *poc.test-run*) printf '%s\\n' unitrun ;;
      *poc.fixture*) printf '%s\\n' true ;;
      *poc.managed*)
        if [ "$instance" = unmanaged-fixture-001 ]; then printf '%s\\n' false; else printf '%s\\n' true; fi
        ;;
      *State.Running*) printf '%s\\n' true ;;
      *'.Id'*)
        if [ "$instance" = hermes-fixture-001 ]; then printf '%s\\n' baseline-id; else printf 'id-%s\\n' "$instance"; fi
        ;;
      *) printf '\\n' ;;
    esac
    ;;
  events)
    event=''
    container=''
    format=''
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --filter)
          case "$2" in event=*) event=${2#event=} ;; container=*) container=${2#container=} ;; esac
          shift 2
          ;;
        --format) format=$2; shift 2 ;;
        *) shift ;;
      esac
    done
    if [ "$event" = restart ] && [ "$container" = hermes-fixture-001 ]; then
      count=${FAKE_RESTART_EVENTS:-1}
      index=0
      while [ "$index" -lt "$count" ]; do printf 'event-%s\\n' "$index"; index=$((index + 1)); done
    elif [ "$format" = '{{json .}}' ]; then
      :
    fi
    ;;
  volume) exit 1 ;;
  run) exit 1 ;;
  *) exit 2 ;;
esac
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_runtime_017_engine_verifier(
    tmp_path: Path,
    restart_events: int,
) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin / "docker")
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join((str(fake_bin), environment["PATH"]))
    environment["FAKE_RESTART_EVENTS"] = str(restart_events)
    verifier = (
        Path(__file__).resolve().parents[4]
        / "scripts"
        / "verify-controller-e2e-engine"
    )
    return subprocess.run(
        [
            str(verifier),
            "RUNTIME-017",
            "unitrun",
            "hermes-fixture-001",
            "1",
            "baseline-id",
            "synthetic-fixture-image",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_runtime_017_engine_validator_accepts_one_logical_restart(
    tmp_path: Path,
) -> None:
    completed = _run_runtime_017_engine_verifier(tmp_path, restart_events=1)

    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(completed.stdout)
    assert evidence["logical_restart_count"] == 1
    assert evidence["verdict"] is True


def test_runtime_017_engine_validator_rejects_duplicate_restart_side_effects(
    tmp_path: Path,
) -> None:
    completed = _run_runtime_017_engine_verifier(tmp_path, restart_events=2)

    assert completed.returncode == 1, completed.stderr
    evidence = json.loads(completed.stdout)
    assert evidence["logical_restart_count"] == 2
    assert evidence["verdict"] is False
