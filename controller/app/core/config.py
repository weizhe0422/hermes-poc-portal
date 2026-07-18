"""Controller 設定：全部來自環境變數（NF-09），名稱依 contracts/environment.yaml。

CA-3／CA-4 裁定（2026-07-19 需求負責人核准）新增的部署注入變數：
HERMES_TEMPLATE_ID、KNOWLEDGE_VERSION、SKILL_VERSION、PORTAL_VERSION
（AgentInstance.versions 必填欄位的來源；environment contract 擴充已記錄於完成報告）。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    default_instance_id: str = "hermes-poc-001"
    hermes_base_url: str = "http://hermes:8000"
    hermes_health_path: str = "/health"
    hermes_llm_base_url: str | None = None
    hermes_model_name: str | None = None
    hermes_start_timeout_seconds: int = 120
    hermes_stop_timeout_seconds: int = 30
    controller_managed_label: str = "poc.managed=true"
    log_level: str = "INFO"
    spec_version: str = "0.1.0"

    # --- CA-3/CA-4 裁定新增（versions 欄位來源；部署時注入實際值） ---
    hermes_template_id: str = "hermes-poc-template-v1"
    knowledge_version: str = "UNSET"
    skill_version: str = "UNSET"
    portal_version: str = "0.1.0"

    # --- 白名單與 Probe 行為（皆可由環境覆寫；NF-09） ---
    # Name 白名單 Pattern（fullmatch）；預設涵蓋 compose 產生名與 E2E fixture 名。
    controller_managed_name_pattern: str = r".*hermes.*"
    # JSON 陣列：[{"instance_id": "...", "template_id": "..."}]；未設定時只含 DEFAULT_INSTANCE_ID。
    controller_instance_registry: str | None = None
    hermes_probe_timeout_seconds: float = 5.0
    health_poll_interval_seconds: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
