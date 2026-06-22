import json
import logging
import re
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from app.config import get_data_dir


_SECRET_PATTERN = re.compile(
    r"(?i)(authorization:\s*bearer\s+|api[_-]?key[\"'=:\s]+)([^\s,;\"]+)"
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = _SECRET_PATTERN.sub(r"\1<redacted>", record.getMessage())
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "backend.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    if not any(
        isinstance(existing, RotatingFileHandler)
        and getattr(existing, "baseFilename", None) == handler.baseFilename
        for existing in root.handlers
    ):
        root.addHandler(handler)
    root.setLevel(logging.INFO)
