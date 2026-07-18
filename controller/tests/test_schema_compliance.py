"""API 回應對 contract JSON Schema 的合規測試（DoD：JSON Response 通過對應 Schema）。

需要環境變數 CONTRACTS_DIR 指向規格 bundle 的 contracts/ 目錄
（scripts/run-unit-tests 以唯讀掛載提供）；未設定時跳過。
"""

import json
import os
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
from referencing import Registry, Resource  # noqa: E402

from tests.conftest import add_managed_fixture  # noqa: E402

CONTRACTS_DIR = os.environ.get("CONTRACTS_DIR")

pytestmark = pytest.mark.skipif(
    not CONTRACTS_DIR, reason="CONTRACTS_DIR not set (mounted by scripts/run-unit-tests)"
)

INSTANCE = "hermes-poc-001"


def build_validator(schema_name: str):
    schemas_dir = Path(CONTRACTS_DIR) / "schemas"  # type: ignore[arg-type]
    resources = []
    for schema_file in schemas_dir.glob("*.json"):
        contents = json.loads(schema_file.read_text(encoding="utf-8"))
        resource = Resource.from_contents(contents)
        resources.append((contents["$id"], resource))
    registry = Registry().with_resources(resources)
    main_schema = json.loads((schemas_dir / schema_name).read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(main_schema, registry=registry)


@pytest.fixture(scope="module")
def agent_instance_validator():
    return build_validator("agent-instance.schema.json")


@pytest.fixture(scope="module")
def error_response_validator():
    return build_validator("error-response.schema.json")


def test_status_response_matches_agent_instance_schema(runtime_app, agent_instance_validator):
    app = runtime_app()
    add_managed_fixture(app.adapter, status="created")
    body = app.client.get(f"/v1/instances/{INSTANCE}").json()
    agent_instance_validator.validate(body)


def test_running_status_response_matches_schema(runtime_app, agent_instance_validator):
    app = runtime_app()
    add_managed_fixture(app.adapter, status="running")
    body = app.client.get(f"/v1/instances/{INSTANCE}").json()
    agent_instance_validator.validate(body)
    assert body["state"] == "HEALTHY"


def test_not_provisioned_response_matches_schema(runtime_app, agent_instance_validator):
    app = runtime_app()
    body = app.client.get(f"/v1/instances/{INSTANCE}").json()
    agent_instance_validator.validate(body)
    assert body["state"] == "NOT_PROVISIONED"


def test_inflight_operation_response_matches_schema(runtime_app, agent_instance_validator):
    app = runtime_app(hermes_start_timeout_seconds=5)
    add_managed_fixture(app.adapter, status="created")
    app.probes.hermes = "UNAVAILABLE"
    body = app.client.post(f"/v1/instances/{INSTANCE}/start").json()
    agent_instance_validator.validate(body)
    assert body["operation"] is not None


def test_error_responses_match_error_schema(runtime_app, error_response_validator):
    app = runtime_app()
    # 404
    body = app.client.get("/v1/instances/no-such-id").json()
    error_response_validator.validate(body)
    # 409
    add_managed_fixture(app.adapter, status="exited")
    body = app.client.post(f"/v1/instances/{INSTANCE}/restart").json()
    error_response_validator.validate(body)
    # 422
    add_managed_fixture(app.adapter, status="running")
    body = app.client.get(f"/v1/instances/{INSTANCE}/logs?tail=99999").json()
    error_response_validator.validate(body)
