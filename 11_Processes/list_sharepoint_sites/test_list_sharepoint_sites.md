---
tool_id: 'test_list_sharepoint_sites'
title: 'List SharePoint Sites Tests'
classification: '05_Processes'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/03-process, tier/zero-input, function/testing, scope/sharepoint, connects/list-sharepoint-sites]
---

# test-list-sharepoint-sites

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_sharepoint_sites.py`).

## Purpose

Confirms [[list_sharepoint_sites]]'s `run()` returns a successful result with at least one site, using `m365_graph_bridge`'s existing mock data -- no real Microsoft account needed.

## Processing Logic

`test_run_returns_sites` -- calls `ListSharepointSites().run()` directly and asserts `success` is `True` and `sites` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[list_sharepoint_sites]] itself is already mock-mode. Once real Graph API access is wired up, this test would need its own mock of the live HTTP call.
