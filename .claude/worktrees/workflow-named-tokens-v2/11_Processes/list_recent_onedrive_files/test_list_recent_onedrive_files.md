---
tool_id: 'test_list_recent_onedrive_files'
title: 'List Recent OneDrive Files Tests'
classification: '05_Processes'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/03-process, tier/zero-input, function/testing, scope/onedrive, connects/list-recent-onedrive-files]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-list-recent-onedrive-files

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_recent_onedrive_files.py`).

## Purpose

Confirms [[list_recent_onedrive_files]]'s `run()` returns a successful result with at least one file, using `m365_graph_bridge`'s existing mock data -- no real Microsoft account needed.

## Processing Logic

`test_run_returns_files` -- calls `ListRecentOnedriveFiles().run()` directly and asserts `success` is `True` and `files` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[list_recent_onedrive_files]] itself is already mock-mode. Once real Graph API access is wired up, this test would need its own mock of the live HTTP call.
