from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def spec_root() -> Path:
    configured = os.getenv("SPEC_ROOT")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(
        Path(__file__).resolve().parents[4] / "hermes-poc-specification-v0.1"
    )
    for candidate in candidates:
        if (candidate / "contracts" / "openapi" / "controller-api.yaml").is_file():
            return candidate.resolve()
    pytest.fail("Unit tests require SPEC_ROOT pointing to the specification bundle")
