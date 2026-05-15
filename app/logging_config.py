import json
import logging
import sys
from datetime import UTC, datetime
from logging.config import dictConfig
from typing import Any

from app.config import get_settings
from app.utils.context import get_request_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "module": record.module,
            "line": record.lineno,
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in logging.LogRecord("", 0, "", 0, "", (), None).__dict__:
                continue
            log_record[key] = value

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record, default=str)


def setup_logging() -> None:
    settings = get_settings()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": JsonFormatter,
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "json",
                }
            },
            "root": {
                "handlers": ["default"],
                "level": settings.log_level.upper(),
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": settings.log_level.upper(), "propagate": False},
                "uvicorn.error": {"handlers": ["default"], "level": settings.log_level.upper(), "propagate": False},
                "uvicorn.access": {"handlers": ["default"], "level": settings.log_level.upper(), "propagate": False},
            },
        }
    )
