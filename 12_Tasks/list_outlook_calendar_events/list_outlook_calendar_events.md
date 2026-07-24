---
tool_id: 'list_outlook_calendar_events'
title: 'List Outlook Calendar Events'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/outlook, scope/calendar]
---

# list-outlook-calendar-events

> **Status:** Active. Requires settings (`start_date`, `end_date`) before running — a Task, not a Process.

## Purpose

Lists Outlook calendar events in a date range. Mock-mode until an Azure AD
app registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg:
`{"start_date": "2026-08-01", "end_date": "2026-08-07"}` (both optional).

## Processing Logic

Imports and calls `list_calendar_events()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "events": [{"id", "subject", "start", "end"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
