"""Controller 白箱測試共用 Fixture。

單元／整合測試一律以 Fake Docker Adapter 與 Fake Probe 取代真實依賴，
不接觸 Docker Engine（docs/04 測試安全；真實 Engine 冒煙另由
scripts/dev-smoke-controller 依核准條件執行）。
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.docker_adapter.adapter import ContainerInfo
from app.health.probes import HealthProbes
from app.main import create_app
from app.registry.registry import INSTANCE_ID_LABEL, InstanceRegistry
from app.state.service import RuntimeService
from app.state.store import InstanceStore

# ---- P-M0 health endpoint fixtures ----


@pytest.fixture
def docker_client_mock() -> MagicMock:
    client = MagicMock()
    client.ping.return_value = True
    return client


@pytest.fixture
def client(docker_client_mock: MagicMock) -> Iterator[TestClient]:
    app = create_app()
    with TestClient(app) as test_client:
        # lifespan 建立的真實 client 一律以 mock 取代：單元測試不得接觸 Docker Engine。
        app.state.docker_client = docker_client_mock
        yield test_client


# ---- P-M1 runtime service fixtures ----


@dataclass
class FakeContainer:
    container_id: str
    name: str
    status: str = "created"
    image: str = "hermes-fixture:test"
    labels: dict[str, str] = field(default_factory=dict)


class FakeDockerAdapter:
    """與 DockerAdapter 相同介面的記憶體版；記錄所有呼叫供白名單／冪等驗證。"""

    def __init__(self) -> None:
        self.containers: dict[str, FakeContainer] = {}
        self.start_calls: list[str] = []
        self.stop_calls: list[str] = []
        self.log_lines: dict[str, list[str]] = {}
        self.start_behavior = "run"  # run：start 後變 running；stay：維持原狀態
        self.stop_behavior = "exit"  # exit：stop 後變 exited；stay：維持 running

    def add_container(self, container: FakeContainer) -> None:
        self.containers[container.container_id] = container

    def _info(self, c: FakeContainer) -> ContainerInfo:
        return ContainerInfo(
            container_id=c.container_id,
            name=c.name,
            status=c.status,
            image=c.image,
            labels=dict(c.labels),
        )

    def find_candidate(self, instance_id: str) -> ContainerInfo | None:
        for c in self.containers.values():
            if c.labels.get(INSTANCE_ID_LABEL) == instance_id:
                return self._info(c)
        for c in self.containers.values():
            if c.name == instance_id:
                return self._info(c)
        return None

    def start(self, container_id: str) -> None:
        self.start_calls.append(container_id)
        if self.start_behavior == "run":
            self.containers[container_id].status = "running"

    def stop(self, container_id: str, timeout_seconds: int) -> None:
        self.stop_calls.append(container_id)
        if self.stop_behavior == "exit":
            self.containers[container_id].status = "exited"

    def inspect(self, container_id: str) -> ContainerInfo | None:
        c = self.containers.get(container_id)
        return self._info(c) if c else None

    def logs_tail(self, container_id: str, tail: int) -> list[str]:
        return self.log_lines.get(container_id, [])[-tail:]


class FakeProbes(HealthProbes):
    def __init__(self) -> None:  # 不呼叫父類：不需要 httpx 與 settings
        self.hermes = "AVAILABLE"
        self.llm = "AVAILABLE"

    async def hermes_status(self) -> str:
        return self.hermes

    async def llm_status(self) -> str:
        return self.llm


@dataclass
class RuntimeTestApp:
    client: TestClient
    adapter: FakeDockerAdapter
    probes: FakeProbes
    store: InstanceStore
    settings: Settings


# 測試預設：短 timeout 與快輪詢，讓 Timeout 案例在秒級完成。
FAST_SETTINGS: dict[str, Any] = {
    "hermes_start_timeout_seconds": 1,
    "hermes_stop_timeout_seconds": 0,
    "health_poll_interval_seconds": 0.05,
    "hermes_model_name": "test-model",
    "knowledge_version": "kw-test-1",
    "skill_version": "sk-test-1",
}


@pytest.fixture
def runtime_app() -> Iterator[Any]:
    """回傳 factory：make(**settings_overrides) -> RuntimeTestApp。"""
    opened: list[TestClient] = []

    def make(**overrides: Any) -> RuntimeTestApp:
        settings = Settings(**{**FAST_SETTINGS, **overrides})
        app = create_app()
        test_client = TestClient(app)
        test_client.__enter__()
        opened.append(test_client)

        adapter = FakeDockerAdapter()
        probes = FakeProbes()
        store = InstanceStore()
        app.state.runtime_service = RuntimeService(
            settings=settings,
            registry=InstanceRegistry.from_settings(settings),
            adapter=adapter,  # type: ignore[arg-type]
            probes=probes,
            store=store,
        )
        return RuntimeTestApp(test_client, adapter, probes, store, settings)

    yield make
    for c in opened:
        c.__exit__(None, None, None)


def add_managed_fixture(
    adapter: FakeDockerAdapter,
    instance_id: str = "hermes-poc-001",
    status: str = "created",
) -> FakeContainer:
    container = FakeContainer(
        container_id=f"cid-{instance_id}",
        name=f"hermes-{instance_id}",
        status=status,
        labels={"poc.managed": "true", INSTANCE_ID_LABEL: instance_id},
    )
    adapter.add_container(container)
    return container
