"""Instance API 整合測試（Mock Docker；對應 RUNTIME-001/003/006/012/013 語意）。"""

import time

from tests.conftest import add_managed_fixture

INSTANCE = "hermes-poc-001"


def wait_for_state(app, instance_id: str, state: str, timeout: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = app.client.get(f"/v1/instances/{instance_id}").json()
        if body["state"] == state:
            return body
        time.sleep(0.05)
    raise AssertionError(f"state never became {state}; last={body['state']}")


# ---- 查詢（RT-01、RT-02） ----


def test_status_of_stopped_managed_instance(runtime_app):
    # RUNTIME-001：已建立但停止的受管 Instance
    app = runtime_app()
    add_managed_fixture(app.adapter, status="created")
    response = app.client.get(f"/v1/instances/{INSTANCE}")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "STOPPED"
    assert body["container_status"] == "CREATED"
    assert body["instance_id"] == INSTANCE
    assert body["template_id"] == "hermes-poc-template-v1"


def test_status_unknown_instance_is_404(runtime_app):
    app = runtime_app()
    response = app.client.get("/v1/instances/no-such-id")
    assert response.status_code == 404
    assert response.json()["error_code"] == "INSTANCE_NOT_FOUND"


def test_status_not_provisioned_when_container_missing(runtime_app):
    app = runtime_app()
    response = app.client.get(f"/v1/instances/{INSTANCE}")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "NOT_PROVISIONED"
    assert body["container_status"] == "MISSING"


def test_list_instances_returns_registry_entries(runtime_app):
    app = runtime_app()
    add_managed_fixture(app.adapter)
    response = app.client.get("/v1/instances")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["instance_id"] == INSTANCE


# ---- Start（RT-03、RT-06、RT-09） ----


def test_start_from_stopped_reaches_healthy(runtime_app):
    # RUNTIME-003（v0.2）：202 必回 STARTING＋operation.action=START，最終 HEALTHY
    app = runtime_app()
    add_managed_fixture(app.adapter, status="created")
    response = app.client.post(f"/v1/instances/{INSTANCE}/start")
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["state"] == "STARTING"
    assert accepted["operation"]["action"] == "START"
    assert accepted["operation"]["operation_id"]
    body = wait_for_state(app, INSTANCE, "HEALTHY")
    assert body["hermes_status"] == "AVAILABLE"
    assert body["llm_status"] == "AVAILABLE"
    assert app.adapter.start_calls == [f"cid-{INSTANCE}"]


def test_start_when_healthy_is_idempotent_noop(runtime_app):
    # RUNTIME-006：已 Healthy 再 Start → 200，不重複操作 Container
    app = runtime_app()
    add_managed_fixture(app.adapter, status="running")
    response = app.client.post(f"/v1/instances/{INSTANCE}/start")
    assert response.status_code == 200
    assert response.json()["state"] == "HEALTHY"
    assert app.adapter.start_calls == []


def test_start_when_unhealthy_is_noop_per_ca1(runtime_app):
    # CA-1 裁定：UNHEALTHY + START → 200 冪等 No-op
    app = runtime_app()
    add_managed_fixture(app.adapter, status="running")
    app.probes.hermes = "UNAVAILABLE"
    response = app.client.post(f"/v1/instances/{INSTANCE}/start")
    assert response.status_code == 200
    assert response.json()["state"] == "UNHEALTHY"
    assert app.adapter.start_calls == []


def test_start_from_error_is_rejected_per_ca1(runtime_app):
    # CA-1 裁定：ERROR + START → 409 INVALID_STATE_TRANSITION
    app = runtime_app()
    add_managed_fixture(app.adapter, status="exited")
    app.store.finish_error(INSTANCE, "RUNTIME_START_TIMEOUT")
    response = app.client.post(f"/v1/instances/{INSTANCE}/start")
    assert response.status_code == 409
    assert response.json()["error_code"] == "INVALID_STATE_TRANSITION"
    assert app.adapter.start_calls == []


# ---- Stop／Restart（RT-04、RT-05、RT-06） ----


def test_stop_running_instance_reaches_stopped(runtime_app):
    # RUNTIME-004（v0.2）：202 必回 STOPPING＋operation.action=STOP＋operation_id
    app = runtime_app()
    add_managed_fixture(app.adapter, status="running")
    response = app.client.post(f"/v1/instances/{INSTANCE}/stop")
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["state"] == "STOPPING"
    assert accepted["operation"]["action"] == "STOP"
    assert accepted["operation"]["operation_id"]
    wait_for_state(app, INSTANCE, "STOPPED")
    assert app.adapter.stop_calls == [f"cid-{INSTANCE}"]
    # RT-04：不刪除 Container
    assert f"cid-{INSTANCE}" in app.adapter.containers


def test_stop_when_stopped_is_idempotent_noop(runtime_app):
    app = runtime_app()
    add_managed_fixture(app.adapter, status="exited")
    response = app.client.post(f"/v1/instances/{INSTANCE}/stop")
    assert response.status_code == 200
    assert response.json()["state"] == "STOPPED"
    assert app.adapter.stop_calls == []


def test_stop_clears_sticky_error(runtime_app):
    # ERROR --STOP_REQUESTED--> STOPPING --STOP_SUCCEEDED--> STOPPED
    app = runtime_app()
    add_managed_fixture(app.adapter, status="running")
    app.store.finish_error(INSTANCE, "RUNTIME_START_TIMEOUT")
    response = app.client.post(f"/v1/instances/{INSTANCE}/stop")
    assert response.status_code == 202
    body = wait_for_state(app, INSTANCE, "STOPPED")
    assert body["last_error_code"] is None


def test_restart_from_stopped_is_invalid(runtime_app):
    # 狀態機 invalid_requests：STOPPED + RESTART → 409 INVALID_STATE_TRANSITION
    app = runtime_app()
    add_managed_fixture(app.adapter, status="exited")
    response = app.client.post(f"/v1/instances/{INSTANCE}/restart")
    assert response.status_code == 409
    assert response.json()["error_code"] == "INVALID_STATE_TRANSITION"


def test_restart_running_instance_cycles_to_healthy(runtime_app):
    # RUNTIME-005（v0.2）：202 必回 STOPPING＋operation.action=RESTART＋operation_id；
    # RUNTIME-014 語意：Restart 保留 Container（Volume），Stop 後 Start 回 HEALTHY
    app = runtime_app()
    container = add_managed_fixture(app.adapter, status="running")
    response = app.client.post(f"/v1/instances/{INSTANCE}/restart")
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["state"] == "STOPPING"
    assert accepted["operation"]["action"] == "RESTART"
    assert accepted["operation"]["operation_id"]
    wait_for_state(app, INSTANCE, "HEALTHY")
    assert app.adapter.stop_calls == [container.container_id]
    assert app.adapter.start_calls == [container.container_id]
    assert container.container_id in app.adapter.containers  # 未刪除


def test_duplicate_restart_reuses_same_operation(runtime_app):
    # RUNTIME-017（v0.2，critical）：Restart 仍執行中時重複 Restart →
    # 202、state ∈ {STOPPING, STARTING}、operation.action=RESTART、同一 operation_id，
    # 且不重複執行 Stop/Start（duplicate_restart_executed=false）。
    app = runtime_app(hermes_start_timeout_seconds=5)
    container = add_managed_fixture(app.adapter, status="running")
    app.probes.hermes = "UNAVAILABLE"  # 讓 Restart 停留在 STARTING 階段

    first = app.client.post(f"/v1/instances/{INSTANCE}/restart")
    assert first.status_code == 202
    first_operation_id = first.json()["operation"]["operation_id"]

    duplicate = app.client.post(f"/v1/instances/{INSTANCE}/restart")
    assert duplicate.status_code == 202
    body = duplicate.json()
    assert body["state"] in ("STOPPING", "STARTING")
    assert body["operation"]["action"] == "RESTART"
    assert body["operation"]["operation_id"] == first_operation_id  # same_operation_id

    app.probes.hermes = "AVAILABLE"  # 放行健康條件，讓原 Restart 完成
    wait_for_state(app, INSTANCE, "HEALTHY")
    # duplicate_restart_executed=false：Stop/Start 各只執行一次
    assert app.adapter.stop_calls == [container.container_id]
    assert app.adapter.start_calls == [container.container_id]


# ---- 白名單（RT-10、RT-11；RUNTIME-012） ----


def test_unmanaged_container_cannot_be_stopped(runtime_app):
    # RUNTIME-012：未受管 Container 回 403，且不得對其執行任何 Docker 操作
    app = runtime_app(
        controller_instance_registry=(
            '[{"instance_id": "hermes-poc-001"}, {"instance_id": "unmanaged-fixture-001"}]'
        )
    )
    from tests.conftest import FakeContainer

    app.adapter.add_container(
        FakeContainer(
            container_id="cid-unmanaged",
            name="unmanaged-fixture-001",
            status="running",
            labels={},  # 無受管 Label；名稱亦不符白名單
        )
    )
    response = app.client.post("/v1/instances/unmanaged-fixture-001/stop")
    assert response.status_code == 403
    assert response.json()["error_code"] == "INSTANCE_NOT_MANAGED"
    assert app.adapter.stop_calls == []
    assert app.adapter.containers["cid-unmanaged"].status == "running"


def test_unmanaged_container_logs_rejected(runtime_app):
    app = runtime_app(
        controller_instance_registry='[{"instance_id": "unmanaged-fixture-001"}]'
    )
    from tests.conftest import FakeContainer

    app.adapter.add_container(
        FakeContainer(container_id="cid-x", name="unmanaged-fixture-001", status="running")
    )
    response = app.client.get("/v1/instances/unmanaged-fixture-001/logs")
    assert response.status_code == 403


# ---- Logs（RT-13、NF-03；RUNTIME-013） ----


def test_logs_are_redacted(runtime_app):
    app = runtime_app()
    container = add_managed_fixture(app.adapter, status="running")
    app.adapter.log_lines[container.container_id] = [
        "INFO agent started",
        "api_key=TEST_SECRET_123456",
        "Authorization: Bearer abc.def.ghi",
    ]
    response = app.client.get(f"/v1/instances/{INSTANCE}/logs?tail=200")
    assert response.status_code == 200
    body = response.json()
    assert body["redacted"] is True
    assert body["instance_id"] == INSTANCE
    joined = "\n".join(body["lines"])
    assert "TEST_SECRET_123456" not in joined
    assert "abc.def.ghi" not in joined
    assert "INFO agent started" in joined


def test_logs_tail_out_of_range_is_validation_error(runtime_app):
    app = runtime_app()
    add_managed_fixture(app.adapter, status="running")
    response = app.client.get(f"/v1/instances/{INSTANCE}/logs?tail=0")
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["correlation_id"]
