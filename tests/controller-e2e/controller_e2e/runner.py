"""Container entry point preserving pytest's machine-readable exit code."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def main() -> int:
    # The pinned image contains no retry plugin. Disabling auto-load also prevents
    # an injected plugin from silently retrying a Critical case.
    os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    from .config import RunnerConfig

    config = RunnerConfig.from_env()
    config.results_dir.mkdir(parents=True, exist_ok=True)

    import pytest

    project_root = Path(__file__).resolve().parents[1]
    arguments = [
        str(project_root / "tests" / "e2e"),
        "-p",
        "controller_e2e.pytest_plugin",
        f"--junitxml={config.results_dir / 'junit.xml'}",
        "-o",
        "cache_dir=/tmp/hermes-controller-e2e-pytest-cache",
        *sys.argv[1:],
    ]
    return int(pytest.main(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
