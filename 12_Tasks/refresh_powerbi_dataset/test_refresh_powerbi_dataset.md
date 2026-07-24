---
tool_id: 'test_refresh_powerbi_dataset'
title: 'Refresh Power BI Dataset Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/powerbi, connects/refresh-powerbi-dataset]
---

# test-refresh-powerbi-dataset

> **Status:** Active. Runnable both via `pytest` and directly (`python test_refresh_powerbi_dataset.py`).

## Purpose

Confirms [[refresh_powerbi_dataset]]'s `run()` returns a successful result with a real-looking refresh request ID, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_returns_refresh_id` -- calls `run()` directly and asserts `success` is `True` and `refresh_request_id` starts with `refresh_`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[refresh_powerbi_dataset]] itself is already mock-mode.
