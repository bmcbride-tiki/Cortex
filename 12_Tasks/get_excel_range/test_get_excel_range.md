---
tool_id: 'test_get_excel_range'
title: 'Get Excel Range Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/excel, connects/get-excel-range]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-get-excel-range

> **Status:** Active. Runnable both via `pytest` and directly (`python test_get_excel_range.py`).

## Purpose

Confirms [[get_excel_range]]'s `run()` returns a successful result with the expected number of rows, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_returns_values` -- calls `run()` directly and asserts `success` is `True` and `values` has 2 rows.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[get_excel_range]] itself is already mock-mode.
