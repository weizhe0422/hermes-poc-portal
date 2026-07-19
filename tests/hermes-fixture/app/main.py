"""Hermes Fixture：模擬 Hermes 健康與失敗模式（docs/03 Test Images）。

Hermes Health 模式由環境變數 FIXTURE_MODE 控制：
- healthy（預設）：/health 回 200。
- unhealthy：/health 回 503（驗證 UNHEALTHY 狀態）。
- slow-start：啟動後延遲 FIXTURE_START_DELAY_SECONDS 才回 200（驗證 RUNTIME_START_TIMEOUT）。
- secret-log：啟動時輸出固定測試 Secret（驗證 Log Redaction；RUNTIME-013）。

Synthetic LLM Probe（OD-03：Synthetic 只驗證介面，不代表 Live Hermes Probe）：
- /llm/health 由 FIXTURE_LLM_MODE 獨立控制（available|unavailable），
  讓 E2E 可獨立模擬「Hermes AVAILABLE＋LLM UNAVAILABLE」等 RT-09 組合。

Persistent Marker（RUNTIME-014 前置條件）：
- 啟動時若 FIXTURE_STATE_DIR（預設 /state）可寫，追加一行啟動記錄至 marker.txt；
  GET /marker 回報 marker 是否存在與行數，供 Restart 後驗證 Volume 保留。

僅供白箱整合與 E2E 測試；不代表真實 Hermes API（OD-02 未決）。
"""

import os
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

MODE = os.environ.get("FIXTURE_MODE", "healthy")
LLM_MODE = os.environ.get("FIXTURE_LLM_MODE", "available")
START_DELAY_SECONDS = int(os.environ.get("FIXTURE_START_DELAY_SECONDS", "300"))
STATE_DIR = Path(os.environ.get("FIXTURE_STATE_DIR", "/state"))
_started_at = time.monotonic()

app = FastAPI(title="Hermes Fixture", docs_url=None, redoc_url=None, openapi_url=None)

if MODE == "secret-log":
    # 固定的假 Secret，僅用於驗證 Redaction；非真實憑證（docs/04 測試安全）。
    print("api_key=TEST_SECRET_123456", flush=True)


def _write_marker() -> None:
    try:
        if STATE_DIR.is_dir():
            marker = STATE_DIR / "marker.txt"
            with marker.open("a", encoding="utf-8") as handle:
                handle.write(f"started {datetime.now(UTC).isoformat()}\n")
    except OSError:
        # 無可寫 State Volume 時略過；/marker 會回報 present=false。
        pass


_write_marker()


@app.get("/health")
async def health() -> JSONResponse:
    if MODE == "unhealthy":
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
    if MODE == "slow-start" and (time.monotonic() - _started_at) < START_DELAY_SECONDS:
        return JSONResponse(status_code=503, content={"status": "starting"})
    return JSONResponse(status_code=200, content={"status": "ok", "mode": MODE})


@app.get("/llm/health")
async def llm_health() -> JSONResponse:
    if LLM_MODE == "unavailable":
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ok", "mode": LLM_MODE})


@app.get("/marker")
async def marker() -> JSONResponse:
    marker_file = STATE_DIR / "marker.txt"
    if marker_file.is_file():
        lines = marker_file.read_text(encoding="utf-8").splitlines()
        return JSONResponse(status_code=200, content={"present": True, "lines": len(lines)})
    return JSONResponse(status_code=200, content={"present": False, "lines": 0})
