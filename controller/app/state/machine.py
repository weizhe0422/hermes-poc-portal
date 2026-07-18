"""Runtime 狀態機（contracts/state-machines/hermes-runtime.yaml v0.1.0）。

逐條對應 contract 的 states、idempotent_requests 與 invalid_requests 表。
CA-1 裁定（2026-07-19 需求負責人核准）：
- UNHEALTHY + START → 200 冪等 No-op（Container 已 Running）。
- ERROR + START → 409 INVALID_STATE_TRANSITION（ERROR 僅允許 STOP／RESTART）。
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
    EXISTING = "EXISTING"  # 202：同型操作已在進行
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

_TABLE: dict[tuple[RuntimeState, Action], Decision] = {
    # START
    (RuntimeState.STOPPED, Action.START): _ACCEPT,
    (RuntimeState.HEALTHY, Action.START): _NOOP,
    (RuntimeState.UNHEALTHY, Action.START): _NOOP,  # CA-1
    (RuntimeState.STARTING, Action.START): _EXISTING,
    (RuntimeState.STOPPING, Action.START): _CONFLICT,
    (RuntimeState.ERROR, Action.START): _INVALID,  # CA-1
    # STOP
    (RuntimeState.HEALTHY, Action.STOP): _ACCEPT,
    (RuntimeState.UNHEALTHY, Action.STOP): _ACCEPT,
    (RuntimeState.ERROR, Action.STOP): _ACCEPT,
    (RuntimeState.STOPPED, Action.STOP): _NOOP,
    (RuntimeState.STOPPING, Action.STOP): _EXISTING,
    (RuntimeState.STARTING, Action.STOP): _CONFLICT,
    # RESTART
    (RuntimeState.HEALTHY, Action.RESTART): _ACCEPT,
    (RuntimeState.UNHEALTHY, Action.RESTART): _ACCEPT,
    (RuntimeState.ERROR, Action.RESTART): _ACCEPT,
    (RuntimeState.STOPPED, Action.RESTART): _INVALID,
    (RuntimeState.STARTING, Action.RESTART): _CONFLICT,
    (RuntimeState.STOPPING, Action.RESTART): _CONFLICT,
}


def decide(state: RuntimeState, action: Action) -> Decision:
    """依 contract 表決定生命週期要求的處理方式。"""
    if state == RuntimeState.NOT_PROVISIONED:
        return _NOT_FOUND
    return _TABLE[(state, action)]


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
