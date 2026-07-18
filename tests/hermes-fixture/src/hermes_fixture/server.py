"""Process behavior, including deterministic CRASH mode."""

from __future__ import annotations

import time
from typing import Callable

import uvicorn

from .app import EventSink, create_app, emit_json_event
from .config import FixtureMode, Settings


def run(
    settings: Settings | None = None,
    *,
    server_runner: Callable[..., object] = uvicorn.run,
    sleeper: Callable[[float], None] = time.sleep,
    event_sink: EventSink = emit_json_event,
) -> int:
    settings = Settings.from_env() if settings is None else settings

    if settings.mode is FixtureMode.CRASH:
        event_sink(
            {
                **settings.metadata(),
                "event": "synthetic_crash",
                "delay_seconds": settings.crash_delay_seconds,
                "exit_code": settings.crash_exit_code,
            }
        )
        sleeper(settings.crash_delay_seconds)
        return settings.crash_exit_code

    server_runner(
        create_app(settings, event_sink=event_sink),
        host=settings.host,
        port=settings.port,
        access_log=False,
        log_config=None,
    )
    return 0
