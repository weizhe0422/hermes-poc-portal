"""Runtime 生命週期服務：Registry 驗證 → 狀態推導 → 狀態機決策 → 非同步操作。

實作對應：RT-02（狀態機）、RT-03/04/05（Lifecycle）、RT-06（冪等）、
RT-07（單一操作 Lock）、RT-08（Timeout→ERROR）、RT-09（雙 Probe）、
RT-10/11（白名單，未受管 Container 不執行任何 Docker 操作）、
RT-13/NF-03（Log Redaction）、NF-11（一律回傳 instance_id）。
"""

import asyncio
import logging
from datetime import UTC, datetime

from app.core.config import Settings
from app.docker_adapter.adapter import ContainerInfo, DockerAdapter
from app.errors import ControllerError
from app.health.probes import HealthProbes
from app.redaction.redactor import redact_lines
from app.registry.registry import InstanceRegistry, RegistryEntry
from app.state.machine import (
    Action,
    Decision,
    DecisionKind,
    RuntimeState,
    decide_idle,
    decide_in_flight,
    map_container_status,
    state_when_idle,
)
from app.state.store import InstanceStore

logger = logging.getLogger("controller.runtime")

CONTROLLER_VERSION = "0.1.0"


class RuntimeService:
    def __init__(
        self,
        settings: Settings,
        registry: InstanceRegistry,
        adapter: DockerAdapter,
        probes: HealthProbes,
        store: InstanceStore,
    ):
        self._settings = settings
        self._registry = registry
        self._adapter = adapter
        self._probes = probes
        self._store = store

    # ---- 查詢 ----

    async def list_instances(self) -> list[dict[str, object]]:
        return [await self.get_instance(iid) for iid in self._registry.instance_ids()]

    async def get_instance(self, instance_id: str) -> dict[str, object]:
        entry = self._registry.require(instance_id)
        candidate = await asyncio.to_thread(self._adapter.find_candidate, instance_id)
        if candidate is None:
            # INSTANCE_REMOVED_EXTERNALLY：Container 消失即回 NOT_PROVISIONED 並清除黏性錯誤。
            self._store.clear(instance_id)
            return self._instance_payload(entry, None, RuntimeState.NOT_PROVISIONED, "MISSING")
        self._registry.require_managed(candidate.name, candidate.labels)
        return await self._build_instance(entry, candidate)

    # ---- Lifecycle ----

    async def request_action(
        self, instance_id: str, action: Action
    ) -> tuple[int, dict[str, object]]:
        """回傳 (http_status, AgentInstance payload)；錯誤以 ControllerError 拋出。"""
        entry = self._registry.require(instance_id)
        candidate = await asyncio.to_thread(self._adapter.find_candidate, instance_id)
        if candidate is None:
            self._store.clear(instance_id)
            raise ControllerError("INSTANCE_NOT_FOUND")
        # 白名單不通過即拒絕，之後不再接觸該 Container（RT-10；RUNTIME-012）。
        self._registry.require_managed(candidate.name, candidate.labels)

        # 同步 critical section：決策、佔用操作與 202 快照之間不得有 await（RT-07）。
        # v0.2.0 要求 202 必回 STARTING/STOPPING＋operation 物件（controller-api 202 Schema），
        # 因此 202 回應以「接受當下」的快照組裝，不重新 inspect（避免操作先完成的 race）。
        decision, payload = self._decide_begin_and_snapshot(entry, candidate, action)

        if decision.kind == DecisionKind.REJECT:
            assert decision.error_code is not None
            raise ControllerError(decision.error_code)

        if decision.kind == DecisionKind.ACCEPT:
            runner = {
                Action.START: self._run_start,
                Action.STOP: self._run_stop,
                Action.RESTART: self._run_restart,
            }[action]
            asyncio.get_running_loop().create_task(runner(instance_id, candidate.container_id))
            logger.info(
                "operation accepted",
                extra={"instance_id": instance_id, "action": action.value},
            )

        if payload is None:
            # NOOP 200：回應反映當下實況（RUNTIME-006/007 的 final_state 驗證）。
            refreshed = await asyncio.to_thread(self._adapter.inspect, candidate.container_id)
            payload = await self._build_instance(entry, refreshed or candidate)
        return decision.http_status, payload

    def _decide_begin_and_snapshot(
        self, entry: RegistryEntry, candidate: ContainerInfo, action: Action
    ) -> tuple[Decision, dict[str, object] | None]:
        """同步：決策＋（ACCEPT 時）佔用操作＋（202 時）組裝快照回應。

        - 操作進行中：contextual_idempotency_rules 以 action 比對——同型 202 沿用
          operation_id（RUNTIME-017），不同型 409 OPERATION_CONFLICT（condition:
          requested_action != current_operation_action）。
        - 無操作：HEALTHY 與 UNHEALTHY 在決策表結果相同（CA-1 後），以 container
          狀態＋黏性錯誤推導即可，不需在鎖內等待 Probe。
        """
        instance_id = entry.instance_id
        record = self._store.record(instance_id)

        if record.operation is not None:
            decision = decide_in_flight(record.operation.action, action)
            if decision.kind == DecisionKind.EXISTING:
                return decision, self._operation_snapshot(entry, candidate)
            return decision, None

        container_status = map_container_status(candidate.status)
        idle_state = state_when_idle(
            container_status, "AVAILABLE", "AVAILABLE", record.last_error_code
        )
        decision = decide_idle(idle_state, action)
        if decision.kind == DecisionKind.ACCEPT:
            initial_phase = (
                RuntimeState.STARTING if action == Action.START else RuntimeState.STOPPING
            )
            self._store.try_begin(instance_id, action, initial_phase)
            return decision, self._operation_snapshot(entry, candidate)
        return decision, None

    def _operation_snapshot(
        self, entry: RegistryEntry, candidate: ContainerInfo
    ) -> dict[str, object]:
        """以進行中操作的階段組裝 202 回應（state=STARTING/STOPPING、operation 必填）。"""
        record = self._store.record(entry.instance_id)
        assert record.operation is not None
        return self._instance_payload(
            entry,
            candidate,
            record.operation.phase,
            map_container_status(candidate.status),
        )

    # ---- 非同步操作（RT-08 Timeout；逾時進 ERROR 並保存錯誤碼） ----

    async def _run_start(self, instance_id: str, container_id: str) -> None:
        try:
            async with asyncio.timeout(self._settings.hermes_start_timeout_seconds):
                await asyncio.to_thread(self._adapter.start, container_id)
                await self._wait_until_healthy(container_id)
            self._store.finish_success(instance_id)
            logger.info("start succeeded", extra={"instance_id": instance_id})
        except TimeoutError:
            self._store.finish_error(instance_id, "RUNTIME_START_TIMEOUT")
            logger.warning("start timeout", extra={"instance_id": instance_id})
        except ControllerError as exc:
            self._store.finish_error(instance_id, exc.error_code)
            logger.warning("start failed", extra={"instance_id": instance_id})
        except Exception:
            self._store.finish_error(instance_id, "INTERNAL_ERROR")
            logger.exception("start failed unexpectedly", extra={"instance_id": instance_id})

    async def _run_stop(self, instance_id: str, container_id: str) -> None:
        try:
            await self._stop_phase(container_id)
            self._store.finish_success(instance_id)
            logger.info("stop succeeded", extra={"instance_id": instance_id})
        except TimeoutError:
            self._store.finish_error(instance_id, "RUNTIME_STOP_TIMEOUT")
            logger.warning("stop timeout", extra={"instance_id": instance_id})
        except ControllerError as exc:
            self._store.finish_error(instance_id, exc.error_code)
            logger.warning("stop failed", extra={"instance_id": instance_id})
        except Exception:
            self._store.finish_error(instance_id, "INTERNAL_ERROR")
            logger.exception("stop failed unexpectedly", extra={"instance_id": instance_id})

    async def _run_restart(self, instance_id: str, container_id: str) -> None:
        """RESTART＝STOPPING→（continuation START_REQUESTED）→STARTING，全程持有同一操作。"""
        try:
            await self._stop_phase(container_id)
        except TimeoutError:
            self._store.finish_error(instance_id, "RUNTIME_STOP_TIMEOUT")
            return
        except ControllerError as exc:
            self._store.finish_error(instance_id, exc.error_code)
            return
        except Exception:
            self._store.finish_error(instance_id, "INTERNAL_ERROR")
            logger.exception("restart stop-phase failed", extra={"instance_id": instance_id})
            return

        self._store.set_phase(instance_id, RuntimeState.STARTING)
        try:
            async with asyncio.timeout(self._settings.hermes_start_timeout_seconds):
                await asyncio.to_thread(self._adapter.start, container_id)
                await self._wait_until_healthy(container_id)
            self._store.finish_success(instance_id)
            logger.info("restart succeeded", extra={"instance_id": instance_id})
        except TimeoutError:
            self._store.finish_error(instance_id, "RUNTIME_START_TIMEOUT")
        except ControllerError as exc:
            self._store.finish_error(instance_id, exc.error_code)
        except Exception:
            self._store.finish_error(instance_id, "INTERNAL_ERROR")
            logger.exception("restart start-phase failed", extra={"instance_id": instance_id})

    async def _stop_phase(self, container_id: str) -> None:
        stop_timeout = self._settings.hermes_stop_timeout_seconds
        # SDK stop 本身以 stop_timeout 作為 SIGTERM→SIGKILL 寬限；
        # 外層再加隨 poll interval 縮放的緩衝，避免 Docker API 卡住時無限等待。
        buffer = 15 * self._settings.health_poll_interval_seconds
        async with asyncio.timeout(stop_timeout + buffer):
            await asyncio.to_thread(self._adapter.stop, container_id, stop_timeout)
            while True:
                info = await asyncio.to_thread(self._adapter.inspect, container_id)
                if info is None or map_container_status(info.status) in ("EXITED", "CREATED"):
                    return
                await asyncio.sleep(self._settings.health_poll_interval_seconds)

    async def _wait_until_healthy(self, container_id: str) -> None:
        while True:
            info = await asyncio.to_thread(self._adapter.inspect, container_id)
            if info is not None and map_container_status(info.status) == "RUNNING":
                hermes = await self._probes.hermes_status()
                llm = await self._probes.llm_status()
                if hermes == "AVAILABLE" and llm == "AVAILABLE":
                    return
            await asyncio.sleep(self._settings.health_poll_interval_seconds)

    # ---- Logs ----

    async def get_logs(self, instance_id: str, tail: int) -> dict[str, object]:
        self._registry.require(instance_id)
        candidate = await asyncio.to_thread(self._adapter.find_candidate, instance_id)
        if candidate is None:
            raise ControllerError("INSTANCE_NOT_FOUND")
        self._registry.require_managed(candidate.name, candidate.labels)
        raw_lines = await asyncio.to_thread(
            self._adapter.logs_tail, candidate.container_id, tail
        )
        return {
            "instance_id": instance_id,
            "lines": redact_lines(raw_lines),
            "redacted": True,
        }

    # ---- AgentInstance payload（agent-instance.schema.json） ----

    async def _build_instance(
        self, entry: RegistryEntry, candidate: ContainerInfo
    ) -> dict[str, object]:
        record = self._store.record(entry.instance_id)
        container_status = map_container_status(candidate.status)

        if record.operation is not None:
            state = record.operation.phase
            hermes_status, llm_status = "UNKNOWN", "UNKNOWN"
        elif container_status == "RUNNING":
            hermes_status = await self._probes.hermes_status()
            llm_status = await self._probes.llm_status()
            state = state_when_idle(
                container_status, hermes_status, llm_status, record.last_error_code
            )
        else:
            hermes_status, llm_status = "UNKNOWN", "UNKNOWN"
            state = state_when_idle(
                container_status, hermes_status, llm_status, record.last_error_code
            )

        return self._instance_payload(
            entry, candidate, state, container_status, hermes_status, llm_status
        )

    def _instance_payload(
        self,
        entry: RegistryEntry,
        candidate: ContainerInfo | None,
        state: RuntimeState,
        container_status: str,
        hermes_status: str = "UNKNOWN",
        llm_status: str = "UNKNOWN",
    ) -> dict[str, object]:
        record = self._store.record(entry.instance_id)
        operation = None
        if record.operation is not None:
            operation = {
                "operation_id": record.operation.operation_id,
                "action": record.operation.action.value,
                "started_at": record.operation.started_at,
            }
        settings = self._settings
        return {
            "instance_id": entry.instance_id,
            "template_id": entry.template_id,
            "state": state.value,
            "container_status": container_status,
            "hermes_status": hermes_status,
            "llm_status": llm_status,
            "operation": operation,
            "last_error_code": record.last_error_code,
            "versions": {
                "spec_version": settings.spec_version,
                "portal_version": settings.portal_version,
                "controller_version": CONTROLLER_VERSION,
                "hermes_image": candidate.image if candidate else "NOT_PROVISIONED",
                # OD-04 未決：模型名未注入時以 UNSET 佔位（schema minLength 1）。
                "model_name": settings.hermes_model_name or "UNSET",
                "knowledge_version": settings.knowledge_version,
                "skill_version": settings.skill_version,
            },
            "updated_at": datetime.now(UTC).isoformat(),
        }
