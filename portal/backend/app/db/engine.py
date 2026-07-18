"""SQLite Engine（docs/03：SQLAlchemy 2.x；單機 PoC 單 Writer）。"""

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.portal_database_url,
        connect_args={"check_same_thread": False},
    )


def database_ready(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
