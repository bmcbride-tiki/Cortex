---
tool_id: 'sandbox_smoke_test'
title: 'Data Processing Smoke Test'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/system-core, tier/zero-input, function/testing, scope/data-processing, connects/workflow-schema, connects/enterprise-adapters, connects/user-identity, connects/canvas-schema, connects/canvas-parser, connects/observer-transformer, connects/core-router]
---

# sandbox-smoke-test

> **Status:** Active. Runnable directly: `python 00_System/sandbox_smoke_test.py`.

## Purpose

A single runnable script that exercises every piece of the `data_processing/` layer together, end to end, without needing the web server running or a browser open -- the fastest way to check "did my change break the workflow-state/licensing/canvas machinery?" Every check is a plain `assert`, so it stops with a traceback the moment something doesn't match.

## Processing Logic

Four checks run in sequence from `main()`, each printing its own banner:

1. `test_data_flow` -- ingest two files, run them through two workflow steps (a plain task, then an AI-flavored skill), confirm output and file lists carry forward correctly.
2. `test_licensing` -- confirm a licensed block runs, an unlicensed one is correctly reported unavailable, and running an unlicensed block anyway raises `PermissionError`.
3. `test_visual_canvas` -- build a small 3-node visual graph, confirm its SVGL brand icon resolves and its nodes run/get greyed out exactly as licensing dictates.
4. `test_observer_pipeline` -- run a short workflow, transform its resulting history into the observer pipeline view, confirm the human-approval stage shows up correctly.

## Output

Console banners + printed JSON (the observer view); a non-zero exit / traceback on any failed `assert`.

## Notes for AI reuse

Sets environment variables (`CORTEX_USER_UPN`, `HAS_COPILOT_PREMIUM`, `HAS_VISIO`) mid-run to simulate different signed-in users rather than reading from a real enterprise login -- see [[user_identity]]. Uses the same `sys.path` bootstrap + flat-import pattern as `health.py`/`server.py` so it runs correctly regardless of working directory. When adding a new `data_processing/` module, add a matching `test_*` function here and call it from `main()`, rather than creating a separate ad-hoc script.
