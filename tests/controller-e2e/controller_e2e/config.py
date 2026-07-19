"""Environment-driven runner configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .errors import EnvironmentBlocker


def _positive_float(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        value = float(raw)
    except ValueError as exc:
        raise EnvironmentBlocker(f"{name} must be numeric, received {raw!r}") from exc
    if value <= 0:
        raise EnvironmentBlocker(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class RunnerConfig:
    spec_root: Path
    results_dir: Path
    controller_base_url: str
    controller_ready_timeout_seconds: float
    request_timeout_seconds: float
    start_timeout_seconds: float
    stop_timeout_seconds: float
    deadline_grace_seconds: float
    poll_initial_interval_seconds: float
    poll_max_interval_seconds: float
    poll_backoff_multiplier: float

    @classmethod
    def from_env(cls) -> "RunnerConfig":
        spec_root = Path(os.getenv("SPEC_ROOT", "/spec")).resolve()
        results_dir = Path(os.getenv("RESULTS_DIR", "/test-results")).resolve()
        base_url = os.getenv(
            "CONTROLLER_BASE_URL", "http://controller-under-test:8090"
        ).rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise EnvironmentBlocker(
                "CONTROLLER_BASE_URL must be an http:// or https:// URL"
            )

        initial_interval = _positive_float("POLL_INITIAL_INTERVAL_SECONDS", "0.1")
        maximum_interval = _positive_float("POLL_MAX_INTERVAL_SECONDS", "1.0")
        multiplier = _positive_float("POLL_BACKOFF_MULTIPLIER", "1.5")
        if initial_interval > maximum_interval:
            raise EnvironmentBlocker(
                "POLL_INITIAL_INTERVAL_SECONDS cannot exceed "
                "POLL_MAX_INTERVAL_SECONDS"
            )
        if multiplier < 1:
            raise EnvironmentBlocker("POLL_BACKOFF_MULTIPLIER must be at least 1")

        return cls(
            spec_root=spec_root,
            results_dir=results_dir,
            controller_base_url=base_url,
            controller_ready_timeout_seconds=_positive_float(
                "CONTROLLER_READY_TIMEOUT_SECONDS", "60"
            ),
            request_timeout_seconds=_positive_float(
                "E2E_HTTP_TIMEOUT_SECONDS", "10"
            ),
            start_timeout_seconds=_positive_float(
                "HERMES_START_TIMEOUT_SECONDS", "120"
            ),
            stop_timeout_seconds=_positive_float(
                "HERMES_STOP_TIMEOUT_SECONDS", "30"
            ),
            deadline_grace_seconds=_positive_float(
                "E2E_DEADLINE_GRACE_SECONDS", "5"
            ),
            poll_initial_interval_seconds=initial_interval,
            poll_max_interval_seconds=maximum_interval,
            poll_backoff_multiplier=multiplier,
        )

    def validate_inputs(self) -> None:
        required = (
            self.spec_root / "contracts" / "openapi" / "controller-api.yaml",
            self.spec_root / "contracts" / "errors" / "error-catalog.yaml",
            self.spec_root / "contracts" / "state-machines" / "hermes-runtime.yaml",
            self.spec_root / "contracts" / "schemas" / "evaluation-case.schema.json",
            self.spec_root / "test-cases" / "runtime" / "cases.yaml",
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise EnvironmentBlocker(
                "SPEC_ROOT is incomplete; missing read-only inputs: "
                + ", ".join(missing)
            )

    @property
    def restart_deadline_seconds(self) -> float:
        return (
            self.stop_timeout_seconds
            + self.start_timeout_seconds
            + self.deadline_grace_seconds
        )

    @property
    def start_deadline_seconds(self) -> float:
        return self.start_timeout_seconds + self.deadline_grace_seconds
