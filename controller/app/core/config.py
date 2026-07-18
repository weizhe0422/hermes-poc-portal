"""Controller 設定：全部來自環境變數（NF-09），名稱依 contracts/environment.yaml。"""

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
