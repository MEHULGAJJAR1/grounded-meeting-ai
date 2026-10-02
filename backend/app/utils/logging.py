"""Structured logs intentionally exclude credentials, bodies and transcript text."""

import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key in (
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "meeting_id",
            "user_id",
            "stage",
            "error_type",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        # Exception messages from vendors can contain input; only log the class.
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload)


def configure_logging(level: str):
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
