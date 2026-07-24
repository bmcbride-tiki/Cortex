---
tool_id: 'test_create_onenote_page'
title: 'Create OneNote Page Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/onenote, connects/create-onenote-page]
---

# test-create-onenote-page

> **Status:** Active. Runnable both via `pytest` and directly (`python test_create_onenote_page.py`).

## Purpose

Confirms [[create_onenote_page]]'s `run()` returns a successful result with a real-looking page ID, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_creates_page` -- calls `run()` directly and asserts `success` is `True` and `page_id` starts with `page_`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[create_onenote_page]] itself is already mock-mode.
