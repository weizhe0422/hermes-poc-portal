from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[2]
APPLIER = REPO_ROOT / "scripts" / "apply-controller-engine-evidence"


def _junit(path: Path, case_id: str) -> None:
    path.write_text(
        f"""<testsuites failures="0"><testsuite failures="0">
<testcase name="engine target"><properties>
<property name="test_case_id" value="{case_id}" />
<property name="requirement_ids" value="RT-06" />
<property name="critical" value="true" />
</properties></testcase></testsuite></testsuites>""",
        encoding="utf-8",
    )
    (path.parent / "summary.json").write_text(
        json.dumps(
            {
                "overall_status": "PASS",
                "counts": {"passed": 1, "failed": 0, "skipped": 0, "not_run": 0},
                "results": [
                    {
                        "status": "PASS",
                        "failure_classification": "NONE",
                        "failure": None,
                        "properties": {"test_case_id": case_id},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (path.parent / "summary.md").write_text(
        "Overall: **PASS**\n", encoding="utf-8"
    )


def test_failed_engine_evidence_changes_the_case_junit_verdict(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    evidence = tmp_path / "invariants-core.json"
    _junit(junit, "RUNTIME-006")
    evidence.write_text(
        json.dumps(
            {
                "phase": "core",
                "test_case_id": "RUNTIME-006",
                "verdict": False,
                "no_container_created_by_controller": False,
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(APPLIER), str(evidence), str(junit)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    testcase = ET.parse(junit).getroot().find(".//testcase")
    assert testcase is not None
    assert testcase.find("failure") is not None
    properties = {
        item.get("name"): item.get("value")
        for item in testcase.findall("./properties/property")
    }
    assert properties["engine_evidence"] == "FAIL"
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["overall_status"] == "FAIL"
    assert summary["counts"]["failed"] == 1


def test_passing_engine_evidence_is_attached_without_failure(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    evidence = tmp_path / "invariants-persistence.json"
    _junit(junit, "RUNTIME-014")
    evidence.write_text(
        json.dumps(
            {
                "phase": "persistence",
                "test_case_id": "RUNTIME-014",
                "verdict": True,
                "restart_transition_observed": True,
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(APPLIER), str(evidence), str(junit)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    testcase = ET.parse(junit).getroot().find(".//testcase")
    assert testcase is not None
    assert testcase.find("failure") is None
    assert any(
        item.get("name") == "engine_evidence" and item.get("value") == "PASS"
        for item in testcase.findall("./properties/property")
    )


def test_runtime_003_engine_start_evidence_is_supported(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    evidence = tmp_path / "invariants-core-start.json"
    _junit(junit, "RUNTIME-003")
    evidence.write_text(
        json.dumps(
            {
                "phase": "core-start",
                "test_case_id": "RUNTIME-003",
                "verdict": True,
                "runtime_running": True,
                "runtime_start_events": 1,
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(APPLIER), str(evidence), str(junit)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    properties = {
        item.get("name"): item.get("value")
        for item in ET.parse(junit).getroot().findall(
            ".//testcase/properties/property"
        )
    }
    assert properties["engine_evidence"] == "PASS"
