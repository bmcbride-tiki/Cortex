---
tool_id: 'test_search_outlook_email'
title: 'Search Outlook Email Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/outlook, connects/search-outlook-email]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-search-outlook-email

> **Status:** Active. Runnable both via `pytest` and directly (`python test_search_outlook_email.py`).

## Purpose

Confirms [[search_outlook_email]]'s `run()` correctly filters mock messages down to the ones matching a given sender.

## Processing Logic

`test_run_filters_by_sender` -- calls `run()` with a `query`/`sender` and asserts exactly one matching message comes back.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[search_outlook_email]] itself is already mock-mode.
