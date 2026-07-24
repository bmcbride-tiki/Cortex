---
tool_id: 'test_list_onenote_notebooks'
title: 'List OneNote Notebooks Tests'
classification: '05_Processes'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/03-process, tier/zero-input, function/testing, scope/onenote, connects/list-onenote-notebooks]
---

# test-list-onenote-notebooks

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_onenote_notebooks.py`).

## Purpose

Confirms [[list_onenote_notebooks]]'s `run()` returns a successful result with at least one notebook, using `m365_graph_bridge`'s existing mock data -- no real Microsoft account needed.

## Processing Logic

`test_run_returns_notebooks` -- calls `ListOnenoteNotebooks().run()` directly and asserts `success` is `True` and `notebooks` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[list_onenote_notebooks]] itself is already mock-mode. Once real Graph API access is wired up, this test would need its own mock of the live HTTP call.
