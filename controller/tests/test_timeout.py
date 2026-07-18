"""操作 Timeout 測試（RT-08；RUNTIME-009 語意；error-catalog RESOURCE_STATE）。"""

import time

from tests.conftest import add_managed_fixture

INSTANCE = "hermes-poc-001"


def wait_for_state(app, state: str, timeout: float = 4.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = app.client.get(f"/v1/instances/{INSTANCE}").json()
        if body["state"] == state:
            return body
        time.sleep(0.05)
    raise AssertionError(f"state never became {state}; last={body['state']}")


def test_start_timeout_enters_error_with_saved_code(runtime_app):
    # RUNTIME-009：啟動逾時 → 初始 202 → 最終 ERROR＋RUNTIME_START_TIMEOUT
    app = runtime_app(hermes_start_timeout_seconds=1)
    add_managed_fixture(app.adapter, status="created")
    app.probes.hermes = "UNAVAILABLE"  # 模擬 slow-start：Probe 一直不 Ready

    response = app.client.post(f"/v1/instances/{INSTANCE}/start")
    assert response.status_code == 202

    body = wait_for_state(app, "ERROR")
    assert body["last_error_code"] == "RUNTIME_START_TIMEOUT"
    assert body["operation"] is None  # 操作已結束，鎖已釋放


def test_stop_timeout_enters_error_with_saved_code(runtime_app):
    app = runtime_app(hermes_stop_timeout_seconds=0, health_poll_interval_seconds=0.05)
    add_managed_fixture(app.adapter, status="running")
    app.adapter.stop_behavior = "stay"  # Container 停不下來

    response = app.client.post(f"/v1/instances/{INSTANCE}/stop")
    assert response.status_code == 202

    body = wait_for_state(app, "ERROR")
    assert body["last_error_code"] == "RUNTIME_STOP_TIMEOUT"


def test_error_after_timeout_allows_stop_recovery(runtime_app):
    # ERROR → STOP → STOPPED（黏性錯誤由成功的 Stop 清除）
    app = runtime_app(hermes_start_timeout_seconds=1)
    add_managed_fixture(app.adapter, status="created")
    app.probes.hermes = "UNAVAILABLE"
    app.client.post(f"/v1/instances/{INSTANCE}/start")
    wait_for_state(app, "ERROR")

    response = app.client.post(f"/v1/instances/{INSTANCE}/stop")
    assert response.status_code == 202
    body = wait_for_state(app, "STOPPED")
    assert body["last_error_code"] is None


def test_error_after_timeout_allows_restart_recovery(runtime_app):
    # ERROR → RESTART → HEALTHY（contract：ERROR + RESTART_REQUESTED 合法）
    app = runtime_app(hermes_start_timeout_seconds=1)
    add_managed_fixture(app.adapter, status="created")
    app.probes.hermes = "UNAVAILABLE"
    app.client.post(f"/v1/instances/{INSTANCE}/start")
    wait_for_state(app, "ERROR")

    app.probes.hermes = "AVAILABLE"  # 恢復健康條件
    response = app.client.post(f"/v1/instances/{INSTANCE}/restart")
    assert response.status_code == 202
    body = wait_for_state(app, "HEALTHY")
    assert body["last_error_code"] is None
