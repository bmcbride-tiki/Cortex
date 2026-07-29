---
tool_id: 'test_create_outlook_calendar_event'
title: 'Create Outlook Calendar Event Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/outlook, scope/calendar, connects/create-outlook-calendar-event]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-create-outlook-calendar-event

> **Status:** Active. Runnable both via `pytest` and directly (`python test_create_outlook_calendar_event.py`).

## Purpose

Confirms [[create_outlook_calendar_event]]'s `run()` returns a successful result with a real-looking event ID, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_creates_event` -- calls `run()` directly and asserts `success` is `True` and `event_id` starts with `evt_`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[create_outlook_calendar_event]] itself is already mock-mode.
