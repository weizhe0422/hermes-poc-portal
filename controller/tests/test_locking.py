"""單一生命週期操作 Lock 測試（RT-07；RUNTIME-008 語意）。"""

from tests.conftest import add_managed_fixture

INSTANCE = "hermes-poc-001"


def start_slow_operation(app):
    """發起一個不會很快完成的 START：Probe 永遠不 Ready，直到 Timeout。"""
    add_managed_fixture(app.adapter, status="created")
    app.probes.hermes = "UNAVAILABLE"
    response = app.client.post(f"/v1/instances/{INSTANCE}/start")
    assert response.status_code == 202
    return response.json()


def test_stop_conflicts_with_inflight_start(runtime_app):
    # RUNTIME-008：並行 START＋STOP → 一個被接受、另一個 409 OPERATION_CONFLICT
    app = runtime_app(hermes_start_timeout_seconds=5)
    start_slow_operation(app)
    response = app.client.post(f"/v1/instances/{INSTANCE}/stop")
    assert response.status_code == 409
    assert response.json()["error_code"] == "OPERATION_CONFLICT"


def test_restart_conflicts_with_inflight_start(runtime_app):
    app = runtime_app(hermes_start_timeout_seconds=5)
    start_slow_operation(app)
    response = app.client.post(f"/v1/instances/{INSTANCE}/restart")
    assert response.status_code == 409
    assert response.json()["error_code"] == "OPERATION_CONFLICT"


def test_duplicate_start_returns_existing_operation(runtime_app):
    # 狀態機 idempotent_requests：STARTING + START → 202 EXISTING_OPERATION
    app = runtime_app(hermes_start_timeout_seconds=5)
    first = start_slow_operation(app)
    response = app.client.post(f"/v1/instances/{INSTANCE}/start")
    assert response.status_code == 202
    body = response.json()
    assert body["state"] == "STARTING"
    # 是同一個操作，不是新操作
    assert body["operation"]["operation_id"] == first["operation"]["operation_id"]
    assert app.adapter.start_calls.count(f"cid-{INSTANCE}") == 1


def test_operation_object_matches_contract_shape(runtime_app):
    app = runtime_app(hermes_start_timeout_seconds=5)
    body = start_slow_operation(app)
    operation = body["operation"]
    assert set(operation) == {"operation_id", "action", "started_at"}
    assert operation["action"] == "START"
