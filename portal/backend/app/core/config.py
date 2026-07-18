"""Portal 設定：全部來自環境變數（NF-09），名稱依 contracts/environment.yaml。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    portal_database_url: str = "sqlite:////data/portal.db"
    default_instance_id: str = "hermes-poc-001"
    controller_base_url: str = "http://controller:8090"
    hermes_base_url: str = "http://hermes:8000"
    agent_request_timeout_seconds: int = 90
    log_level: str = "INFO"
    spec_version: str = "0.1.0"
    static_dir: str = "static"


@lru_cache
def get_settings() -> Settings:
    return Settings()
