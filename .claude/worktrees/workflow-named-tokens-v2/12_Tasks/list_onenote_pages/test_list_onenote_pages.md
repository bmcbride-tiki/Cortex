---
tool_id: 'test_list_onenote_pages'
title: 'List OneNote Pages Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/onenote, connects/list-onenote-pages]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-list-onenote-pages

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_onenote_pages.py`).

## Purpose

Confirms [[list_onenote_pages]]'s `run()` returns a successful result with at least one page, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_returns_pages` -- calls `run()` directly and asserts `success` is `True` and `pages` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[list_onenote_pages]] itself is already mock-mode.
