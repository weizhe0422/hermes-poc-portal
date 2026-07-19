from __future__ import annotations

from hermes_fixture.config import Settings
from hermes_fixture.server import run


def test_crash_mode_emits_structured_event_and_never_starts_uvicorn(tmp_path):
    settings = Settings.from_env(
        {
            "FIXTURE_MODE": "CRASH",
            "FIXTURE_CRASH_DELAY_SECONDS": "1.25",
            "FIXTURE_CRASH_EXIT_CODE": "37",
            "FIXTURE_MARKER_PATH": str(tmp_path / "marker"),
        }
    )
    events = []
    delays = []
    server_calls = []

    exit_code = run(
        settings,
        event_sink=events.append,
        sleeper=delays.append,
        server_runner=lambda *args, **kwargs: server_calls.append((args, kwargs)),
    )

    assert exit_code == 37
    assert delays == [1.25]
    assert server_calls == []
    assert events == [
        {
            **settings.metadata(),
            "event": "synthetic_crash",
            "delay_seconds": 1.25,
            "exit_code": 37,
        }
    ]
