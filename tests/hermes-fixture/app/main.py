"""Hermes Fixture：模擬 Hermes 健康與失敗模式（docs/03 Test Images）。

模式由環境變數 FIXTURE_MODE 控制：
- healthy（預設）：/health 回 200。
- unhealthy：/health 回 503（驗證 UNHEALTHY 狀態）。
- slow-start：啟動後延遲 FIXTURE_START_DELAY_SECONDS 才回 200（驗證 RUNTIME_START_TIMEOUT）。
- secret-log：啟動時輸出固定測試 Secret（驗證 Log Redaction；RUNTIME-013）。

僅供白箱整合與 E2E 測試；不代表真實 Hermes API（OD-02 未決）。
"""

import os
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

MODE = os.environ.get("FIXTURE_MODE", "healthy")
START_DELAY_SECONDS = int(os.environ.get("FIXTURE_START_DELAY_SECONDS", "300"))
_started_at = time.monotonic()

app = FastAPI(title="Hermes Fixture", docs_url=None, redoc_url=None, openapi_url=None)

if MODE == "secret-log":
    # 固定的假 Secret，僅用於驗證 Redaction；非真實憑證（docs/04 測試安全）。
    print("api_key=TEST_SECRET_123456", flush=True)


@app.get("/health")
async def health() -> JSONResponse:
    if MODE == "unhealthy":
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
    if MODE == "slow-start" and (time.monotonic() - _started_at) < START_DELAY_SECONDS:
        return JSONResponse(status_code=503, content={"status": "starting"})
    return JSONResponse(status_code=200, content={"status": "ok", "mode": MODE})
