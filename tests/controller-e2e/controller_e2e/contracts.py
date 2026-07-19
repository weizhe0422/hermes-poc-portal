"""OpenAPI and JSON Schema validation for every Controller response."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urldefrag

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
import yaml

from .errors import ContractAmbiguity, ContractViolation, EnvironmentBlocker


_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


def _format_checker() -> FormatChecker:
    checker = FormatChecker()

    @checker.checks("date-time", raises=(TypeError, ValueError))
    def is_rfc3339(value: object) -> bool:
        if not isinstance(value, str):
            return True
        if not _RFC3339.fullmatch(value):
            return False
        normalized = value.upper().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.tzinfo is not None

    return checker


def _json_pointer(document: Any, fragment: str) -> Any:
    if fragment in ("", "/"):
        return document
    current = document
    for encoded in fragment.lstrip("/").split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        try:
            current = current[int(token)] if isinstance(current, list) else current[token]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ContractViolation(f"Unresolvable JSON pointer: #/{fragment}") from exc
    return current


class ContractBundle:
    def __init__(self, spec_root: Path) -> None:
        self.spec_root = spec_root.resolve()
        self.openapi_path = (
            self.spec_root / "contracts" / "openapi" / "controller-api.yaml"
        )
        state_path = (
            self.spec_root
            / "contracts"
            / "state-machines"
            / "hermes-runtime.yaml"
        )
        error_catalog_path = (
            self.spec_root / "contracts" / "errors" / "error-catalog.yaml"
        )
        try:
            self.openapi = self._load_document(self.openapi_path)
            self.state_machine = self._load_document(state_path)
            self.error_catalog = self._load_document(error_catalog_path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            raise EnvironmentBlocker(f"Unable to load Controller contracts: {exc}") from exc

        if self.openapi.get("openapi") != "3.1.0":
            raise ContractViolation("Controller contract must be OpenAPI 3.1.0")

        self._documents: dict[Path, Any] = {
            self.openapi_path.resolve(): self.openapi,
            state_path.resolve(): self.state_machine,
            error_catalog_path.resolve(): self.error_catalog,
        }
        self._operations = self._index_operations()
        self._registry = self._build_schema_registry()
        self._format_checker = _format_checker()

    @staticmethod
    def _load_document(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            if path.suffix == ".json":
                return json.load(handle)
            return yaml.safe_load(handle)

    def _load_cached(self, path: Path) -> Any:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.spec_root)
        except ValueError as exc:
            raise ContractViolation(f"Contract reference escapes SPEC_ROOT: {path}") from exc
        if resolved not in self._documents:
            self._documents[resolved] = self._load_document(resolved)
        return self._documents[resolved]

    def _build_schema_registry(self) -> Registry:
        registry = Registry()
        schema_dir = self.spec_root / "contracts" / "schemas"
        for path in sorted(schema_dir.glob("*.json")):
            schema = self._load_cached(path)
            Draft202012Validator.check_schema(schema)
            resource = Resource.from_contents(schema)
            registry = registry.with_resource(path.resolve().as_uri(), resource)
            schema_id = schema.get("$id")
            if schema_id:
                registry = registry.with_resource(schema_id, resource)
        return registry

    def _index_operations(self) -> dict[str, tuple[str, str, dict[str, Any]]]:
        operations: dict[str, tuple[str, str, dict[str, Any]]] = {}
        for path, path_item in self.openapi.get("paths", {}).items():
            for method in ("get", "post", "put", "patch", "delete"):
                operation = path_item.get(method)
                if not operation:
                    continue
                operation_id = operation.get("operationId")
                if not operation_id:
                    raise ContractViolation(f"{method.upper()} {path} lacks operationId")
                if operation_id in operations:
                    raise ContractViolation(f"Duplicate operationId: {operation_id}")
                operations[operation_id] = (method.upper(), path, operation)
        return operations

    def _resolve_reference(
        self, reference: str, base_path: Path, root_document: Any
    ) -> tuple[Any, Path, bool]:
        location, fragment = urldefrag(reference)
        if not location:
            document = root_document
            path = base_path
            external = False
        else:
            path = (base_path.parent / location).resolve()
            document = self._load_cached(path)
            external = True
        if fragment:
            document = _json_pointer(document, fragment)
        return deepcopy(document), path, external

    def _materialize_openapi_schema(
        self, node: Any, base_path: Path, root_document: Any
    ) -> Any:
        if isinstance(node, list):
            return [
                self._materialize_openapi_schema(item, base_path, root_document)
                for item in node
            ]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            resolved, resolved_path, external = self._resolve_reference(
                node["$ref"], base_path, root_document
            )
            siblings = {key: value for key, value in node.items() if key != "$ref"}
            if siblings:
                if not isinstance(resolved, dict):
                    raise ContractViolation("A $ref with siblings must resolve to an object")
                resolved.update(siblings)
            # External JSON Schemas carry an absolute $id. Keep their own relative
            # references intact so the Draft 2020-12 registry resolves them correctly.
            if external and resolved_path.suffix == ".json":
                return resolved
            return self._materialize_openapi_schema(
                resolved, resolved_path, resolved
            )
        return {
            key: self._materialize_openapi_schema(value, base_path, root_document)
            for key, value in node.items()
        }

    def operation(self, operation_id: str) -> tuple[str, str, dict[str, Any]]:
        try:
            return self._operations[operation_id]
        except KeyError as exc:
            raise ContractViolation(
                f"Unknown Controller operationId: {operation_id}"
            ) from exc

    def declared_statuses(self, operation_id: str) -> tuple[int, ...]:
        _, _, operation = self.operation(operation_id)
        return tuple(
            sorted(
                int(status)
                for status in operation["responses"]
                if status != "default"
            )
        )

    def success_statuses(self, operation_id: str) -> tuple[int, ...]:
        return tuple(
            status
            for status in self.declared_statuses(operation_id)
            if status < 300
        )

    def response_schema(self, operation_id: str, status_code: int) -> dict[str, Any]:
        _, _, operation = self.operation(operation_id)
        responses = operation.get("responses", {})
        response = responses.get(str(status_code), responses.get("default"))
        if response is None:
            raise ContractViolation(
                f"{operation_id} returned undeclared HTTP status {status_code}"
            )
        response = self._materialize_openapi_schema(
            response, self.openapi_path, self.openapi
        )
        try:
            schema = response["content"]["application/json"]["schema"]
        except (KeyError, TypeError) as exc:
            raise ContractViolation(
                f"{operation_id} HTTP {status_code} lacks an application/json schema"
            ) from exc
        # The response object was materialized recursively above. External JSON
        # Schemas are intentionally left intact with their own absolute $id, so
        # processing this node a second time against the OpenAPI directory would
        # incorrectly rebase their internal relative references.
        return schema

    def validate_response(
        self, operation_id: str, status_code: int, payload: Any
    ) -> None:
        schema = self.response_schema(operation_id, status_code)
        validator = Draft202012Validator(
            schema,
            registry=self._registry,
            format_checker=self._format_checker,
        )
        errors = sorted(
            validator.iter_errors(payload),
            key=lambda error: (
                list(error.absolute_path),
                list(error.absolute_schema_path),
            ),
        )
        if errors:
            details = []
            for error in errors[:8]:
                path = "/".join(str(part) for part in error.absolute_path) or "<root>"
                details.append(f"{path}: {error.message}")
            suffix = "" if len(errors) <= 8 else f"; plus {len(errors) - 8} more"
            raise ContractViolation(
                f"{operation_id} HTTP {status_code} violates response schema: "
                + "; ".join(details)
                + suffix
            )
        if status_code >= 400:
            self._validate_error_catalog(operation_id, status_code, payload)

    def _validate_error_catalog(
        self,
        operation_id: str,
        status_code: int,
        payload: dict[str, Any],
    ) -> None:
        forbidden_fields = {
            str(field).lower()
            for field in self.error_catalog.get("response_requirements", {}).get(
                "forbidden_fields", []
            )
        }

        def find_forbidden(value: Any, prefix: str = "") -> list[str]:
            findings = []
            if isinstance(value, dict):
                for key, item in value.items():
                    path = f"{prefix}.{key}" if prefix else str(key)
                    if str(key).lower() in forbidden_fields:
                        findings.append(path)
                    findings.extend(find_forbidden(item, path))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    findings.extend(find_forbidden(item, f"{prefix}[{index}]"))
            return findings

        forbidden_findings = find_forbidden(payload)
        if forbidden_findings:
            raise ContractViolation(
                f"{operation_id} HTTP {status_code} contains forbidden error fields: "
                + ", ".join(forbidden_findings)
            )

        error_code = payload["error_code"]
        definition = self.error_catalog.get("errors", {}).get(error_code)
        if not isinstance(definition, dict):
            raise ContractViolation(
                f"{operation_id} HTTP {status_code} returned unknown "
                f"error_code {error_code!r}"
            )
        if definition.get("delivery") not in {"HTTP", "BOTH"}:
            raise ContractViolation(
                f"{operation_id} returned resource-state-only error {error_code} over HTTP"
            )
        if definition.get("http_status") != status_code:
            raise ContractViolation(
                f"{operation_id} error {error_code} requires HTTP "
                f"{definition.get('http_status')}, received {status_code}"
            )
        if payload["retryable"] is not definition.get("retryable"):
            raise ContractViolation(
                f"{operation_id} error {error_code} retryable must be "
                f"{definition.get('retryable')!r}"
            )
        if payload["message"] != definition.get("user_message"):
            raise ContractViolation(
                f"{operation_id} error {error_code} message differs from the catalog"
            )

    def assert_healthy_contract(self, instance: dict[str, Any]) -> None:
        requirements = self.state_machine["health_contract"]["healthy_requires"]
        mismatches = []
        for expression in requirements:
            try:
                field, expected = (part.strip() for part in expression.split("==", 1))
            except ValueError as exc:
                raise ContractViolation(
                    f"Unsupported health_contract expression: {expression}"
                ) from exc
            actual = instance.get(field)
            if str(actual) != expected:
                mismatches.append(f"{field} expected {expected}, received {actual!r}")
        if mismatches:
            raise ContractViolation(
                "HEALTHY AgentInstance violates health_contract: "
                + "; ".join(mismatches)
            )

    def event_source_states(self, event: str) -> tuple[str, ...]:
        return tuple(
            transition["from"]
            for transition in self.state_machine.get("transitions", [])
            if transition.get("event") == event
        )

    def lifecycle_request_outcome(
        self, current_state: str, requested_action: str
    ) -> dict[str, Any]:
        """Resolve one request outcome directly from the Frozen state machine."""

        transitions = [
            transition
            for transition in self.state_machine.get("transitions", [])
            if transition.get("from") == current_state
            and transition.get("action") == requested_action
            and isinstance(transition.get("http_status"), int)
        ]
        idempotency = [
            rule
            for rule in self.state_machine.get("idempotency_rules", [])
            if rule.get("current_state") == current_state
            and rule.get("requested_action") == requested_action
            and isinstance(rule.get("http_status"), int)
        ]
        if len(transitions) + len(idempotency) != 1:
            raise ContractViolation(
                "Frozen state machine does not publish one unique outcome for "
                f"state={current_state!r}, action={requested_action!r}"
            )
        if transitions:
            transition = transitions[0]
            return {
                "http_status": transition["http_status"],
                "state": transition["to"],
                "operation_action": transition["action"],
            }
        rule = idempotency[0]
        return {
            "http_status": rule["http_status"],
            "state": current_state,
            "operation_action": None,
        }

    def resource_state_error_field(
        self,
        expected_key: str,
        error_code: str,
    ) -> str:
        definition = self.error_catalog.get("errors", {}).get(error_code)
        if not isinstance(definition, dict):
            raise ContractViolation(
                f"Runtime Expected references unknown error code {error_code!r}"
            )
        if definition.get("delivery") not in {"RESOURCE_STATE", "BOTH"}:
            raise ContractViolation(
                f"Runtime Expected error code {error_code} is not deliverable "
                "through resource state"
            )

        schema_path = (
            self.spec_root / "contracts" / "schemas" / "agent-instance.schema.json"
        )
        schema = self._load_cached(schema_path)
        properties = schema.get("properties", {})
        if expected_key in properties:
            return expected_key

        candidates = sorted(
            str(field)
            for field in properties
            if str(field).endswith("error_code")
        )
        candidate_text = ", ".join(candidates) or "none"
        raise ContractAmbiguity(
            f"Frozen runtime expected.{expected_key} has AgentInstance candidate "
            f"field(s) {candidate_text}, but no published mapping connects them"
        )
