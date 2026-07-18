"""Read-only access to versioned runtime test cases."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from .errors import ContractViolation, EnvironmentBlocker


@dataclass(frozen=True)
class RuntimeCase:
    case_id: str
    purpose: str
    scenario: str
    requirement_ids: tuple[str, ...]
    critical: bool
    preconditions: tuple[str, ...]
    input: dict[str, Any]
    expected: dict[str, Any]
    forbidden: tuple[str, ...]
    verdict_mode: str


class RuntimeCaseCatalog:
    """Loads cases without ever mutating or writing below SPEC_ROOT."""

    def __init__(self, spec_root: Path) -> None:
        case_path = spec_root / "test-cases" / "runtime" / "cases.yaml"
        schema_path = spec_root / "contracts" / "schemas" / "evaluation-case.schema.json"
        try:
            with case_path.open("r", encoding="utf-8") as handle:
                document = yaml.safe_load(handle)
            with schema_path.open("r", encoding="utf-8") as handle:
                schema = json.load(handle)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            raise EnvironmentBlocker(f"Unable to load runtime cases: {exc}") from exc

        if not isinstance(document, dict) or not isinstance(document.get("cases"), list):
            raise ContractViolation(f"{case_path} must contain a cases array")

        validator = Draft202012Validator(schema)
        cases: dict[str, RuntimeCase] = {}
        for raw in document["cases"]:
            errors = sorted(validator.iter_errors(raw), key=lambda item: list(item.path))
            if errors:
                detail = "; ".join(error.message for error in errors)
                raise ContractViolation(f"Invalid runtime case: {detail}")
            case_id = raw["case_id"]
            if case_id in cases:
                raise ContractViolation(f"Duplicate runtime case ID: {case_id}")
            cases[case_id] = RuntimeCase(
                case_id=case_id,
                purpose=raw["purpose"],
                scenario=raw["scenario"],
                requirement_ids=tuple(raw["requirement_ids"]),
                critical=raw["critical"],
                preconditions=tuple(raw.get("preconditions", [])),
                input=dict(raw["input"]),
                expected=dict(raw["expected"]),
                forbidden=tuple(raw.get("forbidden", [])),
                verdict_mode=raw["verdict_mode"],
            )
        self._cases = cases

    def get(self, case_id: str) -> RuntimeCase:
        try:
            return self._cases[case_id]
        except KeyError as exc:
            raise EnvironmentBlocker(
                f"Bundle runtime case {case_id} is absent from SPEC_ROOT"
            ) from exc

    @property
    def case_ids(self) -> tuple[str, ...]:
        return tuple(self._cases)
