import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from controller_e2e.errors import ContractAmbiguity, EnvironmentBlocker
from controller_e2e.pytest_plugin import _failure_classification


def test_environment_blocker_uses_acceptance_classification_name():
    assert (
        _failure_classification(EnvironmentBlocker("synthetic setup failure"))
        == "BLOCKED_BY_ENVIRONMENT"
    )


def test_contract_ambiguity_remains_distinct_from_platform_failure():
    assert (
        _failure_classification(ContractAmbiguity("synthetic ambiguity"))
        == "BLOCKED_BY_CONTRACT"
    )


def test_contract_ambiguity_classification_survives_canonical_junit(
    tmp_path: Path,
) -> None:
    test_file = tmp_path / "test_contract_blocked.py"
    junit_file = tmp_path / "junit.xml"
    results_dir = tmp_path / "results"
    test_file.write_text(
        """import pytest
from controller_e2e.errors import ContractAmbiguity

@pytest.mark.case(
    test_case_id="RUNTIME-009",
    requirement_ids=("RT-08",),
    critical=True,
)
def test_frozen_mapping_is_unpublished():
    raise ContractAmbiguity("synthetic frozen mapping ambiguity")
""",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    controller_project = Path(__file__).resolve().parents[2]
    environment.update(
        {
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONPATH": os.pathsep.join(
                filter(
                    None,
                    (str(controller_project), environment.get("PYTHONPATH", "")),
                )
            ),
            "RESULTS_DIR": str(results_dir),
            "SPEC_ROOT": str(tmp_path / "spec"),
        }
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "controller_e2e.pytest_plugin",
            f"--junitxml={junit_file}",
            "-o",
            "junit_family=legacy",
            str(test_file),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    properties = {
        item.get("name"): item.get("value")
        for item in ET.parse(junit_file).getroot().findall(
            ".//testcase/properties/property"
        )
    }
    assert properties["failure_classification"] == "BLOCKED_BY_CONTRACT"
