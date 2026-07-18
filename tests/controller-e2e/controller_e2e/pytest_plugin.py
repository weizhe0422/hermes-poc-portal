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
    ContractViolation,
    EnvironmentBlocker,
    ExpectedResultMismatch,
    TransportFailure,
)


COVERAGE_GAPS = (
    {
        "test_case_id": "RUNTIME-004",
        "requirement_ids": ["RT-04"],
        "classification": "COVERAGE_GAP",
        "reason": "Traceability matrix references the case, but runtime/cases.yaml has no approved Expected Result.",
    },
    {
        "test_case_id": "RUNTIME-005",
        "requirement_ids": ["RT-05"],
        "classification": "COVERAGE_GAP",
        "reason": "Basic Restart case is absent; RUNTIME-014 is persistence-specific and does not replace it.",
    },
    {
        "test_case_id": "RUNTIME-007",
        "requirement_ids": ["RT-06"],
        "classification": "COVERAGE_GAP",
        "reason": "Stop/Restart idempotency has no approved runtime case Expected Result.",
    },
)


def _failure_classification(exception: BaseException | None) -> str:
    if exception is None:
        return "NONE"
    if isinstance(exception, ContractViolation):
        return "CONTRACT_VIOLATION"
    if isinstance(exception, ExpectedResultMismatch):
        return "EXPECTED_RESULT_MISMATCH"
    if isinstance(exception, TransportFailure):
        return "TRANSPORT_FAILURE"
    if isinstance(exception, EnvironmentBlocker):
        return "ENVIRONMENT_BLOCKER"
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
                ("hermes.case_source", "bundle-runtime-case"),
                ("hermes.coverage_claim", "case-level-partial"),
                ("hermes.acceptance_status", "case-evaluated"),
                ("hermes.golden_status", "bundle-draft-runtime-case"),
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
        report.user_properties.append(("failure_classification", classification))
    elif report.skipped and existing["status"] != "FAIL":
        existing["status"] = "SKIP"
        existing["failure_classification"] = "SKIPPED"
    elif report.when == "call" and existing["status"] not in ("FAIL", "SKIP"):
        existing["status"] = "PASS"
        report.user_properties.append(("failure_classification", "NONE"))


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
    }
    spec_root = Path(os.getenv("SPEC_ROOT", "/spec")).resolve()
    results_dir = Path(os.getenv("RESULTS_DIR", "/test-results")).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    overall_status = "PASS" if exitstatus == 0 and results else "FAIL"
    if not results:
        overall_status = "NOT_EXECUTED"
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
        "requirement_acceptance_claim": "PARTIAL_CASE_TRACE_ONLY",
        "critical_cases": [
            result["properties"].get("test_case_id")
            for result in results
            if result["properties"].get("critical") == "true"
        ],
        "coverage_gaps": list(COVERAGE_GAPS),
        "known_flakiness": [],
        "contract_questions": [
            "RT-06 requires Restart idempotency, but the state machine defines no Restart idempotent response."
        ],
        "assumptions": [
            "RUNTIME-014 final HEALTHY is persistence evidence only because the fixture gates health on its persistent marker.",
            "RUNTIME-006 uses the stable managed-instance registry as its API evidence; the outer isolated-engine harness supplies independent Docker event/snapshot evidence.",
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
