"""Environment-backed configuration for the synthetic runtime fixture."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Optional


class FixtureMode(str, Enum):
    HEALTHY = "HEALTHY"
    SLOW_START = "SLOW_START"
    UNHEALTHY = "UNHEALTHY"
    CRASH = "CRASH"
    SECRET_LOG = "SECRET_LOG"
    PERSISTENT = "PERSISTENT"


def _number(name: str, raw: str, *, minimum: float = 0.0) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return value


def _integer(name: str, raw: str, *, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class Settings:
    mode: FixtureMode
    host: str
    port: int
    instance_id: str
    run_id: str
    model_name: str
    spec_version: str
    start_delay_seconds: float
    crash_delay_seconds: float
    crash_exit_code: int
    test_secret: str
    marker_path: Path
    marker_value: str

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "Settings":
        values = os.environ if environ is None else environ

        raw_mode = values.get("FIXTURE_MODE", FixtureMode.HEALTHY.value).strip().upper()
        try:
            mode = FixtureMode(raw_mode)
        except ValueError as exc:
            supported = ", ".join(item.value for item in FixtureMode)
            raise ValueError(f"FIXTURE_MODE must be one of: {supported}") from exc

        marker_path = Path(values.get("FIXTURE_MARKER_PATH", "/state/runtime-014.marker"))
        if not marker_path.is_absolute():
            raise ValueError("FIXTURE_MARKER_PATH must be absolute")

        host = values.get("FIXTURE_HOST", "0.0.0.0").strip()
        instance_id = values.get("FIXTURE_INSTANCE_ID", "hermes-fixture-001").strip()
        run_id = values.get("FIXTURE_RUN_ID", values.get("POC_TEST_RUN", "local")).strip()
        model_name = values.get("FIXTURE_MODEL_NAME", "synthetic-test-model").strip()
        spec_version = values.get("SPEC_VERSION", "0.1.0").strip()
        test_secret = values.get("FIXTURE_TEST_SECRET", "TEST_SECRET_123456")
        marker_value = values.get(
            "FIXTURE_MARKER_VALUE", "RUNTIME-014-PERSISTENT-MARKER"
        )

        required_text = {
            "FIXTURE_HOST": host,
            "FIXTURE_INSTANCE_ID": instance_id,
            "FIXTURE_RUN_ID": run_id,
            "FIXTURE_MODEL_NAME": model_name,
            "SPEC_VERSION": spec_version,
            "FIXTURE_TEST_SECRET": test_secret,
            "FIXTURE_MARKER_VALUE": marker_value,
        }
        for name, value in required_text.items():
            if not value:
                raise ValueError(f"{name} must not be empty")

        return cls(
            mode=mode,
            host=host,
            port=_integer(
                "FIXTURE_PORT",
                values.get("FIXTURE_PORT", "8000"),
                minimum=1,
                maximum=65535,
            ),
            instance_id=instance_id,
            run_id=run_id,
            model_name=model_name,
            spec_version=spec_version,
            start_delay_seconds=_number(
                "FIXTURE_START_DELAY_SECONDS",
                values.get("FIXTURE_START_DELAY_SECONDS", "30"),
            ),
            crash_delay_seconds=_number(
                "FIXTURE_CRASH_DELAY_SECONDS",
                values.get("FIXTURE_CRASH_DELAY_SECONDS", "0"),
            ),
            crash_exit_code=_integer(
                "FIXTURE_CRASH_EXIT_CODE",
                values.get("FIXTURE_CRASH_EXIT_CODE", "42"),
                minimum=1,
                maximum=255,
            ),
            test_secret=test_secret,
            marker_path=marker_path,
            marker_value=marker_value,
        )

    def metadata(self) -> dict[str, object]:
        return {
            "test_only": True,
            "classification": "SYNTHETIC_TEST_ONLY",
            "fixture_type": "SYNTHETIC",
            "service": "hermes-runtime-fixture",
            "fixture_version": "0.1.0",
            "spec_version": self.spec_version,
            "instance_id": self.instance_id,
            "run_id": self.run_id,
            "mode": self.mode.value,
        }
