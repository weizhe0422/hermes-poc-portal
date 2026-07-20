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
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = REPO_ROOT / "scripts" / "collect-test-results"
FROZEN_CONTRACT_COMMIT = "febdea906a51bab59e582755c495ed2253fb64b8"
INTEGRATION_COMMIT = "0123456789abcdef0123456789abcdef01234567"
TEST_COMMIT = "5988c57e3533c570470181a244e3d2bffa0e963c"


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
        "contract_tag": "contract-m0-m1-v0.2.1",
        "contract_commit": FROZEN_CONTRACT_COMMIT,
        "contract_version": "0.2.1",
        "git_commit": INTEGRATION_COMMIT,
        "git_branch": None,
        "platform_commit": "59a2df63c5cedb1a44cc7804004e5d228413434d",
        "test_commit": TEST_COMMIT,
        "test_suite": "controller-e2e",
        "images": {
            "controller": "example.invalid/controller:candidate",
            "controller_e2e": "example.invalid/controller-e2e:0.1.0",
            "docker_engine_test": "example.invalid/docker-engine:test",
            "hermes_fixture": "example.invalid/hermes-fixture:0.1.0",
        },
        "image_ids": {
            "controller": f"sha256:{'a' * 64}",
            "controller_e2e": f"sha256:{'b' * 64}",
            "docker_engine_test": f"sha256:{'c' * 64}",
            "hermes_fixture": f"sha256:{'d' * 64}",
        },
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
    (snapshots / "controller-environment.json").write_text(
        json.dumps(
            {
                "schema_version": "0.2.0",
                "contract_tag": "contract-m0-m1-v0.2.1",
                "case": {
                    "test_case_id": "CONTROLLER-ENV-001",
                    "is_independent_container": True,
                    "uses_isolated_docker_engine": True,
                    "has_docker_socket": False,
                    "can_affect_dev_or_prod_containers": False,
                    "cleanup_limited_to_run_id": True,
                    "verdict": True,
                },
            }
        ),
        encoding="utf-8",
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
        ("CONTROLLER-ENV-001", "E2E-03,E2E-04"),
        ("RUNTIME-001", "RT-01,RT-02"),
        ("RUNTIME-003", "RT-03,RT-09"),
        ("RUNTIME-004", "RT-04"),
        ("RUNTIME-005", "RT-05"),
        ("RUNTIME-006", "RT-06"),
        ("RUNTIME-007", "RT-06"),
        ("RUNTIME-008", "RT-07"),
        ("RUNTIME-009", "RT-08"),
        ("RUNTIME-012", "RT-10,RT-11"),
        ("RUNTIME-013", "RT-13,NF-03"),
        ("RUNTIME-014", "RT-05"),
        ("RUNTIME-017", "RT-06"),
    )
    testcase_rows = []
    for case_id, requirements in case_specs:
        requirement_property = (
            f'<property name="requirement_ids" value="{requirements}" />'
            if include_requirement_ids or case_id != "RUNTIME-001"
            else ""
        )
        engine_property = (
            '<property name="engine_evidence" value="PASS" />\n'
            f'      <property name="engine_evidence_file" '
            f'value="evidence-{case_id}.json" />'
            if case_id.startswith("RUNTIME-") and case_id != "RUNTIME-001"
            else ""
        )
        outer_property = (
            '<property name="outer_evidence" value="PASS" />\n'
            '      <property name="outer_evidence_file" '
            'value="controller-environment.json" />'
            if case_id == "CONTROLLER-ENV-001"
            else ""
        )
        if case_id != "RUNTIME-001" or status == "passed":
            result = ""
        elif status == "failed":
            result = '<failure message="contract mismatch" />'
        else:
            result = '<skipped message="coverage gap" />'
        is_runtime = case_id.startswith("RUNTIME-")
        case_source = (
            "frozen-runtime-case" if is_runtime else "frozen-infrastructure-case"
        )
        evidence_kind = "black-box" if is_runtime else "controller-isolation"
        testcase_rows.append(
            f"""  <testcase classname="controller" name="{case_id.lower()}" time="0.1">
    <properties>
      <property name="test_case_id" value="{case_id}" />
      {requirement_property}
      <property name="critical" value="true" />
      <property name="hermes.case_source" value="{case_source}" />
      <property name="hermes.coverage_claim" value="case-level" />
      <property name="hermes.acceptance_status" value="case-evaluated" />
      <property name="hermes.golden_status" value="frozen-v0.2.1" />
      <property name="hermes.evidence_kind" value="{evidence_kind}" />
      {engine_property}
      {outer_property}
    </properties>
    {result}
  </testcase>"""
        )
    junit = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<testsuite tests="13">\n'
        + "\n".join(testcase_rows)
        + "\n</testsuite>\n"
    )
    junit_dir = run_root / ("controller-e2e/core-start" if nested else "junit")
    junit_dir.mkdir(parents=True)
    (junit_dir / "controller.xml").write_text(junit, encoding="utf-8")
    phase_status_rows = []
    for case_id, requirements in case_specs:
        if not case_id.startswith("RUNTIME-"):
            continue
        phase = case_id.lower()
        phase_dir = run_root / "controller-e2e" / phase
        phase_dir.mkdir(parents=True, exist_ok=True)
        (phase_dir / "summary.json").write_text(
            json.dumps({"overall_status": "PASS", "test_case_id": case_id}),
            encoding="utf-8",
        )
        (phase_dir / "summary.md").write_text(
            f"# {case_id}\n\nPASS\n", encoding="utf-8"
        )
        (phase_dir / "http-trace.jsonl").write_text(
            json.dumps({"test_case_id": case_id, "status": "synthetic"}) + "\n",
            encoding="utf-8",
        )
        (logs / f"controller-{phase}.log").write_text(
            f"synthetic log for {case_id}\n", encoding="utf-8"
        )
        phase_status_rows.append(
            json.dumps(
                {
                    "phase": phase,
                    "test_case_id": case_id,
                    "runner_exit_code": 0,
                    "engine_exit_code": 0,
                }
            )
        )
        if case_id == "RUNTIME-001":
            continue
        engine_evidence = {
            "test_case_id": case_id,
            "requirement_ids": requirements.split(","),
            "verdict": True,
        }
        if case_id == "RUNTIME-008":
            engine_evidence["winning_action"] = "START"
        (snapshots / f"evidence-{case_id}.json").write_text(
            json.dumps(engine_evidence), encoding="utf-8"
        )
        (snapshots / f"events-{case_id}.jsonl").write_text(
            '{"synthetic":"event evidence"}\n', encoding="utf-8"
        )
    (run_root / "controller-e2e" / "phase-status.jsonl").write_text(
        "\n".join(phase_status_rows) + "\n", encoding="utf-8"
    )
    (run_root / "controller-e2e" / "runtime-008" / "engine-context.json").write_text(
        '{"test_case_id":"RUNTIME-008","winning_action":"START"}\n',
        encoding="utf-8",
    )


def _write_portal_junit(run_root: Path) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_root.name,
        "fixture_type": "SYNTHETIC",
        "spec_version": "0.1.0",
        "contract_tag": "contract-m0-m1-v0.2.1",
        "contract_commit": FROZEN_CONTRACT_COMMIT,
        "contract_version": "0.2.1",
        "git_commit": INTEGRATION_COMMIT,
        "git_branch": None,
        "platform_commit": "59a2df63c5cedb1a44cc7804004e5d228413434d",
        "test_commit": TEST_COMMIT,
        "test_suite": "portal-e2e",
        "images": {
            "controller": "example.invalid/controller:candidate",
            "docker_engine_test": "example.invalid/docker-engine:test",
            "hermes_fixture": "example.invalid/hermes-fixture:0.1.0",
            "portal": "example.invalid/portal:candidate",
            "portal_e2e": "example.invalid/portal-e2e:0.1.0",
        },
        "image_ids": {
            "controller": f"sha256:{'a' * 64}",
            "docker_engine_test": f"sha256:{'c' * 64}",
            "hermes_fixture": f"sha256:{'d' * 64}",
            "portal": f"sha256:{'e' * 64}",
            "portal_e2e": f"sha256:{'f' * 64}",
        },
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
    (portal / "summary.json").write_text(
        '{"overall_status":"PASS"}\n', encoding="utf-8"
    )
    case_specs = (
        ("ARTIFACT-001", "BLD-08", "artifact"),
        ("EXECUTION-001", "E2E-05", "execution-probe"),
        ("EXECUTION-002", "E2E-06", "execution-probe"),
        ("EXECUTION-003", "E2E-07", "execution-probe"),
        ("EXECUTION-004", "E2E-08", "runner-isolation"),
        ("SECURITY-001", "BLD-07", "host-network"),
        ("SECURITY-002", "E2E-01,E2E-02", "network-isolation"),
        ("SECURITY-003", "E2E-02", "runner-isolation"),
    )
    rows = []
    metadata_cases = []
    for case_id, requirements, evidence_kind in case_specs:
        result = ""
        outer_property = (
            '<property name="outer_evidence" value="PASS" />\n'
            '      <property name="outer_evidence_file" '
            'value="infrastructure-evidence.json" />'
            if case_id
            in {
                "SECURITY-001",
                "SECURITY-002",
                "SECURITY-003",
                "EXECUTION-004",
                "ARTIFACT-001",
            }
            else ""
        )
        rows.append(
            f"""  <testcase classname="portal" name="{case_id.lower()}" time="0.1">
    <properties>
      <property name="test_case_id" value="{case_id}" />
      <property name="requirement_ids" value="{requirements}" />
      <property name="critical" value="true" />
      <property name="hermes.case_source" value="frozen-infrastructure-case" />
      <property name="hermes.coverage_claim" value="case-level" />
      <property name="hermes.acceptance_status" value="case-evaluated" />
      <property name="hermes.golden_status" value="frozen-v0.2.1" />
      <property name="hermes.evidence_kind" value="{evidence_kind}" />
      {outer_property}
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
                "report_type": "hermes.portal-e2e.frozen-infrastructure-execution",
                "cases": metadata_cases,
            }
        ),
        encoding="utf-8",
    )
    trace_path = portal / "execution-probe" / "test-output" / "probe" / "trace.zip"
    trace_path.parent.mkdir(parents=True)
    with zipfile.ZipFile(trace_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("trace.network", "synthetic trace evidence")
    (portal / "execution-probe" / "playwright.log").write_text(
        "intentional failure retained\n", encoding="utf-8"
    )
    (portal / "infrastructure-evidence.json").write_text(
        json.dumps(
            {
                "schema_version": "0.2.0",
                "contract_tag": "contract-m0-m1-v0.2.1",
                "cases": {
                    "SECURITY-001": {
                        "portal_running": True,
                        "controller_running": True,
                        "hermes_running": True,
                        "host_ports_published": [8080],
                        "controller_published": False,
                        "hermes_published": False,
                        "verdict": True,
                    },
                    "SECURITY-002": {
                        "is_independent_container": True,
                        "networks": ["e2e-network"],
                        "can_connect_portal": True,
                        "can_connect_controller": False,
                        "can_connect_hermes": False,
                        "verdict": True,
                    },
                    "SECURITY-003": {
                        "has_docker_socket": False,
                        "has_knowledge_mount": False,
                        "has_skill_mount": False,
                        "has_formal_volume": False,
                        "has_writable_source_mount": False,
                        "can_access_git_metadata": False,
                        "verdict": True,
                    },
                    "EXECUTION-004": {
                        "git_status_unchanged": True,
                        "runner_has_git_metadata": False,
                        "runner_has_writable_source": False,
                        "only_gitignore_artifacts_allowed": True,
                        "verdict": True,
                    },
                    "ARTIFACT-001": {
                        "written_to_independent_volume": True,
                        "readable_after_runner_exit": True,
                        "required_files_present": {
                            "manifest": True,
                            "summary": True,
                            "junit": True,
                        },
                        "trace_paths": [
                            "portal-e2e/execution-probe/test-output/probe/trace.zip"
                        ],
                        "log_paths": ["portal-e2e/execution-probe/playwright.log"],
                        "secret_findings": [],
                        "verdict": True,
                    },
                },
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


def _run_master_collector(
    results_root: Path,
    master_run_id: str,
    infrastructure_run_id: str,
    runtime_run_id: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["TEST_RESULTS_ROOT"] = str(results_root)
    return subprocess.run(
        [
            sys.executable,
            str(COLLECTOR),
            "--master",
            master_run_id,
            infrastructure_run_id,
            runtime_run_id,
        ],
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
    runtime_001 = next(
        case for case in summary["cases"] if case["test_case_id"] == "RUNTIME-001"
    )
    assert runtime_001["requirement_ids"] == ["RT-01", "RT-02"]
    assert "RUNTIME-001" in (run_root / "summary.md").read_text(encoding="utf-8")


def test_collector_evaluates_the_complete_frozen_runtime_inventory(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-frozen-runtime"
    _write_junit(run_root)

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "PASS"
    assert summary["counts"] == {
        "total": 13,
        "passed": 13,
        "failed": 0,
        "skipped": 0,
        "not_evaluated": 0,
        "blocked_by_contract": 0,
    }
    assert [
        case["test_case_id"]
        for case in summary["cases"]
        if case["test_case_id"].startswith("RUNTIME-")
    ] == [
        case_id
        for case_id, _requirements in (
            ("RUNTIME-001", "RT-01,RT-02"),
            ("RUNTIME-003", "RT-03,RT-09"),
            ("RUNTIME-004", "RT-04"),
            ("RUNTIME-005", "RT-05"),
            ("RUNTIME-006", "RT-06"),
            ("RUNTIME-007", "RT-06"),
            ("RUNTIME-008", "RT-07"),
            ("RUNTIME-009", "RT-08"),
            ("RUNTIME-012", "RT-10,RT-11"),
            ("RUNTIME-013", "RT-13,NF-03"),
            ("RUNTIME-014", "RT-05"),
            ("RUNTIME-017", "RT-06"),
        )
    ]


def test_master_collector_classifies_all_31_cases_without_not_evaluated(
    tmp_path: Path,
) -> None:
    infrastructure_root = tmp_path / "infra-child"
    runtime_root = tmp_path / "runtime-child"
    _write_portal_junit(infrastructure_root)
    _write_junit(runtime_root)
    assert _run_collector(tmp_path, infrastructure_root.name).returncode == 0
    assert _run_collector(tmp_path, runtime_root.name).returncode == 0

    completed = _run_master_collector(
        tmp_path,
        "m0-m1-master",
        infrastructure_root.name,
        runtime_root.name,
    )

    assert completed.returncode == 0, completed.stderr
    master_root = tmp_path / "m0-m1-master"
    summary = json.loads((master_root / "summary.json").read_text(encoding="utf-8"))
    summary_schema = json.loads(
        (REPO_ROOT / "tests/reporting/summary.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(summary_schema).validate(summary)
    master_manifest = json.loads(
        (master_root / "manifest.yaml").read_text(encoding="utf-8")
    )
    manifest_schema = json.loads(
        (REPO_ROOT / "tests/reporting/manifest.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(manifest_schema).validate(master_manifest)
    assert master_manifest["git_commit"] == INTEGRATION_COMMIT
    assert master_manifest["git_branch"] is None
    assert master_manifest["test_commit"] == TEST_COMMIT
    assert summary["status"] == "PASS"
    assert summary["counts"] == {
        "total": 31,
        "passed": 21,
        "failed": 0,
        "skipped": 10,
        "not_evaluated": 0,
        "blocked_by_contract": 0,
        "deferred_by_milestone": 10,
    }
    classifications = {
        case["test_case_id"]: case["status"] for case in summary["cases"]
    }
    assert set(classifications.values()) == {"PASSED", "DEFERRED_BY_MILESTONE"}
    assert classifications["RUNTIME-017"] == "PASSED"
    assert classifications["CW-001"] == "DEFERRED_BY_MILESTONE"
    assert classifications["DEPLOY-005"] == "DEFERRED_BY_MILESTONE"
    assert all(case["status"] != "NOT_EVALUATED" for case in summary["cases"])
    master_junit = master_root / "junit" / "m0-m1-acceptance.xml"
    assert len(ET.parse(master_junit).getroot().findall("testcase")) == 31


def test_master_collector_rejects_shared_image_identity_drift(
    tmp_path: Path,
) -> None:
    infrastructure_root = tmp_path / "infra-image-child"
    runtime_root = tmp_path / "runtime-image-child"
    _write_portal_junit(infrastructure_root)
    _write_junit(runtime_root)
    assert _run_collector(tmp_path, infrastructure_root.name).returncode == 0
    assert _run_collector(tmp_path, runtime_root.name).returncode == 0
    runtime_manifest_path = runtime_root / "manifest.yaml"
    runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
    runtime_manifest["images"]["controller"] = "example.invalid/controller:retagged"
    runtime_manifest["image_ids"]["hermes_fixture"] = f"sha256:{'9' * 64}"
    runtime_manifest_path.write_text(json.dumps(runtime_manifest), encoding="utf-8")

    completed = _run_master_collector(
        tmp_path,
        "m0-m1-image-drift",
        infrastructure_root.name,
        runtime_root.name,
    )

    assert completed.returncode == 80
    summary = json.loads(
        (tmp_path / "m0-m1-image-drift" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "FAIL"
    assert "child manifests disagree on images.controller" in summary[
        "manifest_errors"
    ]
    assert "child manifests disagree on image_ids.hermes_fixture" in summary[
        "manifest_errors"
    ]


@pytest.mark.parametrize("field", ("git_commit", "test_commit"))
def test_master_collector_rejects_child_candidate_identity_drift(
    tmp_path: Path, field: str
) -> None:
    infrastructure_root = tmp_path / f"infra-{field}-child"
    runtime_root = tmp_path / f"runtime-{field}-child"
    _write_portal_junit(infrastructure_root)
    _write_junit(runtime_root)
    assert _run_collector(tmp_path, infrastructure_root.name).returncode == 0
    assert _run_collector(tmp_path, runtime_root.name).returncode == 0
    runtime_manifest_path = runtime_root / "manifest.yaml"
    runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
    runtime_manifest[field] = "9" * 40
    runtime_manifest_path.write_text(json.dumps(runtime_manifest), encoding="utf-8")

    completed = _run_master_collector(
        tmp_path,
        f"m0-m1-{field}-drift",
        infrastructure_root.name,
        runtime_root.name,
    )

    assert completed.returncode == 80
    summary = json.loads(
        (tmp_path / f"m0-m1-{field}-drift" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert f"child manifests disagree on {field}" in summary["manifest_errors"]


def test_master_collector_treats_child_branches_as_record_only(tmp_path: Path) -> None:
    infrastructure_root = tmp_path / "infra-detached-child"
    runtime_root = tmp_path / "runtime-attached-child"
    _write_portal_junit(infrastructure_root)
    _write_junit(runtime_root)
    runtime_manifest_path = runtime_root / "manifest.yaml"
    runtime_manifest = json.loads(runtime_manifest_path.read_text(encoding="utf-8"))
    runtime_manifest["git_branch"] = "integration-local"
    runtime_manifest_path.write_text(json.dumps(runtime_manifest), encoding="utf-8")
    assert _run_collector(tmp_path, infrastructure_root.name).returncode == 0
    assert _run_collector(tmp_path, runtime_root.name).returncode == 0

    completed = _run_master_collector(
        tmp_path,
        "m0-m1-record-only-branch",
        infrastructure_root.name,
        runtime_root.name,
    )

    assert completed.returncode == 0, completed.stderr
    master_manifest = json.loads(
        (tmp_path / "m0-m1-record-only-branch/manifest.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert master_manifest["git_branch"] is None


def test_master_collector_always_classifies_all_31_when_child_row_is_missing(
    tmp_path: Path,
) -> None:
    infrastructure_root = tmp_path / "infra-missing-row-child"
    runtime_root = tmp_path / "runtime-missing-row-child"
    _write_portal_junit(infrastructure_root)
    _write_junit(runtime_root)
    assert _run_collector(tmp_path, infrastructure_root.name).returncode == 0
    assert _run_collector(tmp_path, runtime_root.name).returncode == 0
    runtime_junit = runtime_root / "junit/controller.xml"
    tree = ET.parse(runtime_junit)
    target = next(
        testcase
        for testcase in tree.getroot().iter("testcase")
        if any(
            prop.get("name") == "test_case_id"
            and prop.get("value") == "RUNTIME-017"
            for prop in testcase.findall("./properties/property")
        )
    )
    tree.getroot().remove(target)
    tree.write(runtime_junit, encoding="utf-8", xml_declaration=True)

    completed = _run_master_collector(
        tmp_path,
        "m0-m1-missing-row",
        infrastructure_root.name,
        runtime_root.name,
    )

    assert completed.returncode == 80
    master_root = tmp_path / "m0-m1-missing-row"
    summary = json.loads((master_root / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["cases"]) == 31
    missing = next(
        case for case in summary["cases"] if case["test_case_id"] == "RUNTIME-017"
    )
    assert missing["status"] == "FAILED"
    assert missing["failure_classification"] == "BLOCKED_BY_ENVIRONMENT"
    master_junit = ET.parse(master_root / "junit/m0-m1-acceptance.xml").getroot()
    assert len(master_junit.findall("testcase")) == 31
    missing_row = next(
        testcase
        for testcase in master_junit.findall("testcase")
        if any(
            prop.get("name") == "test_case_id"
            and prop.get("value") == "RUNTIME-017"
            for prop in testcase.findall("./properties/property")
        )
    )
    assert missing_row.find("failure") is not None


def test_master_fail_status_is_represented_in_junit(
    tmp_path: Path,
) -> None:
    infrastructure_root = tmp_path / "infra-integrity-child"
    runtime_root = tmp_path / "runtime-integrity-child"
    _write_portal_junit(infrastructure_root)
    _write_junit(runtime_root)
    assert _run_collector(tmp_path, infrastructure_root.name).returncode == 0
    assert _run_collector(tmp_path, runtime_root.name).returncode == 0
    runner_status_path = runtime_root / "controller-e2e/runner-status.json"
    runner_status = json.loads(runner_status_path.read_text(encoding="utf-8"))
    runner_status["source_tree_unchanged"] = False
    runner_status_path.write_text(json.dumps(runner_status), encoding="utf-8")

    completed = _run_master_collector(
        tmp_path,
        "m0-m1-integrity-failed",
        infrastructure_root.name,
        runtime_root.name,
    )

    assert completed.returncode == 80
    master_root = tmp_path / "m0-m1-integrity-failed"
    summary = json.loads((master_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "FAIL"
    junit = ET.parse(master_root / "junit/m0-m1-acceptance.xml").getroot()
    assert len(junit.findall("testcase")) == 31
    assert any(
        row.find("failure") is not None or row.find("error") is not None
        for row in junit.findall("testcase")
    )


def test_master_collector_retains_a_frozen_child_failure(tmp_path: Path) -> None:
    infrastructure_root = tmp_path / "infra-failure-child"
    runtime_root = tmp_path / "runtime-failure-child"
    _write_portal_junit(infrastructure_root)
    _write_junit(runtime_root)
    assert _run_collector(tmp_path, infrastructure_root.name).returncode == 0
    assert _run_collector(tmp_path, runtime_root.name).returncode == 0
    runtime_junit = next((runtime_root / "junit").glob("*.xml"))
    tree = ET.parse(runtime_junit)
    target = next(
        testcase
        for testcase in tree.getroot().iter("testcase")
        if any(
            prop.get("name") == "test_case_id"
            and prop.get("value") == "RUNTIME-001"
            for prop in testcase.findall("./properties/property")
        )
    )
    ET.SubElement(target, "failure", message="frozen Expected Result mismatch")
    tree.write(runtime_junit, encoding="utf-8", xml_declaration=True)
    runner_status_path = runtime_root / "controller-e2e/runner-status.json"
    runner_status = json.loads(runner_status_path.read_text(encoding="utf-8"))
    runner_status["runner_passed"] = False
    runner_status_path.write_text(json.dumps(runner_status), encoding="utf-8")
    child_summary_path = runtime_root / "summary.json"
    child_summary = json.loads(child_summary_path.read_text(encoding="utf-8"))
    child_summary["status"] = "FAIL"
    child_summary_path.write_text(json.dumps(child_summary), encoding="utf-8")

    completed = _run_master_collector(
        tmp_path,
        "m0-m1-failed-master",
        infrastructure_root.name,
        runtime_root.name,
    )

    assert completed.returncode == 80
    summary = json.loads(
        (tmp_path / "m0-m1-failed-master" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "FAIL"
    assert summary["counts"]["failed"] == 1
    assert summary["critical_not_passed"] == ["RUNTIME-001"]
    assert summary["artifact_errors"] == []
    assert next(
        case for case in summary["cases"] if case["test_case_id"] == "ARTIFACT-001"
    )["status"] == "PASSED"
    assert next(
        case for case in summary["cases"] if case["test_case_id"] == "RUNTIME-001"
    )["status"] == "FAILED"


def test_master_junit_marks_outer_evidence_validation_failures(
    tmp_path: Path,
) -> None:
    infrastructure_root = tmp_path / "infra-evidence-child"
    runtime_root = tmp_path / "runtime-evidence-child"
    _write_portal_junit(infrastructure_root)
    _write_junit(runtime_root)
    assert _run_collector(tmp_path, infrastructure_root.name).returncode == 0
    assert _run_collector(tmp_path, runtime_root.name).returncode == 0
    (infrastructure_root / "portal-e2e/infrastructure-evidence.json").unlink()

    completed = _run_master_collector(
        tmp_path,
        "m0-m1-evidence-failed",
        infrastructure_root.name,
        runtime_root.name,
    )

    assert completed.returncode == 80
    master_root = tmp_path / "m0-m1-evidence-failed"
    summary = json.loads((master_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["counts"]["failed"] == 5
    tree = ET.parse(master_root / "junit/m0-m1-acceptance.xml")
    security_001 = next(
        testcase
        for testcase in tree.getroot().iter("testcase")
        if any(
            prop.get("name") == "test_case_id"
            and prop.get("value") == "SECURITY-001"
            for prop in testcase.findall("./properties/property")
        )
    )
    assert security_001.find("failure") is not None


def test_master_collector_preserves_explicit_contract_blocked_as_a_distinct_outcome(
    tmp_path: Path,
) -> None:
    infrastructure_root = tmp_path / "infra-contract-child"
    runtime_root = tmp_path / "runtime-contract-child"
    _write_portal_junit(infrastructure_root)
    _write_junit(runtime_root)
    runtime_junit = runtime_root / "junit/controller.xml"
    tree = ET.parse(runtime_junit)
    blocked_case = next(
        testcase
        for testcase in tree.getroot().iter("testcase")
        if any(
            prop.get("name") == "test_case_id"
            and prop.get("value") == "RUNTIME-001"
            for prop in testcase.findall("./properties/property")
        )
    )
    properties = blocked_case.find("properties")
    assert properties is not None
    ET.SubElement(
        properties,
        "property",
        name="failure_classification",
        value="BLOCKED_BY_CONTRACT",
    )
    ET.SubElement(blocked_case, "failure", message="Synthetic Contract ambiguity")
    tree.write(runtime_junit, encoding="utf-8", xml_declaration=True)
    runner_status_path = runtime_root / "controller-e2e/runner-status.json"
    runner_status = json.loads(runner_status_path.read_text(encoding="utf-8"))
    runner_status["runner_passed"] = False
    runner_status_path.write_text(json.dumps(runner_status), encoding="utf-8")
    assert _run_collector(tmp_path, infrastructure_root.name).returncode == 0
    assert _run_collector(tmp_path, runtime_root.name).returncode == 80

    completed = _run_master_collector(
        tmp_path,
        "m0-m1-contract-blocked",
        infrastructure_root.name,
        runtime_root.name,
    )

    assert completed.returncode == 80
    master_root = tmp_path / "m0-m1-contract-blocked"
    summary = json.loads((master_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "CONTRACT_BLOCKED"
    assert summary["counts"] == {
        "total": 31,
        "passed": 20,
        "failed": 0,
        "blocked_by_contract": 1,
        "skipped": 10,
        "not_evaluated": 0,
        "deferred_by_milestone": 10,
    }
    case_ids = [case["test_case_id"] for case in summary["cases"]]
    assert len(case_ids) == len(set(case_ids)) == 31
    assert summary["critical_not_passed"] == ["RUNTIME-001"]
    assert next(
        case for case in summary["cases"] if case["test_case_id"] == "RUNTIME-001"
    )["status"] == "BLOCKED_BY_CONTRACT"


def test_collector_fails_when_critical_case_is_skipped(tmp_path: Path) -> None:
    run_root = tmp_path / "run-skip"
    _write_junit(run_root, status="skipped")

    completed = _run_collector(tmp_path, "run-skip")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "FAIL"
    assert summary["critical_not_passed"] == ["RUNTIME-001"]


def test_collector_classifies_explicit_contract_ambiguity_without_platform_failure(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-contract-blocked"
    _write_junit(run_root)
    junit_path = run_root / "junit/controller.xml"
    tree = ET.parse(junit_path)
    target = next(
        testcase
        for testcase in tree.getroot().iter("testcase")
        if any(
            prop.get("name") == "test_case_id"
            and prop.get("value") == "RUNTIME-001"
            for prop in testcase.findall("./properties/property")
        )
    )
    properties = target.find("properties")
    assert properties is not None
    ET.SubElement(
        properties,
        "property",
        name="failure_classification",
        value="BLOCKED_BY_CONTRACT",
    )
    ET.SubElement(
        target,
        "failure",
        message="Synthetic Contract ambiguity",
    )
    tree.write(junit_path, encoding="utf-8", xml_declaration=True)
    runner_status_path = run_root / "controller-e2e/runner-status.json"
    runner_status = json.loads(runner_status_path.read_text(encoding="utf-8"))
    runner_status["runner_passed"] = False
    runner_status_path.write_text(json.dumps(runner_status), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "CONTRACT_BLOCKED"
    assert summary["counts"]["passed"] == 12
    assert summary["counts"]["failed"] == 0
    assert summary["counts"]["blocked_by_contract"] == 1
    assert summary["critical_not_passed"] == ["RUNTIME-001"]
    blocked_case = next(
        case for case in summary["cases"] if case["test_case_id"] == "RUNTIME-001"
    )
    assert blocked_case["status"] == "BLOCKED_BY_CONTRACT"
    assert blocked_case["failure_classification"] == "BLOCKED_BY_CONTRACT"


def test_collector_allows_empty_no_lifecycle_engine_event_windows(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-empty-noop-events"
    _write_junit(run_root)
    snapshots = run_root / "controller-e2e/docker-snapshots"
    for case_id in ("RUNTIME-006", "RUNTIME-007"):
        (snapshots / f"events-{case_id}.jsonl").write_text("", encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "PASS"


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


def test_collector_requires_platform_candidate_provenance(tmp_path: Path) -> None:
    run_root = tmp_path / "run-no-platform-provenance"
    _write_junit(run_root)
    manifest_path = run_root / "manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("platform_commit")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["manifest_errors"] == [
        "manifest.platform_commit must be a 40-character lowercase commit"
    ]


def test_collector_requires_frozen_contract_provenance(tmp_path: Path) -> None:
    run_root = tmp_path / "run-no-contract-provenance"
    _write_junit(run_root)
    manifest_path = run_root / "manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("contract_tag")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["manifest_errors"] == [
        "manifest.contract_tag must equal 'contract-m0-m1-v0.2.1'"
    ]


def test_manifest_schema_describes_frozen_contract_provenance(tmp_path: Path) -> None:
    run_root = tmp_path / "run-manifest-schema"
    _write_junit(run_root)
    manifest = json.loads((run_root / "manifest.yaml").read_text(encoding="utf-8"))
    manifest_schema = json.loads(
        (REPO_ROOT / "tests/reporting/manifest.schema.json").read_text(encoding="utf-8")
    )

    Draft202012Validator(manifest_schema).validate(manifest)


def test_manifest_schema_accepts_an_attached_branch_record(tmp_path: Path) -> None:
    run_root = tmp_path / "run-attached-manifest"
    _write_junit(run_root)
    manifest_path = run_root / "manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["git_branch"] = "integration-local"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_schema = json.loads(
        (REPO_ROOT / "tests/reporting/manifest.schema.json").read_text(encoding="utf-8")
    )

    Draft202012Validator(manifest_schema).validate(manifest)
    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("case_label", "branch_value"),
    (("missing", "missing"), ("empty", "")),
)
def test_collector_requires_a_nullable_branch_record(
    tmp_path: Path, case_label: str, branch_value: str
) -> None:
    run_root = tmp_path / f"run-branch-{case_label}"
    _write_junit(run_root)
    manifest_path = run_root / "manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if branch_value == "missing":
        manifest.pop("git_branch")
    else:
        manifest["git_branch"] = branch_value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["manifest_errors"] == [
        "manifest.git_branch must be null or a non-empty branch record"
    ]


def test_collector_requires_test_candidate_provenance(tmp_path: Path) -> None:
    run_root = tmp_path / "run-no-test-provenance"
    _write_junit(run_root)
    manifest_path = run_root / "manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("test_commit")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["manifest_errors"] == [
        "manifest.test_commit must be a 40-character lowercase commit"
    ]


def test_collector_does_not_require_an_oci_revision_label(tmp_path: Path) -> None:
    run_root = tmp_path / "run-no-oci-revision-label"
    _write_junit(run_root)
    manifest = json.loads((run_root / "manifest.yaml").read_text(encoding="utf-8"))
    assert "oci_labels" not in manifest
    assert "org.opencontainers.image.revision" not in json.dumps(manifest)

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 0, completed.stderr


def test_collector_requires_image_ids_for_every_image(tmp_path: Path) -> None:
    run_root = tmp_path / "run-incomplete-image-ids"
    _write_junit(run_root)
    manifest_path = run_root / "manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["image_ids"].pop("controller")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["manifest_errors"] == [
        "manifest.image_ids keys must match manifest.images keys"
    ]


def test_collector_requires_suite_specific_product_image_role(tmp_path: Path) -> None:
    run_root = tmp_path / "run-no-product-image"
    _write_junit(run_root)
    manifest_path = run_root / "manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["images"].pop("controller")
    manifest["image_ids"].pop("controller")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["manifest_errors"] == [
        "manifest.images roles must equal "
        "controller,controller_e2e,docker_engine_test,hermes_fixture"
    ]


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


def test_collector_evaluates_the_complete_frozen_portal_infrastructure_inventory(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-infra"
    _write_portal_junit(run_root)

    completed = _run_collector(tmp_path, "run-infra")

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "PASS"
    assert summary["counts"]["passed"] == 8
    assert summary["counts"]["not_evaluated"] == 0
    assert summary["cases"][0]["execution_status"] == "PASSED"
    assert summary["cases"][0]["status"] == "PASSED"


def test_collector_does_not_treat_the_failure_probe_junit_as_acceptance_cases(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-infra-with-probe"
    _write_portal_junit(run_root)
    probe_root = run_root / "portal-e2e" / "execution-probe"
    probe_root.mkdir(parents=True, exist_ok=True)
    (probe_root / "junit.xml").write_text(
        """<testsuite tests="1" failures="1">
<testcase classname="failure-probe" name="deterministic injected failure">
<failure message="intentional probe failure" />
</testcase></testsuite>""",
        encoding="utf-8",
    )

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["counts"]["total"] == 8
    assert summary["counts"]["failed"] == 0


def test_collector_rejects_missing_outer_infrastructure_evidence(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-infra-no-outer-evidence"
    _write_portal_junit(run_root)
    (run_root / "portal-e2e" / "infrastructure-evidence.json").unlink()

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "FAIL"
    assert "required artifact is missing: portal-e2e/infrastructure-evidence.json" in summary[
        "artifact_errors"
    ]
    failed_ids = {
        case["test_case_id"]
        for case in summary["cases"]
        if case["status"] == "FAILED"
    }
    assert failed_ids == {
        "SECURITY-001",
        "SECURITY-002",
        "SECURITY-003",
        "EXECUTION-004",
        "ARTIFACT-001",
    }
    canonical_junit = next((run_root / "junit").glob("*.xml"))
    junit_tree = ET.parse(canonical_junit)
    junit_security_001 = next(
        testcase
        for testcase in junit_tree.getroot().iter("testcase")
        if any(
            prop.get("name") == "test_case_id"
            and prop.get("value") == "SECURITY-001"
            for prop in testcase.findall("./properties/property")
        )
    )
    assert junit_security_001.find("failure") is not None


def test_collector_rejects_partial_outer_expected_field_evidence(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-infra-partial-outer-evidence"
    _write_portal_junit(run_root)
    evidence_path = run_root / "portal-e2e/infrastructure-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["cases"]["SECURITY-002"].pop("can_connect_hermes")
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert (
        "SECURITY-002 outer evidence can_connect_hermes must equal False"
        in summary["artifact_errors"]
    )
    failed = [
        case["test_case_id"]
        for case in summary["cases"]
        if case["status"] == "FAILED"
    ]
    assert failed == ["SECURITY-002"]


def test_collector_rejects_missing_security_001_running_precondition(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-infra-controller-not-running"
    _write_portal_junit(run_root)
    evidence_path = run_root / "portal-e2e" / "infrastructure-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["cases"]["SECURITY-001"]["controller_running"] = False
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert (
        "SECURITY-001 outer evidence controller_running must equal True"
        in summary["artifact_errors"]
    )
    failed = [
        case["test_case_id"]
        for case in summary["cases"]
        if case["status"] == "FAILED"
    ]
    assert failed == ["SECURITY-001"]


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


def test_collector_requires_each_runtime_engine_evidence_artifact(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-missing-runtime-engine-evidence"
    _write_junit(run_root)
    missing = run_root / "controller-e2e/docker-snapshots/evidence-RUNTIME-017.json"
    missing.unlink()

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert (
        "required artifact is missing: "
        "controller-e2e/docker-snapshots/evidence-RUNTIME-017.json"
    ) in summary["artifact_errors"]
    runtime_017 = next(
        case for case in summary["cases"] if case["test_case_id"] == "RUNTIME-017"
    )
    assert runtime_017["status"] == "FAILED"


def test_collector_requires_each_runtime_phase_log_and_http_trace(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-missing-runtime-phase-artifact"
    _write_junit(run_root)
    (run_root / "controller-e2e/logs/controller-runtime-017.log").unlink()
    (run_root / "controller-e2e/runtime-017/http-trace.jsonl").unlink()

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert (
        "required artifact is missing: "
        "controller-e2e/logs/controller-runtime-017.log"
    ) in summary["artifact_errors"]
    assert (
        "required artifact is missing: "
        "controller-e2e/runtime-017/http-trace.jsonl"
    ) in summary["artifact_errors"]


def test_collector_rejects_runtime_008_winner_evidence_drift(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-runtime-008-winner-drift"
    _write_junit(run_root)
    context_path = run_root / "controller-e2e/runtime-008/engine-context.json"
    context_path.write_text(
        '{"test_case_id":"RUNTIME-008","winning_action":"STOP"}\n',
        encoding="utf-8",
    )

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert (
        "RUNTIME-008 Engine evidence winner differs from API context"
        in summary["artifact_errors"]
    )
    runtime_008 = next(
        case for case in summary["cases"] if case["test_case_id"] == "RUNTIME-008"
    )
    assert runtime_008["status"] == "FAILED"


def test_collector_accepts_extended_runtime_008_engine_context(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-runtime-008-extended-context"
    _write_junit(run_root)
    context_path = run_root / "controller-e2e/runtime-008/engine-context.json"
    context_path.write_text(
        json.dumps(
            {
                "test_case_id": "RUNTIME-008",
                "accepted_actions": ["STOP", "START"],
                "operation_actions": ["START"],
                "winning_action": "START",
                "engine_observation": "START",
                "responses": [
                    {
                        "action": "STOP",
                        "http_status": 200,
                        "operation_action": None,
                    },
                    {
                        "action": "START",
                        "http_status": 202,
                        "operation_action": "START",
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "PASS"


def test_collector_rejects_contradictory_runtime_008_engine_context(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-runtime-008-contradictory-context"
    _write_junit(run_root)
    context_path = run_root / "controller-e2e/runtime-008/engine-context.json"
    context_path.write_text(
        json.dumps(
            {
                "test_case_id": "RUNTIME-008",
                "accepted_actions": ["START"],
                "operation_actions": ["START"],
                "winning_action": "STOP",
                "engine_observation": "STOP",
                "responses": [
                    {
                        "action": "START",
                        "http_status": 202,
                        "operation_action": "START",
                        "error_class": None,
                    },
                    {
                        "action": "STOP",
                        "http_status": 409,
                        "operation_action": None,
                        "error_class": None,
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert (
        "RUNTIME-008 Engine context observation is inconsistent"
        in summary["artifact_errors"]
    )


def test_collector_treats_failed_engine_verdict_as_case_failure_not_artifact_error(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "run-engine-invariant-failure"
    _write_junit(run_root)
    junit_path = run_root / "junit/controller.xml"
    tree = ET.parse(junit_path)
    target = next(
        testcase
        for testcase in tree.getroot().iter("testcase")
        if any(
            prop.get("name") == "test_case_id"
            and prop.get("value") == "RUNTIME-006"
            for prop in testcase.findall("./properties/property")
        )
    )
    engine_property = next(
        prop
        for prop in target.findall("./properties/property")
        if prop.get("name") == "engine_evidence"
    )
    engine_property.set("value", "FAIL")
    ET.SubElement(target, "failure", message="isolated Engine invariant failed")
    tree.write(junit_path, encoding="utf-8", xml_declaration=True)
    evidence_path = (
        run_root / "controller-e2e/docker-snapshots/evidence-RUNTIME-006.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["verdict"] = False
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    status_path = run_root / "controller-e2e/runner-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["runner_passed"] = False
    status_path.write_text(json.dumps(status), encoding="utf-8")

    completed = _run_collector(tmp_path, run_root.name)

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    runtime_006 = next(
        case for case in summary["cases"] if case["test_case_id"] == "RUNTIME-006"
    )
    assert runtime_006["status"] == "FAILED"
    assert summary["artifact_errors"] == []
    assert summary["metadata_errors"] == []


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
    root.remove(list(root.findall("testcase"))[-2])
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
    root.append(deepcopy(root.findall("testcase")[1]))
    tree.write(junit_path, encoding="utf-8", xml_declaration=True)

    completed = _run_collector(tmp_path, "run-duplicate")

    assert completed.returncode == 80
    summary = json.loads((run_root / "summary.json").read_text(encoding="utf-8"))
    assert summary["inventory_errors"] == [
        "suite inventory has duplicate cases: RUNTIME-001"
    ]
