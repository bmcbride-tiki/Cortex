# =============================================================================
# logger.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Provides one shared way to produce log messages as structured JSON lines
#   (instead of plain text), each one tagged with which workflow and which
#   correlation ID it belongs to. That makes it possible to later search or
#   filter a huge pile of log output down to "everything that happened
#   during this one specific workflow run."
#
# WHAT IT INTERACTS WITH
#   - `core_router.py`'s `CoreWorkflowRouter`, the only current consumer --
#     it calls `CortexLogger.get_logger("CoreWorkflowRouter")` once at
#     import time and logs every step execution/transition through it.
#   - Standard output (`sys.stdout`) -- every log line is printed as one
#     JSON object per line, not written to a log file.
#
# KEY FUNCTIONALITY NOTES
#   - `get_logger()` is safe to call repeatedly with the same name -- it
#     only attaches a new handler the first time, so re-calling it later
#     doesn't duplicate every log line.
#   - `workflow_id` / `correlation_id` in each log line come from the
#     `extra={...}` dict passed to a normal `logger.info(...)` call -- if a
#     caller doesn't supply them, they default to the literal string `"N/A"`
#     rather than being omitted from the JSON.
# =============================================================================

import logging
import json
import sys
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "workflow_id": getattr(record, "workflow_id", "N/A"),
            "correlation_id": getattr(record, "correlation_id", "N/A")
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

class CortexLogger:
    @staticmethod
    def get_logger(name: str = "Cortex") -> logging.Logger:
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JSONFormatter())
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
