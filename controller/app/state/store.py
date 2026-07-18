"""每個 Instance 的操作狀態與併發鎖（RT-06、RT-07）。

單一 Uvicorn Event Loop 內以同步 check-and-set 保證同一 Instance
同時只有一個生命週期操作；try_begin 內不得有 await。

已知限制：狀態保存在記憶體，Controller 重啟後進行中操作與 ERROR 註記遺失，
狀態改由 Container 實際狀況重新推導（PoC 接受，見完成報告）。
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.state.machine import Action, RuntimeState


@dataclass
class Operation:
    operation_id: str
    action: Action
    started_at: str
    # 內部欄位：RESTART 會經歷 STOPPING→STARTING 兩階段；不輸出到 API Response。
    phase: RuntimeState = RuntimeState.STOPPING


@dataclass
class InstanceRecord:
    operation: Operation | None = None
    last_error_code: str | None = None


class InstanceStore:
    def __init__(self) -> None:
        self._records: dict[str, InstanceRecord] = {}

    def record(self, instance_id: str) -> InstanceRecord:
        return self._records.setdefault(instance_id, InstanceRecord())

    def try_begin(self, instance_id: str, action: Action, initial_phase: RuntimeState) -> Operation:
        """原子性開始操作；已有操作時由呼叫端依狀態機表回應，不在此覆蓋。"""
        record = self.record(instance_id)
        assert record.operation is None, "caller must check existing operation first"
        operation = Operation(
            operation_id=uuid.uuid4().hex,
            action=action,
            started_at=datetime.now(UTC).isoformat(),
            phase=initial_phase,
        )
        record.operation = operation
        return operation

    def set_phase(self, instance_id: str, phase: RuntimeState) -> None:
        record = self.record(instance_id)
        if record.operation is not None:
            record.operation.phase = phase

    def finish_success(self, instance_id: str) -> None:
        record = self.record(instance_id)
        record.operation = None
        record.last_error_code = None

    def finish_error(self, instance_id: str, error_code: str) -> None:
        record = self.record(instance_id)
        record.operation = None
        record.last_error_code = error_code

    def clear(self, instance_id: str) -> None:
        self._records.pop(instance_id, None)
