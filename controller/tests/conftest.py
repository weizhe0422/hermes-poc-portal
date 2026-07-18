from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


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
