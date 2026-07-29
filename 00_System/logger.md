---
tool_id: 'logger'
title: 'Structured JSON Logger'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/logging, scope/workflow-builder, connects/core-router]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# logger

> **Status:** Active. No `__main__` block.

## Purpose

Provides one shared way to produce log messages as structured JSON lines (instead of plain text), each tagged with which workflow and which correlation ID it belongs to -- so a pile of log output can later be filtered down to "everything that happened during this one specific workflow run."

## Processing Logic

### `JSONFormatter.format(record) -> str`

A `logging.Formatter` subclass that renders each log record as one JSON object: timestamp, level, logger name, message, plus `workflow_id`/`correlation_id` pulled from the record's `extra={...}` (defaulting to `"N/A"` if not supplied). Includes a formatted exception traceback if the record carries one.

### `CortexLogger.get_logger(name="Cortex") -> logging.Logger`

Returns a standard Python logger with a `JSONFormatter`-equipped `StreamHandler` attached to stdout -- safe to call repeatedly with the same name, since it only attaches the handler the first time.

## Output

One JSON object per line, printed to stdout.

## Notes for AI reuse

The only current consumer is [[core_router]]'s `CoreWorkflowRouter`, which calls `get_logger("CoreWorkflowRouter")` once at import time. Any new module wanting the same structured logging should call `CortexLogger.get_logger(<own name>)` rather than configuring `logging` directly, so every log line in the app stays in the same JSON shape.
