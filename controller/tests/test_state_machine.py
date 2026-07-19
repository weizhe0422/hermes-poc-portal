"""狀態機表驅動測試（RT-02、RT-06；hermes-runtime.yaml Frozen v0.2.0 + CA-1 裁定）。"""

import pytest

from app.state.machine import (
    IDLE_STATES,
    Action,
    DecisionKind,
    RuntimeState,
    decide_idle,
    decide_in_flight,
    map_container_status,
    state_when_idle,
)

S = RuntimeState
A = Action
K = DecisionKind

# ---- decide_idle：無操作進行中（transitions／idempotency_rules／invalid_requests） ----

# (state, action) -> (kind, http_status, error_code)
IDLE_TABLE = [
    # START
    (S.STOPPED, A.START, K.ACCEPT, 202, None),  # STOPPED+START→STARTING(202)
    (S.HEALTHY, A.START, K.NOOP, 200, None),  # NO_OP_ALREADY_STARTED
    (S.UNHEALTHY, A.START, K.NOOP, 200, None),  # CA-1 裁定（v0.2 未定義，裁定續行）
    (S.ERROR, A.START, K.REJECT, 409, "INVALID_STATE_TRANSITION"),  # CA-1 裁定
    (S.NOT_PROVISIONED, A.START, K.REJECT, 404, "INSTANCE_NOT_FOUND"),
    # STOP
    (S.HEALTHY, A.STOP, K.ACCEPT, 202, None),
    (S.UNHEALTHY, A.STOP, K.ACCEPT, 202, None),
    (S.ERROR, A.STOP, K.ACCEPT, 202, None),
    (S.STOPPED, A.STOP, K.NOOP, 200, None),  # NO_OP_ALREADY_STOPPED（RUNTIME-007）
    (S.NOT_PROVISIONED, A.STOP, K.REJECT, 404, "INSTANCE_NOT_FOUND"),
    # RESTART
    (S.HEALTHY, A.RESTART, K.ACCEPT, 202, None),
    (S.UNHEALTHY, A.RESTART, K.ACCEPT, 202, None),
    (S.ERROR, A.RESTART, K.ACCEPT, 202, None),
    (S.STOPPED, A.RESTART, K.REJECT, 409, "INVALID_STATE_TRANSITION"),
    (S.NOT_PROVISIONED, A.RESTART, K.REJECT, 404, "INSTANCE_NOT_FOUND"),
]


@pytest.mark.parametrize("state,action,kind,http_status,error_code", IDLE_TABLE)
def test_idle_decision_table(state, action, kind, http_status, error_code):
    decision = decide_idle(state, action)
    assert decision.kind == kind
    assert decision.http_status == http_status
    assert decision.error_code == error_code


def test_idle_table_is_exhaustive():
    for state in IDLE_STATES:
        for action in Action:
            decide_idle(state, action)  # 任何 idle 組合都必須有明確決策


@pytest.mark.parametrize("state", [S.STARTING, S.STOPPING])
def test_idle_decision_rejects_in_flight_states(state):
    # STARTING/STOPPING 只在操作進行中出現，必須走 decide_in_flight
    with pytest.raises(ValueError):
        decide_idle(state, A.START)


# ---- decide_in_flight：contextual_idempotency_rules 與 condition 化 409（v0.2.0） ----

IN_FLIGHT_TABLE = [
    # 同型操作 → 202 EXISTING_OPERATION（requires_same_operation_id）
    (A.START, A.START, K.EXISTING, 202, None),
    (A.STOP, A.STOP, K.EXISTING, 202, None),
    (A.RESTART, A.RESTART, K.EXISTING, 202, None),  # RUNTIME-017
    # 不同操作 → 409 OPERATION_CONFLICT（requested != current_operation_action）
    (A.START, A.STOP, K.REJECT, 409, "OPERATION_CONFLICT"),
    (A.START, A.RESTART, K.REJECT, 409, "OPERATION_CONFLICT"),
    (A.STOP, A.START, K.REJECT, 409, "OPERATION_CONFLICT"),
    (A.STOP, A.RESTART, K.REJECT, 409, "OPERATION_CONFLICT"),
    (A.RESTART, A.START, K.REJECT, 409, "OPERATION_CONFLICT"),
    (A.RESTART, A.STOP, K.REJECT, 409, "OPERATION_CONFLICT"),
]


@pytest.mark.parametrize("current,requested,kind,http_status,error_code", IN_FLIGHT_TABLE)
def test_in_flight_decision_table(current, requested, kind, http_status, error_code):
    decision = decide_in_flight(current, requested)
    assert decision.kind == kind
    assert decision.http_status == http_status
    assert decision.error_code == error_code


# ---- container status 對映與狀態推導（v0.1 起未變） ----


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
