"""Runtime 狀態機（contracts/state-machines/hermes-runtime.yaml，Frozen v0.2.0）。

決策分兩層，逐條對應 contract：
- decide_in_flight：操作進行中，依 contextual_idempotency_rules 以「action 比對」判定——
  同型操作 → 202 EXISTING_OPERATION（沿用同一 operation_id）；
  不同操作 → 409 OPERATION_CONFLICT（invalid_requests 的 condition:
  requested_action != current_operation_action）。
- decide_idle：無操作進行中，依 transitions／idempotency_rules／invalid_requests 表。

CA-1 裁定（2026-07-19 需求負責人核准；v0.2.0 對此兩格仍未定義，裁定續行）：
- UNHEALTHY + START → 200 冪等 No-op（Container 已 Running）。
- ERROR + START → 409 INVALID_STATE_TRANSITION（終態不允許的操作）。
"""

from dataclasses import dataclass
from enum import StrEnum


class RuntimeState(StrEnum):
    NOT_PROVISIONED = "NOT_PROVISIONED"
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class Action(StrEnum):
    START = "START"
    STOP = "STOP"
    RESTART = "RESTART"


class DecisionKind(StrEnum):
    ACCEPT = "ACCEPT"  # 202：開始新操作
    NOOP = "NOOP"  # 200：冪等 No-op，已在目標狀態
    EXISTING = "EXISTING"  # 202：同型操作已在進行，沿用 operation_id
    REJECT = "REJECT"  # 4xx：不允許


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    http_status: int
    error_code: str | None = None


_ACCEPT = Decision(DecisionKind.ACCEPT, 202)
_NOOP = Decision(DecisionKind.NOOP, 200)
_EXISTING = Decision(DecisionKind.EXISTING, 202)
_CONFLICT = Decision(DecisionKind.REJECT, 409, "OPERATION_CONFLICT")
_INVALID = Decision(DecisionKind.REJECT, 409, "INVALID_STATE_TRANSITION")
_NOT_FOUND = Decision(DecisionKind.REJECT, 404, "INSTANCE_NOT_FOUND")

# 無操作進行中的決策表；STARTING/STOPPING 只在操作進行中出現，屬 decide_in_flight 範圍。
IDLE_STATES = (
    RuntimeState.NOT_PROVISIONED,
    RuntimeState.STOPPED,
    RuntimeState.HEALTHY,
    RuntimeState.UNHEALTHY,
    RuntimeState.ERROR,
)

_IDLE_TABLE: dict[tuple[RuntimeState, Action], Decision] = {
    # START
    (RuntimeState.STOPPED, Action.START): _ACCEPT,  # transitions: STOPPED+START→STARTING(202)
    (RuntimeState.HEALTHY, Action.START): _NOOP,  # idempotency: NO_OP_ALREADY_STARTED
    (RuntimeState.UNHEALTHY, Action.START): _NOOP,  # CA-1
    (RuntimeState.ERROR, Action.START): _INVALID,  # CA-1
    # STOP
    (RuntimeState.HEALTHY, Action.STOP): _ACCEPT,
    (RuntimeState.UNHEALTHY, Action.STOP): _ACCEPT,
    (RuntimeState.ERROR, Action.STOP): _ACCEPT,
    (RuntimeState.STOPPED, Action.STOP): _NOOP,  # idempotency: NO_OP_ALREADY_STOPPED
    # RESTART
    (RuntimeState.HEALTHY, Action.RESTART): _ACCEPT,
    (RuntimeState.UNHEALTHY, Action.RESTART): _ACCEPT,
    (RuntimeState.ERROR, Action.RESTART): _ACCEPT,
    (RuntimeState.STOPPED, Action.RESTART): _INVALID,  # invalid_requests
}


def decide_idle(state: RuntimeState, action: Action) -> Decision:
    """無操作進行中時，依 contract 表決定生命週期要求的處理方式。"""
    if state == RuntimeState.NOT_PROVISIONED:
        return _NOT_FOUND
    if state not in IDLE_STATES:
        raise ValueError(f"decide_idle called with in-flight state {state}")
    return _IDLE_TABLE[(state, action)]


def decide_in_flight(current_operation_action: Action, requested_action: Action) -> Decision:
    """操作進行中：contextual_idempotency_rules（同型 202）與 condition 化的 409。"""
    if requested_action == current_operation_action:
        return _EXISTING
    return _CONFLICT


# Docker container status -> AgentInstance.container_status enum
_CONTAINER_STATUS_MAP = {
    "created": "CREATED",
    "running": "RUNNING",
    "exited": "EXITED",
    "paused": "PAUSED",
    "restarting": "RESTARTING",
}


def map_container_status(docker_status: str) -> str:
    return _CONTAINER_STATUS_MAP.get(docker_status.lower(), "UNKNOWN")


def state_when_idle(
    container_status: str,
    hermes_status: str,
    llm_status: str,
    last_error_code: str | None,
) -> RuntimeState:
    """無進行中操作時的狀態推導。

    - ERROR 具黏性：Lifecycle 失敗／逾時後保持 ERROR，直到 STOP/RESTART 成功
      （contract：ERROR 僅有 STOP_REQUESTED/RESTART_REQUESTED 轉移）。
    - RUNNING 且 Hermes 與 LLM Probe 皆 AVAILABLE 才是 HEALTHY（RT-09）。
    - PAUSED/RESTARTING/UNKNOWN：Container 存在但非健康，視為 UNHEALTHY。
    """
    if last_error_code is not None:
        return RuntimeState.ERROR
    if container_status == "RUNNING":
        if hermes_status == "AVAILABLE" and llm_status == "AVAILABLE":
            return RuntimeState.HEALTHY
        return RuntimeState.UNHEALTHY
    if container_status in ("CREATED", "EXITED"):
        return RuntimeState.STOPPED
    return RuntimeState.UNHEALTHY
