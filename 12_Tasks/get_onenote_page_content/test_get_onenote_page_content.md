---
tool_id: 'test_get_onenote_page_content'
title: 'Get OneNote Page Content Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/onenote, connects/get-onenote-page-content]
---

# test-get-onenote-page-content

> **Status:** Active. Runnable both via `pytest` and directly (`python test_get_onenote_page_content.py`).

## Purpose

Confirms [[get_onenote_page_content]]'s `run()` returns a successful result containing HTML content, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_returns_html` -- calls `run()` directly and asserts `success` is `True` and `content_html` contains an `<html>` tag.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[get_onenote_page_content]] itself is already mock-mode.
