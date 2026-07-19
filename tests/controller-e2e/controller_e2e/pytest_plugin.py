"""JUnit metadata, failure classification, and deterministic summaries."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any

import pytest
import yaml

from .artifacts import redact
from .errors import (
    ContractAmbiguity,
    ContractViolation,
    EnvironmentBlocker,
    ExpectedResultMismatch,
    TransportFailure,
)


COVERAGE_GAPS: tuple[dict[str, Any], ...] = ()


def _upsert_user_property(
    properties: list[tuple[str, object]], name: str, value: str
) -> None:
    properties[:] = [item for item in properties if item[0] != name]
    properties.append((name, value))


def _failure_classification(exception: BaseException | None) -> str:
    if exception is None:
        return "NONE"
    if isinstance(exception, ContractAmbiguity):
        return "BLOCKED_BY_CONTRACT"
    if isinstance(exception, ContractViolation):
        return "CONTRACT_VIOLATION"
    if isinstance(exception, ExpectedResultMismatch):
        return "EXPECTED_RESULT_MISMATCH"
    if isinstance(exception, TransportFailure):
        return "TRANSPORT_FAILURE"
    if isinstance(exception, EnvironmentBlocker):
        return "BLOCKED_BY_ENVIRONMENT"
    if isinstance(exception, AssertionError):
        return "ASSERTION_FAILURE"
    return "TEST_IMPLEMENTATION_ERROR"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "case(test_case_id, requirement_ids, critical, assumptions=()): Bundle case metadata",
    )
    config._hermes_results = {}  # type: ignore[attr-defined]
    config._hermes_started = time.monotonic()  # type: ignore[attr-defined]


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    for item in items:
        marker = item.get_closest_marker("case")
        if marker is None:
            raise pytest.UsageError(
                f"E2E test {item.nodeid} lacks required @pytest.mark.case metadata"
            )
        case_id = marker.kwargs["test_case_id"]
        requirement_ids = tuple(marker.kwargs["requirement_ids"])
        critical = bool(marker.kwargs["critical"])
        item.user_properties.extend(
            [
                ("test_case_id", case_id),
                ("requirement_ids", ",".join(requirement_ids)),
                ("critical", str(critical).lower()),
                ("milestone", "T-M1"),
                ("retry_policy", "NO_RETRY"),
                ("hermes.case_source", "frozen-runtime-case"),
                ("hermes.coverage_claim", "case-level"),
                ("hermes.acceptance_status", "case-evaluated"),
                ("hermes.golden_status", "frozen-v0.2.0"),
                ("hermes.evidence_kind", "black-box"),
            ]
        )
        for assumption in marker.kwargs.get("assumptions", ()):
            item.user_properties.append(("assumption", assumption))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    outcome = yield
    report = outcome.get_result()
    results: dict[str, dict[str, Any]] = item.config._hermes_results  # type: ignore[attr-defined]
    existing = results.setdefault(
        item.nodeid,
        {
            "nodeid": item.nodeid,
            "properties": dict(item.user_properties),
            "duration_seconds": 0.0,
            "status": "NOT_RUN",
            "failure_classification": "NONE",
            "failure": None,
        },
    )
    existing["duration_seconds"] += report.duration

    exception = call.excinfo.value if call.excinfo else None
    classification = _failure_classification(exception)
    if report.failed:
        existing["status"] = "FAIL"
        existing["failure_classification"] = classification
        existing["failure"] = str(report.longrepr)[:12000]
        # pytest's JUnit writer uses the teardown report's item properties.
        # Persist the classification on both objects so a call-phase failure is
        # still present in the canonical XML after teardown.
        _upsert_user_property(
            item.user_properties, "failure_classification", classification
        )
        _upsert_user_property(
            report.user_properties, "failure_classification", classification
        )
    elif report.skipped and existing["status"] != "FAIL":
        existing["status"] = "SKIP"
        existing["failure_classification"] = "SKIPPED"
    elif report.when == "call" and existing["status"] not in ("FAIL", "SKIP"):
        existing["status"] = "PASS"
        _upsert_user_property(item.user_properties, "failure_classification", "NONE")
        _upsert_user_property(report.user_properties, "failure_classification", "NONE")


def _versions(spec_root: Path) -> dict[str, Any]:
    path = spec_root / "contracts" / "versions.yaml"
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle)
        return {
            key: value
            for key, value in document.items()
            if key != "runtime_values_to_fill"
        }
    except (OSError, TypeError, yaml.YAMLError):
        return {}


def _markdown(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    lines = [
        "# Hermes Controller E2E T-M1 Summary",
        "",
        f"- Overall: **{summary['overall_status']}**",
        f"- Exit code: `{summary['pytest_exit_code']}`",
        f"- Passed: {counts['passed']}",
        f"- Failed: {counts['failed']}",
        f"- Skipped: {counts['skipped']}",
        f"- Duration: {summary['duration_seconds']:.3f}s",
        "",
        "## Executed cases",
        "",
        "| Test Case | Requirements | Status | Failure classification |",
        "|---|---|---|---|",
    ]
    for result in summary["results"]:
        properties = result["properties"]
        lines.append(
            f"| {properties.get('test_case_id', '')} | "
            f"{properties.get('requirement_ids', '')} | {result['status']} | "
            f"{result['failure_classification']} |"
        )
    lines.extend(["", "## Explicit coverage gaps", ""])
    for gap in summary["coverage_gaps"]:
        lines.append(
            f"- `{gap['test_case_id']}` ({', '.join(gap['requirement_ids'])}): "
            f"{gap['reason']}"
        )
    lines.extend(
        [
            "",
            "## Assumptions",
            "",
            "- RUNTIME-014 uses a persistent-marker-gated fixture: final HEALTHY is the black-box persistence proof.",
            "- RUNTIME-006 checks the public managed registry; the outer isolated-engine harness separately records create events and the final container set.",
            "- Polling is bounded state observation, not test retry. Critical cases are executed once.",
            "",
        ]
    )
    return "\n".join(lines)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    results = list(config._hermes_results.values())  # type: ignore[attr-defined]
    results.sort(key=lambda result: result["properties"].get("test_case_id", ""))
    secret_values = tuple(
        value
        for value in (
            part.strip() for part in os.getenv("TRACE_REDACT_VALUES", "").split(",")
        )
        if value
    )
    results = redact(results, secret_values)
    counts = {
        "passed": sum(result["status"] == "PASS" for result in results),
        "failed": sum(result["status"] == "FAIL" for result in results),
        "skipped": sum(result["status"] == "SKIP" for result in results),
        "not_run": sum(result["status"] == "NOT_RUN" for result in results),
        "blocked_by_contract": sum(
            result["failure_classification"] == "BLOCKED_BY_CONTRACT"
            for result in results
        ),
    }
    spec_root = Path(os.getenv("SPEC_ROOT", "/spec")).resolve()
    results_dir = Path(os.getenv("RESULTS_DIR", "/test-results")).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    overall_status = "PASS" if exitstatus == 0 and results else "FAIL"
    if not results:
        overall_status = "NOT_EXECUTED"
    elif counts["failed"] and counts["failed"] == counts["blocked_by_contract"]:
        overall_status = "CONTRACT_BLOCKED"
    summary = {
        "role": "independent-test-implementer",
        "milestone": "T-M1",
        "overall_status": overall_status,
        "pytest_exit_code": int(exitstatus),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": time.monotonic() - config._hermes_started,  # type: ignore[attr-defined]
        "counts": counts,
        "case_traced_requirements": sorted(
            {
                requirement
                for result in results
                for requirement in result["properties"].get(
                    "requirement_ids", ""
                ).split(",")
                if requirement
            }
        ),
        "requirement_acceptance_claim": "FROZEN_CASE_LEVEL",
        "critical_cases": [
            result["properties"].get("test_case_id")
            for result in results
            if result["properties"].get("critical") == "true"
        ],
        "coverage_gaps": list(COVERAGE_GAPS),
        "known_flakiness": [
            "RUNTIME-008 uses a simultaneous two-thread barrier; the Frozen case does not specify request ordering, so a Stop-first scheduler outcome is reported rather than retried."
        ],
        "contract_questions": [
            "RUNTIME-009 expected.error_code has no published mapping to AgentInstance.last_error_code.",
            "RUNTIME-008 freezes one accepted operation plus one conflict but does not define which concurrent request must win.",
            "Frozen versions.yaml includes RUNTIME-008/009/012/013 in M0/M1 while the legacy work packet labels them T-M2.",
        ],
        "assumptions": [
            "Engine-only fields such as container identity, event counts, and volume markers are attached by the external isolated-Docker orchestrator.",
            "Polling is bounded state observation and every Critical case has retry_policy=NO_RETRY.",
        ],
        "artifact_formats": ["JUnit XML", "JSON", "Markdown", "HTTP trace JSONL"],
        "versions": _versions(spec_root),
        "results": results,
    }
    (results_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (results_dir / "summary.md").write_text(_markdown(summary), encoding="utf-8")

    terminal = config.pluginmanager.get_plugin("terminalreporter")
    if terminal:
        terminal.write_sep(
            "=",
            f"T-M1 summary: {summary['overall_status']} "
            f"({counts['passed']} passed, {counts['failed']} failed); "
            f"artifacts: {results_dir}",
        )
