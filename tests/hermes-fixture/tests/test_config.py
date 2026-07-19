from __future__ import annotations

import pytest

from hermes_fixture.config import FixtureMode, Settings


@pytest.mark.parametrize("mode", list(FixtureMode))
def test_every_documented_mode_parses(mode, tmp_path):
    settings = Settings.from_env(
        {
            "FIXTURE_MODE": mode.value.lower(),
            "FIXTURE_MARKER_PATH": str(tmp_path / "marker"),
        }
    )
    assert settings.mode is mode


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("FIXTURE_MODE", "UNKNOWN", "FIXTURE_MODE must be one of"),
        ("FIXTURE_PORT", "0", "FIXTURE_PORT must be between"),
        (
            "FIXTURE_START_DELAY_SECONDS",
            "nan",
            "FIXTURE_START_DELAY_SECONDS must be finite",
        ),
        ("FIXTURE_CRASH_EXIT_CODE", "256", "FIXTURE_CRASH_EXIT_CODE must be between"),
        ("FIXTURE_MARKER_PATH", "relative", "FIXTURE_MARKER_PATH must be absolute"),
    ],
)
def test_invalid_environment_fails_fast(name, value, message, tmp_path):
    environment = {"FIXTURE_MARKER_PATH": str(tmp_path / "marker"), name: value}
    with pytest.raises(ValueError, match=message):
        Settings.from_env(environment)
