import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    # 測試用獨立 SQLite 檔案；設定於 import app 前生效。
    os.environ["PORTAL_DATABASE_URL"] = f"sqlite:///{tmp_path}/test-portal.db"

    from app.core.config import get_settings
    from app.db.engine import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

    get_settings.cache_clear()
    get_engine.cache_clear()
