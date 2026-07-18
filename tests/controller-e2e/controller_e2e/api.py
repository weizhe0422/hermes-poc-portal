"""HTTPX client constrained to the published Controller API."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
from urllib.parse import quote

import httpx

from .artifacts import HttpTraceWriter
from .contracts import ContractBundle
from .errors import ContractViolation, TransportFailure


@dataclass(frozen=True)
class ValidatedResponse:
    operation_id: str
    status_code: int
    payload: Any
    elapsed_seconds: float


class ControllerClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        contracts: ContractBundle,
        trace: HttpTraceWriter,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._contracts = contracts
        self._trace = trace
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport,
            follow_redirects=False,
            trust_env=False,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ControllerClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _exchange(self, operation_id: str, path: str) -> ValidatedResponse:
        method, _, _ = self._contracts.operation(operation_id)
        started = time.monotonic()
        try:
            response = self._client.request(method, path)
        except httpx.HTTPError as exc:
            elapsed = time.monotonic() - started
            self._trace.write(
                {
                    "operation_id": operation_id,
                    "request": {"method": method, "path": path},
                    "duration_ms": round(elapsed * 1000, 3),
                    "transport_error": f"{type(exc).__name__}: {exc}",
                }
            )
            raise TransportFailure(
                f"{operation_id} could not reach Controller: {type(exc).__name__}: {exc}"
            ) from exc

        elapsed = time.monotonic() - started
        content_type = response.headers.get("content-type", "")
        trace_record: dict[str, Any] = {
            "operation_id": operation_id,
            "request": {"method": method, "path": path},
            "response": {
                "status_code": response.status_code,
                "content_type": content_type,
                "headers": dict(response.headers),
            },
            "duration_ms": round(elapsed * 1000, 3),
        }
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            trace_record["response"]["body_text"] = response.text[:65536]
            trace_record["contract_validation"] = "FAIL: non-JSON content type"
            self._trace.write(trace_record)
            raise ContractViolation(
                f"{operation_id} HTTP {response.status_code} must return application/json; "
                f"received {content_type!r}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            trace_record["response"]["body_text"] = response.text[:65536]
            trace_record["contract_validation"] = "FAIL: invalid JSON"
            self._trace.write(trace_record)
            raise ContractViolation(
                f"{operation_id} HTTP {response.status_code} returned invalid JSON"
            ) from exc

        trace_record["response"]["body"] = payload
        try:
            self._contracts.validate_response(
                operation_id, response.status_code, payload
            )
        except ContractViolation as exc:
            trace_record["contract_validation"] = f"FAIL: {exc}"
            self._trace.write(trace_record)
            raise
        trace_record["contract_validation"] = "PASS"
        self._trace.write(trace_record)
        return ValidatedResponse(
            operation_id=operation_id,
            status_code=response.status_code,
            payload=payload,
            elapsed_seconds=elapsed,
        )

    @staticmethod
    def _instance_path(instance_id: str, suffix: str = "") -> str:
        encoded = quote(instance_id, safe="")
        return f"/v1/instances/{encoded}{suffix}"

    def liveness(self) -> ValidatedResponse:
        return self._exchange("controllerLiveness", "/health/live")

    def readiness(self) -> ValidatedResponse:
        return self._exchange("controllerReadiness", "/health/ready")

    def list_instances(self) -> ValidatedResponse:
        return self._exchange("listManagedInstances", "/v1/instances")

    def get_instance(self, instance_id: str) -> ValidatedResponse:
        return self._exchange(
            "getManagedInstance", self._instance_path(instance_id)
        )

    def start_instance(self, instance_id: str) -> ValidatedResponse:
        return self._exchange(
            "startManagedInstance", self._instance_path(instance_id, "/start")
        )

    def stop_instance(self, instance_id: str) -> ValidatedResponse:
        return self._exchange(
            "stopManagedInstance", self._instance_path(instance_id, "/stop")
        )

    def restart_instance(self, instance_id: str) -> ValidatedResponse:
        return self._exchange(
            "restartManagedInstance", self._instance_path(instance_id, "/restart")
        )
