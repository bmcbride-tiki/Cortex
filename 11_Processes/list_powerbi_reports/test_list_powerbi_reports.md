---
tool_id: 'test_list_powerbi_reports'
title: 'List Power BI Reports Tests'
classification: '05_Processes'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/03-process, tier/zero-input, function/testing, scope/powerbi, connects/list-powerbi-reports]
---

# test-list-powerbi-reports

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_powerbi_reports.py`).

## Purpose

Confirms [[list_powerbi_reports]]'s `run()` returns a successful result with at least one report, using `m365_graph_bridge`'s existing mock data -- no real Microsoft account needed.

## Processing Logic

`test_run_returns_reports` -- calls `ListPowerbiReports().run()` directly and asserts `success` is `True` and `reports` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[list_powerbi_reports]] itself is already mock-mode. Once real Graph API access is wired up, this test would need its own mock of the live HTTP call.
