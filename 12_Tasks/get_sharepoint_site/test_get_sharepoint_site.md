---
tool_id: 'test_get_sharepoint_site'
title: 'Get SharePoint Site Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/sharepoint, connects/get-sharepoint-site]
---

# test-get-sharepoint-site

> **Status:** Active. Runnable both via `pytest` and directly (`python test_get_sharepoint_site.py`).

## Purpose

Confirms [[get_sharepoint_site]]'s `run()` returns a successful result with a real-looking site ID, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_returns_site` -- calls `run()` directly and asserts `success` is `True` and `id` starts with `site_`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[get_sharepoint_site]] itself is already mock-mode.
