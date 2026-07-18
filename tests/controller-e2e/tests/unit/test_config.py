from __future__ import annotations

import pytest

from controller_e2e.config import RunnerConfig
from controller_e2e.errors import EnvironmentBlocker


def test_controller_readiness_preflight_has_a_bounded_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CONTROLLER_READY_TIMEOUT_SECONDS", raising=False)

    config = RunnerConfig.from_env()

    assert config.controller_ready_timeout_seconds == 60.0


def test_controller_readiness_preflight_rejects_an_unbounded_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONTROLLER_READY_TIMEOUT_SECONDS", "0")

    with pytest.raises(EnvironmentBlocker, match="greater than zero"):
        RunnerConfig.from_env()
