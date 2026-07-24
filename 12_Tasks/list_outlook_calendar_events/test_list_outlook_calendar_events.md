---
tool_id: 'test_list_outlook_calendar_events'
title: 'List Outlook Calendar Events Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/outlook, scope/calendar, connects/list-outlook-calendar-events]
---

# test-list-outlook-calendar-events

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_outlook_calendar_events.py`).

## Purpose

Confirms [[list_outlook_calendar_events]]'s `run()` returns a successful result with at least one event, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_returns_events` -- calls `run()` directly (with empty date filters) and asserts `success` is `True` and `events` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[list_outlook_calendar_events]] itself is already mock-mode.
