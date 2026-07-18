"""狀態機表驅動測試（RT-02、RT-06；hermes-runtime.yaml 全表 + CA-1 裁定）。"""

import pytest

from app.state.machine import (
    Action,
    DecisionKind,
    RuntimeState,
    decide,
    map_container_status,
    state_when_idle,
)

S = RuntimeState
A = Action
K = DecisionKind

# (state, action) -> (kind, http_status, error_code)
CONTRACT_TABLE = [
    # START
    (S.STOPPED, A.START, K.ACCEPT, 202, None),
    (S.HEALTHY, A.START, K.NOOP, 200, None),
    (S.UNHEALTHY, A.START, K.NOOP, 200, None),  # CA-1 裁定
    (S.STARTING, A.START, K.EXISTING, 202, None),
    (S.STOPPING, A.START, K.REJECT, 409, "OPERATION_CONFLICT"),
    (S.ERROR, A.START, K.REJECT, 409, "INVALID_STATE_TRANSITION"),  # CA-1 裁定
    (S.NOT_PROVISIONED, A.START, K.REJECT, 404, "INSTANCE_NOT_FOUND"),
    # STOP
    (S.HEALTHY, A.STOP, K.ACCEPT, 202, None),
    (S.UNHEALTHY, A.STOP, K.ACCEPT, 202, None),
    (S.ERROR, A.STOP, K.ACCEPT, 202, None),
    (S.STOPPED, A.STOP, K.NOOP, 200, None),
    (S.STOPPING, A.STOP, K.EXISTING, 202, None),
    (S.STARTING, A.STOP, K.REJECT, 409, "OPERATION_CONFLICT"),
    (S.NOT_PROVISIONED, A.STOP, K.REJECT, 404, "INSTANCE_NOT_FOUND"),
    # RESTART
    (S.HEALTHY, A.RESTART, K.ACCEPT, 202, None),
    (S.UNHEALTHY, A.RESTART, K.ACCEPT, 202, None),
    (S.ERROR, A.RESTART, K.ACCEPT, 202, None),
    (S.STOPPED, A.RESTART, K.REJECT, 409, "INVALID_STATE_TRANSITION"),
    (S.STARTING, A.RESTART, K.REJECT, 409, "OPERATION_CONFLICT"),
    (S.STOPPING, A.RESTART, K.REJECT, 409, "OPERATION_CONFLICT"),
    (S.NOT_PROVISIONED, A.RESTART, K.REJECT, 404, "INSTANCE_NOT_FOUND"),
]


@pytest.mark.parametrize("state,action,kind,http_status,error_code", CONTRACT_TABLE)
def test_decision_table(state, action, kind, http_status, error_code):
    decision = decide(state, action)
    assert decision.kind == kind
    assert decision.http_status == http_status
    assert decision.error_code == error_code


def test_decision_table_is_exhaustive():
    for state in RuntimeState:
        for action in Action:
            decide(state, action)  # 任何組合都必須有明確決策，不得 KeyError


@pytest.mark.parametrize(
    "docker_status,expected",
    [
        ("created", "CREATED"),
        ("running", "RUNNING"),
        ("exited", "EXITED"),
        ("paused", "PAUSED"),
        ("restarting", "RESTARTING"),
        ("dead", "UNKNOWN"),
        ("removing", "UNKNOWN"),
    ],
)
def test_map_container_status(docker_status, expected):
    assert map_container_status(docker_status) == expected


def test_idle_state_healthy_requires_both_probes():
    # RT-09：Container Running 不等於 Healthy
    assert state_when_idle("RUNNING", "AVAILABLE", "AVAILABLE", None) == S.HEALTHY
    assert state_when_idle("RUNNING", "UNAVAILABLE", "AVAILABLE", None) == S.UNHEALTHY
    assert state_when_idle("RUNNING", "AVAILABLE", "UNAVAILABLE", None) == S.UNHEALTHY
    assert state_when_idle("RUNNING", "UNHEALTHY", "AVAILABLE", None) == S.UNHEALTHY
    assert state_when_idle("RUNNING", "AVAILABLE", "UNKNOWN", None) == S.UNHEALTHY


def test_idle_state_stopped_and_error():
    assert state_when_idle("CREATED", "UNKNOWN", "UNKNOWN", None) == S.STOPPED
    assert state_when_idle("EXITED", "UNKNOWN", "UNKNOWN", None) == S.STOPPED
    # ERROR 具黏性：有保存錯誤時優先於其他推導
    assert state_when_idle("RUNNING", "AVAILABLE", "AVAILABLE", "RUNTIME_START_TIMEOUT") == S.ERROR
    assert state_when_idle("EXITED", "UNKNOWN", "UNKNOWN", "RUNTIME_STOP_TIMEOUT") == S.ERROR


def test_idle_state_degraded_container_states():
    assert state_when_idle("PAUSED", "UNKNOWN", "UNKNOWN", None) == S.UNHEALTHY
    assert state_when_idle("RESTARTING", "UNKNOWN", "UNKNOWN", None) == S.UNHEALTHY
    assert state_when_idle("UNKNOWN", "UNKNOWN", "UNKNOWN", None) == S.UNHEALTHY
