"""Redacted, append-only HTTP evidence artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any


_SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api-key",
    "api_key",
)


def _configured_secret_values() -> tuple[str, ...]:
    raw = os.getenv("TRACE_REDACT_VALUES", "")
    return tuple(value for value in (part.strip() for part in raw.split(",")) if value)


def _redact_text(value: str, secret_values: tuple[str, ...]) -> str:
    result = value
    for secret in secret_values:
        result = result.replace(secret, "[REDACTED]")
    return result


def redact(value: Any, secret_values: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                output[key] = "[REDACTED]"
            else:
                output[key] = redact(item, secret_values)
        return output
    if isinstance(value, list):
        return [redact(item, secret_values) for item in value]
    if isinstance(value, str):
        return _redact_text(value, secret_values)
    return value


class HttpTraceWriter:
    def __init__(self, results_dir: Path, test_case_id: str) -> None:
        results_dir.mkdir(parents=True, exist_ok=True)
        self.path = results_dir / "http-trace.jsonl"
        self.test_case_id = test_case_id
        self._secret_values = _configured_secret_values()
        self._lock = Lock()

    def write(self, record: dict[str, Any]) -> None:
        envelope = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "test_case_id": self.test_case_id,
            **record,
        }
        serialized = json.dumps(
            redact(envelope, self._secret_values),
            ensure_ascii=False,
            sort_keys=True,
        )
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(serialized + "\n")
