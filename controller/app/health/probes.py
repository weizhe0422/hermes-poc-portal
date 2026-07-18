"""Hermes 與 LLM Health Probe（RT-09；Container Running 不等於 Healthy）。

- Hermes Probe：GET {HERMES_BASE_URL}{HERMES_HEALTH_PATH}
  2xx → AVAILABLE；其他 HTTP 回應 → UNHEALTHY；連線失敗／逾時 → UNAVAILABLE。
- LLM Probe（OD-03 裁定預設：最小非敏感請求）：GET {HERMES_LLM_BASE_URL}
  HTTP < 500 → AVAILABLE；>=500 或連線失敗 → UNAVAILABLE；未設定 → UNKNOWN（OD-04 未決）。
"""

import httpx

from app.core.config import Settings


class HealthProbes:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._timeout = settings.hermes_probe_timeout_seconds

    async def hermes_status(self) -> str:
        url = self._settings.hermes_base_url.rstrip("/") + self._settings.hermes_health_path
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
        except httpx.HTTPError:
            return "UNAVAILABLE"
        if 200 <= response.status_code < 300:
            return "AVAILABLE"
        return "UNHEALTHY"

    async def llm_status(self) -> str:
        base_url = self._settings.hermes_llm_base_url
        if not base_url:
            return "UNKNOWN"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(base_url)
        except httpx.HTTPError:
            return "UNAVAILABLE"
        if response.status_code < 500:
            return "AVAILABLE"
        return "UNAVAILABLE"
