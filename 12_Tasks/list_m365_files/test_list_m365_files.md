---
tool_id: 'test_list_m365_files'
title: 'List M365 Files Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/onedrive, scope/sharepoint, connects/list-m365-files]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-list-m365-files

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_m365_files.py`).

## Purpose

Confirms [[list_m365_files]]'s `run()` returns a successful result with at least one file, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_returns_files` -- calls `run()` directly and asserts `success` is `True` and `files` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[list_m365_files]] itself is already mock-mode.
