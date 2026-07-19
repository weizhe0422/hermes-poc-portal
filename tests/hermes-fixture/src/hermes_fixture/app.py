"""FastAPI application for deterministic Controller E2E runtime behavior."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Mapping

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import FixtureMode, Settings

Clock = Callable[[], float]
EventSink = Callable[[Mapping[str, object]], None]


def emit_json_event(event: Mapping[str, object]) -> None:
    """Emit one stable JSON object per line for Controller log assertions."""

    print(
        json.dumps(dict(event), ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        flush=True,
    )


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False


class ProbeState:
    """Pure, inspectable readiness state shared by all HTTP probes."""

    def __init__(self, settings: Settings, clock: Clock) -> None:
        self.settings = settings
        self._clock = clock
        self._started_at = clock()
        self._marker_lock = threading.Lock()

    def _marker_status(self) -> dict[str, object]:
        path = self.settings.marker_path
        try:
            if not path.is_file():
                return {
                    "marker_id": "RUNTIME-014",
                    "present": False,
                    "valid": False,
                    "sha256": None,
                }
            content = path.read_bytes()
        except OSError:
            return {
                "marker_id": "RUNTIME-014",
                "present": False,
                "valid": False,
                "sha256": None,
            }

        expected = self.settings.marker_value.encode("utf-8")
        return {
            "marker_id": "RUNTIME-014",
            "present": True,
            "valid": content == expected,
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def write_marker(self) -> dict[str, object]:
        """Atomically seed the fixed marker; callers cannot choose path or content."""

        path = self.settings.marker_path
        payload = self.settings.marker_value.encode("utf-8")
        with self._marker_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(f"{path}.tmp")
            try:
                with temporary.open("wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            finally:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        return self._marker_status()

    def snapshot(self) -> dict[str, object]:
        mode = self.settings.mode
        ready = False
        hermes_status = "UNAVAILABLE"
        llm_status = "UNAVAILABLE"
        reason = "FIXTURE_NOT_READY"
        marker: dict[str, object] | None = None

        if mode in {FixtureMode.HEALTHY, FixtureMode.SECRET_LOG}:
            ready = True
            hermes_status = "AVAILABLE"
            llm_status = "AVAILABLE"
            reason = "READY"
        elif mode is FixtureMode.SLOW_START:
            if self._clock() - self._started_at >= self.settings.start_delay_seconds:
                ready = True
                hermes_status = "AVAILABLE"
                llm_status = "AVAILABLE"
                reason = "SLOW_START_COMPLETE"
            else:
                reason = "SLOW_START_PENDING"
        elif mode is FixtureMode.UNHEALTHY:
            llm_status = "AVAILABLE"
            reason = "SYNTHETIC_HERMES_UNHEALTHY"
        elif mode is FixtureMode.PERSISTENT:
            marker = self._marker_status()
            llm_status = "AVAILABLE"
            if marker["valid"]:
                ready = True
                hermes_status = "AVAILABLE"
                reason = "PERSISTENT_MARKER_VALID"
            elif marker["present"]:
                reason = "PERSISTENT_MARKER_INVALID"
            else:
                reason = "PERSISTENT_MARKER_MISSING"
        elif mode is FixtureMode.CRASH:
            reason = "CRASH_MODE_PROCESS_MUST_EXIT"

        result = self.settings.metadata()
        result.update(
            {
                "status": "AVAILABLE" if ready else "UNAVAILABLE",
                "ready": ready,
                "hermes_status": hermes_status,
                "llm_status": llm_status,
                "reason": reason,
            }
        )
        if marker is not None:
            result["persistent_marker"] = marker
        return result


def _openai_error(message: str, code: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": "synthetic_fixture_error",
                "param": None,
                "code": code,
            }
        },
    )


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock = time.monotonic,
    event_sink: EventSink = emit_json_event,
) -> FastAPI:
    settings = Settings.from_env() if settings is None else settings
    state = ProbeState(settings, clock)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        event_sink({**settings.metadata(), "event": "fixture_started"})
        if settings.mode is FixtureMode.SECRET_LOG:
            event_sink(
                {
                    **settings.metadata(),
                    "event": "synthetic_secret_log",
                    "secret": settings.test_secret,
                }
            )
        yield
        event_sink({**settings.metadata(), "event": "fixture_stopped"})

    app = FastAPI(
        title="TEST ONLY Hermes Runtime Fixture",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.probe_state = state

    @app.middleware("http")
    async def add_test_only_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Hermes-Fixture"] = "SYNTHETIC_TEST_ONLY"
        return response

    @app.get("/metadata")
    def metadata():
        return {
            **settings.metadata(),
            "supported_modes": [item.value for item in FixtureMode],
            "health_path": "/health",
            "llm_probe_paths": ["/llm/health", "/v1/models", "/v1/chat/completions"],
        }

    @app.get("/health")
    def health():
        snapshot = state.snapshot()
        return JSONResponse(status_code=200 if snapshot["ready"] else 503, content=snapshot)

    @app.get("/llm/health")
    def llm_health():
        snapshot = state.snapshot()
        available = snapshot["llm_status"] == "AVAILABLE"
        body = {
            **settings.metadata(),
            "status": "AVAILABLE" if available else "UNAVAILABLE",
            "model": settings.model_name,
        }
        return JSONResponse(status_code=200 if available else 503, content=body)

    @app.get("/v1/models")
    def models():
        if state.snapshot()["llm_status"] != "AVAILABLE":
            return _openai_error(
                "TEST ONLY deterministic LLM probe is unavailable",
                "FIXTURE_LLM_UNAVAILABLE",
                503,
            )
        return {
            "object": "list",
            "data": [
                {
                    "id": settings.model_name,
                    "object": "model",
                    "created": 0,
                    "owned_by": "synthetic-test-only",
                }
            ],
        }

    @app.post("/v1/chat/completions")
    def chat_completions(request: ChatCompletionRequest):
        if state.snapshot()["llm_status"] != "AVAILABLE":
            return _openai_error(
                "TEST ONLY deterministic LLM probe is unavailable",
                "FIXTURE_LLM_UNAVAILABLE",
                503,
            )
        if request.stream:
            return _openai_error(
                "Streaming is intentionally unsupported by this deterministic fixture",
                "FIXTURE_STREAMING_UNSUPPORTED",
                400,
            )
        if request.model != settings.model_name:
            return _openai_error(
                "Requested model is not provided by this deterministic fixture",
                "FIXTURE_MODEL_NOT_FOUND",
                404,
            )
        return {
            "id": "chatcmpl-synthetic-deterministic",
            "object": "chat.completion",
            "created": 0,
            "model": settings.model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "TEST ONLY deterministic probe response",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    @app.put("/test-only/persistent-marker")
    def seed_persistent_marker():
        if settings.mode is not FixtureMode.PERSISTENT:
            return JSONResponse(
                status_code=409,
                content={
                    **settings.metadata(),
                    "error_code": "FIXTURE_MODE_NOT_PERSISTENT",
                },
            )
        return {**settings.metadata(), "persistent_marker": state.write_marker()}

    @app.get("/test-only/persistent-marker")
    def read_persistent_marker():
        if settings.mode is not FixtureMode.PERSISTENT:
            return JSONResponse(
                status_code=409,
                content={
                    **settings.metadata(),
                    "error_code": "FIXTURE_MODE_NOT_PERSISTENT",
                },
            )
        marker = state._marker_status()
        if not marker["present"]:
            status_code = 404
        elif not marker["valid"]:
            status_code = 409
        else:
            status_code = 200
        return JSONResponse(
            status_code=status_code,
            content={**settings.metadata(), "persistent_marker": marker},
        )

    return app
