from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_GUARD = REPO_ROOT / "scripts" / "verify-acceptance-source"
CONTRACT_TAG = "contract-m0-m1-v0.2.1"
ENTRY_POINTS = (
    "scripts/run-portal-e2e",
    "scripts/run-controller-e2e",
    "scripts/run-m0-m1-acceptance",
)


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write(repository: Path, relative_path: str, content: str) -> None:
    destination = repository / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", message)
    return _git(repository, "rev-parse", "HEAD")


def _acceptance_repository(tmp_path: Path, *, detached: bool) -> tuple[Path, dict[str, str]]:
    assert SOURCE_GUARD.is_file(), "the CA-4 source guard must exist"

    repository = tmp_path / "repository"
    remote = tmp_path / "origin.git"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.email", "ca4@example.invalid")
    _git(repository, "config", "user.name", "CA-4 Test")

    _write(repository, "hermes-poc-specification-v0.1/contracts/versions.yaml", "version: 0.2.1\n")
    _write(repository, "hermes-poc-specification-v0.1/contracts/openapi/controller-api.yaml", "openapi: 3.1.0\n")
    _write(repository, "hermes-poc-specification-v0.1/test-cases/infrastructure/cases.yaml", "cases: []\n")
    _write(repository, "hermes-poc-specification-v0.1/test-cases/runtime/cases.yaml", "cases: []\n")
    _write(repository, "hermes-poc-specification-v0.1/docs/requirements.md", "frozen\n")
    _write(repository, ".DS_Store", "frozen root artifact\n")
    contract_commit = _commit(repository, "contract")
    _git(repository, "tag", "-a", CONTRACT_TAG, "-m", "frozen contract")

    for relative_path in (
        ".dockerignore",
        ".env.example",
        ".gitignore",
        "compose.yaml",
        "portal/Dockerfile",
        "controller/Dockerfile",
        "scripts/build-all",
        "scripts/dev-smoke-controller",
        "scripts/run-unit-tests",
    ):
        _write(repository, relative_path, f"platform-owned: {relative_path}\n")
    platform_commit = _commit(repository, "platform")

    copied_scripts = {
        "scripts/verify-acceptance-source": SOURCE_GUARD,
        **{relative_path: REPO_ROOT / relative_path for relative_path in ENTRY_POINTS},
    }
    for relative_path, source in copied_scripts.items():
        shutil.copy2(source, repository / relative_path)
    for relative_path in (
        "README.md",
        "compose.e2e.portal.yaml",
        "compose.e2e.controller.yaml",
        "tests/hermes-fixture/Dockerfile",
        "tests/controller-e2e/Dockerfile",
        "tests/portal-e2e/Dockerfile",
        "scripts/apply-controller-engine-evidence",
        "scripts/bootstrap-controller-e2e-engine",
        "scripts/cleanup-controller-e2e-engine",
        "scripts/collect-controller-e2e-engine",
        "scripts/collect-controller-environment-evidence",
        "scripts/collect-portal-infrastructure-evidence",
        "scripts/collect-test-results",
        "scripts/finalize-infrastructure-evidence",
        "scripts/prepare-controller-e2e-engine",
        "scripts/run-controller-e2e",
        "scripts/run-m0-m1-acceptance",
        "scripts/run-portal-e2e",
        "scripts/verify-controller-e2e-engine",
    ):
        if relative_path in copied_scripts:
            continue
        _write(repository, relative_path, f"test-owned: {relative_path}\n")
    test_commit = _commit(repository, "test")

    _git(repository, "commit", "--allow-empty", "-m", "integration")
    integration_commit = _git(repository, "rev-parse", "HEAD")

    _git(repository.parent, "init", "--bare", str(remote))
    _git(repository, "remote", "add", "origin", str(remote))
    _git(
        repository,
        "push",
        "origin",
        f"{integration_commit}:refs/heads/integration/poc-rc-001",
    )
    _git(repository, "push", "origin", CONTRACT_TAG)

    if detached:
        _git(repository, "checkout", "--detach", integration_commit)
    else:
        _git(repository, "branch", "-M", "integration-local")

    environment = {
        "EXPECTED_INTEGRATION_COMMIT": integration_commit,
        "EXPECTED_INTEGRATION_REF": "refs/heads/integration/poc-rc-001",
        "PLATFORM_COMMIT": platform_commit,
        "TEST_COMMIT": test_commit,
        "CONTRACT_TAG": CONTRACT_TAG,
        "EXPECTED_CONTRACT_COMMIT": contract_commit,
    }
    return repository, environment


def _run_guard(repository: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    command_environment = os.environ.copy()
    command_environment.update(environment)
    return subprocess.run(
        [str(repository / "scripts/verify-acceptance-source")],
        cwd=repository,
        env=command_environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_source_guard_accepts_the_exact_detached_integration_candidate(tmp_path: Path) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)

    completed = _run_guard(repository, environment)

    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(completed.stdout)
    assert evidence["head"] == environment["EXPECTED_INTEGRATION_COMMIT"]
    assert evidence["head_tree"] == _git(repository, "rev-parse", "HEAD^{tree}")
    assert evidence["checkout_mode"] == "DETACHED"
    assert evidence["git_branch"] is None
    assert evidence["remote_ref_commit"] == environment["EXPECTED_INTEGRATION_COMMIT"]
    assert evidence["source_inventory"]
    assert len(evidence["source_inventory_sha256"]) == 64
    raw_inventory = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
    ).stdout
    assert evidence["source_inventory_sha256"] == hashlib.sha256(
        raw_inventory
    ).hexdigest()


def test_source_guard_accepts_a_branch_checkout_at_the_exact_commit(tmp_path: Path) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=False)

    completed = _run_guard(repository, environment)

    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(completed.stdout)
    assert evidence["checkout_mode"] == "BRANCH"
    assert evidence["git_branch"] == "integration-local"


@pytest.mark.parametrize(
    "invalid_commit",
    (
        "a" * 41,
        "a" * 7,
        "g" * 40,
        "A" * 40,
    ),
)
def test_source_guard_rejects_malformed_commit_values(
    tmp_path: Path, invalid_commit: str
) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    environment["EXPECTED_INTEGRATION_COMMIT"] = invalid_commit

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert "40-character lowercase commit" in completed.stderr


@pytest.mark.parametrize(
    "commit_name",
    ("PLATFORM_COMMIT", "TEST_COMMIT", "EXPECTED_CONTRACT_COMMIT"),
)
def test_source_guard_validates_every_candidate_commit_value(
    tmp_path: Path, commit_name: str
) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    environment[commit_name] = "short"

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert commit_name in completed.stderr
    assert "40-character lowercase commit" in completed.stderr


def test_source_guard_rejects_a_non_commit_object(tmp_path: Path) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    blob = repository / "blob.txt"
    blob.write_text("not a commit\n", encoding="utf-8")
    environment["PLATFORM_COMMIT"] = _git(repository, "hash-object", "-w", str(blob))
    blob.unlink()

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert "commit object" in completed.stderr


def test_source_guard_rejects_a_head_mismatch(tmp_path: Path) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    environment["EXPECTED_INTEGRATION_COMMIT"] = environment["PLATFORM_COMMIT"]

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert "HEAD is" in completed.stderr


def test_source_guard_rejects_a_remote_ref_mismatch(tmp_path: Path) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    remote = tmp_path / "origin.git"
    _git(
        repository,
        "--git-dir",
        str(remote),
        "update-ref",
        "refs/heads/integration/poc-rc-001",
        environment["TEST_COMMIT"],
    )

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert "expected" in completed.stderr


def test_source_guard_rejects_a_contract_tag_mismatch(tmp_path: Path) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    environment["EXPECTED_CONTRACT_COMMIT"] = environment["PLATFORM_COMMIT"]

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert "peels to" in completed.stderr


def test_source_guard_rejects_a_candidate_that_is_not_an_ancestor(tmp_path: Path) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    tree = _git(repository, "rev-parse", "HEAD^{tree}")
    unrelated = _git(repository, "commit-tree", tree, "-m", "unrelated")
    environment["PLATFORM_COMMIT"] = unrelated

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert "is not an ancestor" in completed.stderr


@pytest.mark.parametrize(
    ("relative_path", "expected_message"),
    (
        ("hermes-poc-specification-v0.1/docs/requirements.md", "Frozen Contract/Expected"),
        ("portal/Dockerfile", "Platform-owned"),
        ("tests/controller-e2e/Dockerfile", "Test-owned"),
        ("tests/hermes-fixture/Dockerfile", "tests/hermes-fixture tree"),
    ),
)
def test_source_guard_rejects_candidate_ownership_tree_drift(
    tmp_path: Path, relative_path: str, expected_message: str
) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=False)
    _write(repository, relative_path, "post-integration drift\n")
    drifted_integration = _commit(repository, "drift integration-owned content")
    _git(
        repository,
        "push",
        "--force",
        "origin",
        f"{drifted_integration}:refs/heads/integration/poc-rc-001",
    )
    environment["EXPECTED_INTEGRATION_COMMIT"] = drifted_integration

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert expected_message in completed.stderr


@pytest.mark.parametrize("drift_kind", ("staged", "unstaged", "untracked"))
def test_source_guard_rejects_any_working_tree_drift(
    tmp_path: Path, drift_kind: str
) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    if drift_kind == "untracked":
        _write(repository, "untracked.txt", "drift\n")
    else:
        _write(repository, "portal/Dockerfile", f"{drift_kind} drift\n")
        if drift_kind == "staged":
            _git(repository, "add", "portal/Dockerfile")

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert "source tree must be clean" in completed.stderr


def test_source_guard_rejects_an_unowned_committed_path(tmp_path: Path) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=False)
    _write(repository, "scripts/unowned-integration-hook", "unapproved\n")
    drifted_integration = _commit(repository, "add unowned integration path")
    _git(
        repository,
        "push",
        "--force",
        "origin",
        f"{drifted_integration}:refs/heads/integration/poc-rc-001",
    )
    environment["EXPECTED_INTEGRATION_COMMIT"] = drifted_integration

    completed = _run_guard(repository, environment)

    assert completed.returncode == 70
    assert "tracked path has no approved owner" in completed.stderr


def test_source_guard_ignores_repository_selection_environment_injection(
    tmp_path: Path,
) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    environment["GIT_DIR"] = str(tmp_path / "origin.git")
    environment["GIT_WORK_TREE"] = str(tmp_path)
    environment["GIT_INDEX_FILE"] = str(tmp_path / "attacker-index")

    completed = _run_guard(repository, environment)

    assert completed.returncode == 0, completed.stderr


def test_source_guard_disables_replace_objects(tmp_path: Path) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    _git(
        repository,
        "replace",
        environment["EXPECTED_INTEGRATION_COMMIT"],
        environment["PLATFORM_COMMIT"],
    )

    completed = _run_guard(repository, environment)

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("relative_entrypoint", "arguments"),
    (
        ("scripts/run-portal-e2e", ("--build-only",)),
        ("scripts/run-controller-e2e", ("--build-only",)),
        ("scripts/run-m0-m1-acceptance", ()),
    ),
)
def test_entrypoint_guard_failure_creates_no_artifact_and_never_calls_docker(
    tmp_path: Path, relative_entrypoint: str, arguments: tuple[str, ...]
) -> None:
    repository, environment = _acceptance_repository(tmp_path, detached=True)
    environment["EXPECTED_INTEGRATION_COMMIT"] = "short"
    results_root = tmp_path / "acceptance-artifacts"
    sentinel = tmp_path / "docker-called"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        f"#!/bin/sh\n: > {sentinel}\nexit 99\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    command_environment = os.environ.copy()
    command_environment.update(environment)
    command_environment.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{command_environment['PATH']}",
            "RUN_ID": "ca4-preflight-sentinel",
            "TEST_RESULTS_ROOT": str(results_root),
        }
    )

    completed = subprocess.run(
        [str(repository / relative_entrypoint), *arguments],
        cwd=repository,
        env=command_environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 70, completed.stderr
    assert "acceptance source guard failed" in completed.stderr
    assert not sentinel.exists()
    assert not results_root.exists()


@pytest.mark.parametrize(
    "relative_entrypoint",
    ("scripts/run-portal-e2e", "scripts/run-controller-e2e"),
)
def test_child_entrypoint_uses_guard_evidence_as_its_identity_baseline(
    relative_entrypoint: str,
) -> None:
    source = (REPO_ROOT / relative_entrypoint).read_text(encoding="utf-8")

    assert 'json.load(sys.stdin)["head"]' in source
    assert 'json.load(sys.stdin)["head_tree"]' in source
    assert 'json.load(sys.stdin)["git_branch"]' in source
    assert "git branch --show-current" not in source
    assert "org.opencontainers.image.revision" not in source
