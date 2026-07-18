"""JSON Lines 結構化 Log（NF-10）；每筆包含 correlation_id 與 task_id／instance_id（若有）。"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.correlation import get_correlation_id


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }
        for key in ("task_id", "instance_id", "actor_id"):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            entry["error_type"] = record.exc_info[0].__name__
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLineFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
