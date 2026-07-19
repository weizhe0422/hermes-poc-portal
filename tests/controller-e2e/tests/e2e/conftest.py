from __future__ import annotations

import os

import pytest

from controller_e2e.api import ControllerClient, ValidatedResponse
from controller_e2e.artifacts import HttpTraceWriter
from controller_e2e.cases import RuntimeCase, RuntimeCaseCatalog
from controller_e2e.config import RunnerConfig
from controller_e2e.contracts import ContractBundle
from controller_e2e.errors import (
    ContractViolation,
    EnvironmentBlocker,
    ExpectedResultMismatch,
    TransportFailure,
)
from controller_e2e.polling import BoundedPoller


@pytest.fixture(autouse=True)
def outer_phase_precondition() -> None:
    """Classify an outer fixture-preparation failure without calling the SUT."""

    if os.getenv("E2E_SETUP_BLOCKER", "").strip():
        raise EnvironmentBlocker(
            "outer isolated fixture preparation did not satisfy the case precondition"
        )


@pytest.fixture(scope="session")
def runner_config() -> RunnerConfig:
    config = RunnerConfig.from_env()
    config.validate_inputs()
    config.results_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture(scope="session")
def contracts(runner_config: RunnerConfig) -> ContractBundle:
    return ContractBundle(runner_config.spec_root)


@pytest.fixture(scope="session")
def runtime_catalog(runner_config: RunnerConfig) -> RuntimeCaseCatalog:
    return RuntimeCaseCatalog(runner_config.spec_root)


@pytest.fixture
def runtime_case(
    request: pytest.FixtureRequest,
    runtime_catalog: RuntimeCaseCatalog,
) -> RuntimeCase:
    marker = request.node.get_closest_marker("case")
    if marker is None:
        raise ContractViolation("Every E2E test requires case metadata")
    case = runtime_catalog.get(marker.kwargs["test_case_id"])
    marked_requirements = tuple(marker.kwargs["requirement_ids"])
    if case.requirement_ids != marked_requirements:
        raise ContractViolation(
            f"JUnit metadata for {case.case_id} has requirements "
            f"{marked_requirements!r}, but the Bundle case has "
            f"{case.requirement_ids!r}"
        )
    if case.critical != bool(marker.kwargs["critical"]):
        raise ContractViolation(
            f"JUnit critical metadata for {case.case_id} differs from the Bundle case"
        )
    return case


@pytest.fixture
def controller_client(
    request: pytest.FixtureRequest,
    runner_config: RunnerConfig,
    contracts: ContractBundle,
):
    marker = request.node.get_closest_marker("case")
    trace = HttpTraceWriter(
        runner_config.results_dir, marker.kwargs["test_case_id"]
    )
    client = ControllerClient(
        base_url=runner_config.controller_base_url,
        timeout_seconds=runner_config.request_timeout_seconds,
        contracts=contracts,
        trace=trace,
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def poller(runner_config: RunnerConfig) -> BoundedPoller:
    return BoundedPoller(
        initial_interval_seconds=runner_config.poll_initial_interval_seconds,
        max_interval_seconds=runner_config.poll_max_interval_seconds,
        backoff_multiplier=runner_config.poll_backoff_multiplier,
    )


@pytest.fixture(scope="session", autouse=True)
def controller_readiness_preflight(
    runner_config: RunnerConfig,
    contracts: ContractBundle,
) -> None:
    """Wait for the isolated Controller and its Docker Engine, with a hard bound."""

    trace = HttpTraceWriter(runner_config.results_dir, "CONTROLLER-ENV-001")
    client = ControllerClient(
        base_url=runner_config.controller_base_url,
        timeout_seconds=runner_config.request_timeout_seconds,
        contracts=contracts,
        trace=trace,
    )
    readiness_poller = BoundedPoller[ValidatedResponse | TransportFailure](
        initial_interval_seconds=runner_config.poll_initial_interval_seconds,
        max_interval_seconds=runner_config.poll_max_interval_seconds,
        backoff_multiplier=runner_config.poll_backoff_multiplier,
    )

    def observe() -> ValidatedResponse | TransportFailure:
        try:
            return client.readiness()
        except TransportFailure as exc:
            return exc

    def ready(observation: ValidatedResponse | TransportFailure) -> bool:
        return (
            isinstance(observation, ValidatedResponse)
            and observation.status_code == 200
            and observation.payload == {
                "status": "OK",
                "docker_status": "AVAILABLE",
            }
        )

    try:
        readiness_poller.until(
            fetch=observe,
            accepted=ready,
            timeout_seconds=runner_config.controller_ready_timeout_seconds,
            description="Controller readiness",
        )
    except ExpectedResultMismatch as exc:
        raise EnvironmentBlocker(str(exc)) from exc
    finally:
        client.close()
