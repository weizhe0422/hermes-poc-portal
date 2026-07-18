from __future__ import annotations

from copy import deepcopy
import json
import os
import subprocess
import sys
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = REPO_ROOT / "scripts" / "collect-test-results"


def _write_junit(
    run_root: Path,
    *,
    status: str = "passed",
    include_requirement_ids: bool = True,
    nested: bool = False,
) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_root.name,
        "fixture_type": "SYNTHETIC",
        "spec_version": "0.1.0",
        "git_commit": "0123456789abcdef",
        "git_branch": "test/t-m0-m1",
        "test_suite": "controller-e2e",
        "images": {"controller_e2e": "example.invalid/controller-e2e:0.1.0"},
        "executed_at": "2026-07-18T00:00:00Z",
    }
    (run_root / "manifest.yaml").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    logs = run_root / "controller-e2e" / "logs"
    snapshots = run_root / "controller-e2e" / "docker-snapshots"
    logs.mkdir(parents=True, exist_ok=True)
    snapshots.mkdir(parents=True, exist_ok=True)
    for name in (
        "controller-core-start.log",
        "controller-core-idempotency.log",
        "controller-persistence.log",
        "docker-engine-test.log",
    ):
        (logs / name).write_text("synthetic test log\n", encoding="utf-8")
    (snapshots / "containers.jsonl").write_text("{}\n", encoding="utf-8")
    (snapshots / "persistence.json").write_text("{}\n", encoding="utf-8")
    for name in (
        "events-core-start.jsonl",
        "events-core-idempotency.jsonl",
        "events-persistence.jsonl",
    ):
        (snapshots / name).write_text("{}\n", encoding="utf-8")
    for name in (
        "invariants-core-start.json",
        "invariants-core-idempotency.json",
        "invariants-persistence.json",
    ):
        (snapshots / name).write_text(
            json.dumps({"verdict": True}), encoding="utf-8"
        )
    (snapshots / "cleanup.json").write_text(
        json.dumps({"cleanup_verified": True}), encoding="utf-8"
    )
    (snapshots / "outer-cleanup.json").write_text(
        json.dumps({"compose_down_verified": True}), encoding="utf-8"
    )
    (run_root / "controller-e2e" / "runner-status.json").write_text(
        json.dumps(
            {
                "orchestration_completed": True,
                "runner_passed": True,
                "evidence_collection_verified": True,
                "cleanup_verified": True,
                "compose_down_verified": True,
                "source_tree_unchanged": True,
            }
        ),
        encoding="utf-8",
    )
    case_specs = (
        ("RUNTIME-001", "RT-01,RT-02"),
        ("RUNTIME-003", "RT-03,RT-09"),
        ("RUNTIME-006", "RT-06"),
        ("RUNTIME-014", "RT-05,NF-05"),
    )
    testcase_rows = []
    for case_id, requirements in case_specs:
        requirement_property = (
            f'<property name="requirement_ids" value="{requirements}" />'
            if include_requirement_ids or case_id != "RUNTIME-001"
            else ""
        )
        engine_property = (
            '<property name="engine_evidence" value="PASS" />'
            if case_id in {"RUNTIME-003", "RUNTIME-006", "RUNTIME-014"}
            else ""
        )
        if case_id != "RUNTIME-001" or status == "passed":
            result = ""
        elif status == "failed":
            result = '<failure message="contract mismatch" />'
        else:
            result = '<skipped message="coverage gap" />'
        testcase_rows.append(
            f"""  <testcase classname="controller" name="{case_id.lower()}" time="0.1">
    <properties>
      <property name="test_case_id" value="{case_id}" />
      {requirement_property}
      <property name="critical" value="true" />
      <property name="hermes.case_source" value="bundle-runtime-case" />
      <property name="hermes.coverage_claim" value="case-level-partial" />
      <property name="hermes.acceptance_status" value="case-evaluated" />
      <property name="hermes.golden_status" value="bundle-draft-runtime-case" />
      <property name="hermes.evidence_kind" value="black-box" />
      {engine_property}
    </properties>
    {result}
  </testcase>"""
        )
    junit = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuite tests="4">\n'
        + "\n".join(testcase_rows)
        + "\n</testsuite>\n"
    )
    junit_dir = run_root / ("controller-e2e/core-start" if nested else "junit")
    junit_dir.mkdir(parents=True)
    (junit_dir / "controller.xml").write_text(junit, encoding="utf-8")


def _write_portal_junit(run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_root.name,
        "fixture_type": "SYNTHETIC",
        "spec_version": "0.1.0",
        "git_commit": "0123456789abcdef",
        "git_branch": "test/t-m0-m1",
        "test_suite": "portal-e2e",
        "images": {"portal_e2e": "example.invalid/portal-e2e:0.1.0"},
        "executed_at": "2026-07-18T00:00:00Z",
    }
    (run_root / "manifest.yaml").write_text(json.dumps(manifest), encoding="utf-8")
    portal = run_root / "portal-e2e"
    (portal / "playwright-report").mkdir(parents=True)
    (portal / "preflight").mkdir(parents=True)
    (portal / "junit").mkdir(parents=True)
    (portal / "compose.log").write_text("portal runner log\n", encoding="utf-8")
    (portal / "playwright-report" / "index.html").write_text(
        "<!doctype html><title>test</title>", encoding="utf-8"
    )
    (portal / "preflight" / "artifact-write-probe.json").write_text(
        '{"status":"writable"}\n', encoding="utf-8"
    )
    (portal / "cleanup.json").write_text(
        '{"compose_down_verified":true}\n', encoding="utf-8"
    )
    (portal / "runner-status.json").write_text(
        json.dumps(
            {
                "orchestration_completed": True,
                "runner_passed": True,
                "compose_logs_verified": True,
                "cleanup_verified": True,
                "source_tree_unchanged": True,
            }
        ),
        encoding="utf-8",
    )
    case_specs = (
        ("ARTIFACT-001", "BLD-08", "artifact"),
        ("EXECUTION-001", "E2E-05", "preflight"),
        ("EXECUTION-002", "E2E-06", "artifact"),
        ("EXECUTION-003", "E2E-07", "preflight"),
        ("EXECUTION-004", "E2E-08", "preflight"),
        ("SECURITY-001", "E2E-01", "network-isolation"),
        ("SECURITY-002", "E2E-02", "network-isolation"),
        ("SECURITY-003", "E2E-02", "network-isolation"),
    )
    rows = []
    metadata_cases = []
    for case_id, requirements, evidence_kind in case_specs:
        result = (
            '<skipped message="orchestration-only source-tree check" />'
            if case_id == "EXECUTION-004"
            else ""
        )
        rows.append(
            f"""  <testcase classname="portal" name="{case_id.lower()}" time="0.1">
    <properties>
      <property name="test_case_id" value="{case_id}" />
      <property name="requirement_ids" value="{requirements}" />
      <property name="critical" value="false" />
      <property name="hermes.case_source" value="traceability-matrix-placeholder" />
      <property name="hermes.coverage_claim" value="none" />
      <property name="hermes.acceptance_status" value="not-evaluated" />
      <property name="hermes.golden_status" value="not-applicable" />
      <property name="hermes.evidence_kind" value="{evidence_kind}" />
    </properties>
    {result}
  </testcase>"""
        )
        metadata_cases.append({"case_id": case_id})
    (portal / "junit" / "portal-e2e.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuite tests="8">\n'
        + "\n".join(rows)
        + "\n</testsuite>\n",
        encoding="utf-8",
    )
    (portal / "metadata.json").write_text(
        json.dumps(
            {
                "report_type": "hermes.portal-e2e.matrix-placeholder-execution",
                "cases": metadata_cases,
            }
        ),
        encoding="utf-8",
    )


def _run_collector(
    results_root: Path,
    run_id: str,
    environment_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["TEST_RESULTS_ROOT"] = str(results_root)
    environment.update(environment_overrides or {})
    return subprocess.run(
        [sys.executable, str(COLLECTOR), run_id],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_collector_writes_machine_and_human_summary(tmp_path: Path) -> None:
    run_root = tmp_path / "run-pass"
    _write_junit(run_root)

    completed = _run_collector(tmp_path, "run-pass")

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    summary_schema = json.loads(
        (REPO_ROOT / "tests/reporting/summary.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(summary_schema).validate(summary)
    assert summary["status"] == "PASS"
    assert summary["cases"][0]["test_case_id"] == "RUNTIME-001"
    assert summary["cases"][0]["requirement_ids"] == ["RT-01", "RT-02"]
    assert "RUNTIME-001" in (run_root / "summary.md").read_text(encoding="utf-8")


def test_collector_fails_when_critical_case_is_skipped(tmp_path: Path) -> None:
    run_root = tmp_path / "run-skip"
    _write_junit(run_root, status="skipped")

    completed = _run_collector(tmp_path, "run-skip")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "FAIL"
    assert summary["critical_not_passed"] == ["RUNTIME-001"]


def test_collector_fails_when_artifact_contains_test_secret(tmp_path: Path) -> None:
    run_root = tmp_path / "run-secret"
    _write_junit(run_root)
    (run_root / "leak.log").write_text("TEST_SECRET_123456", encoding="utf-8")

    completed = _run_collector(tmp_path, "run-secret")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["secret_findings"] == ["leak.log"]


def test_collector_normalizes_nested_junit_to_canonical_directory(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-nested"
    _write_junit(run_root, nested=True)

    completed = _run_collector(tmp_path, "run-nested")

    assert completed.returncode == 0, completed.stderr
    assert (
        run_root / "junit" / "controller-e2e-core-start-controller.xml"
    ).is_file()


def test_collector_fails_when_requirement_metadata_is_missing(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-metadata"
    _write_junit(run_root, include_requirement_ids=False)

    completed = _run_collector(tmp_path, "run-metadata")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["metadata_errors"] == [
        "RUNTIME-001: missing requirement_ids JUnit property"
    ]


def test_collector_fails_when_manifest_is_missing(tmp_path: Path) -> None:
    run_root = tmp_path / "run-no-manifest"
    _write_junit(run_root)
    (run_root / "manifest.yaml").unlink()

    completed = _run_collector(tmp_path, "run-no-manifest")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["manifest_errors"] == ["manifest.yaml is missing"]


def test_collector_rejects_a_path_traversal_run_id(tmp_path: Path) -> None:
    completed = _run_collector(tmp_path, "../outside")

    assert completed.returncode == 80
    assert "unsupported characters" in completed.stderr


def test_collector_rejects_dot_and_compose_normalized_run_ids(
    tmp_path: Path,
) -> None:
    for run_id in (".", "..", "Upper", "a.b"):
        completed = _run_collector(tmp_path, run_id)
        assert completed.returncode == 80


def test_collector_preserves_placeholder_as_not_evaluated(tmp_path: Path) -> None:
    run_root = tmp_path / "run-infra"
    _write_portal_junit(run_root)

    completed = _run_collector(tmp_path, "run-infra")

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "INFRA_PASS"
    assert summary["counts"]["passed"] == 0
    assert summary["counts"]["not_evaluated"] == 8
    assert summary["cases"][0]["execution_status"] == "PASSED"
    assert summary["cases"][0]["status"] == "NOT_EVALUATED"


def test_collector_fails_for_zero_testcase_junit(tmp_path: Path) -> None:
    run_root = tmp_path / "run-empty"
    _write_junit(run_root)
    (run_root / "junit" / "controller.xml").write_text(
        '<testsuite tests="0" />', encoding="utf-8"
    )

    completed = _run_collector(tmp_path, "run-empty")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["counts"]["total"] == 0


def test_collector_scans_nested_runner_summaries_for_secrets(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-nested-secret"
    _write_junit(run_root)
    nested = run_root / "controller-e2e" / "core-start" / "summary.json"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text('{"detail":"TEST_SECRET_123456"}', encoding="utf-8")

    completed = _run_collector(tmp_path, "run-nested-secret")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["secret_findings"] == [
        "controller-e2e/core-start/summary.json"
    ]


def test_collector_scans_compressed_trace_members_for_secrets(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-trace-secret"
    _write_junit(run_root)
    trace_path = run_root / "controller-e2e" / "trace.zip"
    with zipfile.ZipFile(trace_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("trace.network", "header TEST_SECRET_123456 footer")

    completed = _run_collector(tmp_path, "run-trace-secret")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["secret_findings"] == [
        "controller-e2e/trace.zip!trace.network"
    ]


def test_collector_cannot_disable_the_default_secret_pattern(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-default-secret"
    _write_junit(run_root)
    (run_root / "leak.log").write_text("TEST_SECRET_123456", encoding="utf-8")

    completed = _run_collector(
        tmp_path,
        "run-default-secret",
        {"TEST_SECRET_PATTERNS": ""},
    )

    assert completed.returncode == 80


def test_collector_reports_invalid_testcase_duration_without_traceback(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-invalid-time"
    _write_junit(run_root)
    junit_path = run_root / "junit" / "controller.xml"
    junit_path.write_text(
        junit_path.read_text(encoding="utf-8").replace('time="0.1"', 'time="NaN?"'),
        encoding="utf-8",
    )

    completed = _run_collector(tmp_path, "run-invalid-time")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert "testcase time is not numeric" in summary["parse_errors"][0]


def test_collector_rejects_an_unapproved_case_mapping(tmp_path: Path) -> None:
    run_root = tmp_path / "run-unapproved-case"
    _write_junit(run_root)
    junit_path = run_root / "junit" / "controller.xml"
    junit_path.write_text(
        junit_path.read_text(encoding="utf-8").replace("RUNTIME-001", "RUNTIME-999"),
        encoding="utf-8",
    )

    completed = _run_collector(tmp_path, "run-unapproved-case")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert any("not approved" in error for error in summary["metadata_errors"])


def test_collector_fails_when_runner_status_disagrees_with_junit(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-runner-failure"
    _write_junit(run_root)
    status_path = run_root / "controller-e2e" / "runner-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["source_tree_unchanged"] = False
    status_path.write_text(json.dumps(status), encoding="utf-8")

    completed = _run_collector(tmp_path, "run-runner-failure")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert any("source_tree_unchanged" in error for error in summary["artifact_errors"])


def test_collector_rejects_symbolic_link_artifacts(tmp_path: Path) -> None:
    run_root = tmp_path / "run-symlink"
    _write_junit(run_root)
    (run_root / "linked-artifact").symlink_to(run_root / "manifest.yaml")

    completed = _run_collector(tmp_path, "run-symlink")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert any("symbolic-link artifact" in error for error in summary["artifact_errors"])


def test_collector_rejects_an_incomplete_suite_inventory(tmp_path: Path) -> None:
    run_root = tmp_path / "run-incomplete"
    _write_junit(run_root)
    junit_path = run_root / "junit" / "controller.xml"
    tree = ET.parse(junit_path)
    root = tree.getroot()
    root.remove(list(root.findall("testcase"))[-1])
    tree.write(junit_path, encoding="utf-8", xml_declaration=True)

    completed = _run_collector(tmp_path, "run-incomplete")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["inventory_errors"] == [
        "suite inventory is missing cases: RUNTIME-014"
    ]


def test_collector_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    run_root = tmp_path / "run-duplicate"
    _write_junit(run_root)
    junit_path = run_root / "junit" / "controller.xml"
    tree = ET.parse(junit_path)
    root = tree.getroot()
    root.append(deepcopy(root.find("testcase")))
    tree.write(junit_path, encoding="utf-8", xml_declaration=True)

    completed = _run_collector(tmp_path, "run-duplicate")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["inventory_errors"] == [
        "suite inventory has duplicate cases: RUNTIME-001"
    ]
