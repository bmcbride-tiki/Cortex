---
tool_id: 'create_outlook_calendar_event'
title: 'Create Outlook Calendar Event'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/outlook, scope/calendar]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# create-outlook-calendar-event

> **Status:** Active. Requires settings (`subject`, `start`, `end`) before running — a Task, not a Process.

## Purpose

Creates an Outlook calendar event. Mock-mode until an Azure AD app
registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg:
`{"subject": "...", "start": "2026-08-01T10:00:00Z", "end": "2026-08-01T11:00:00Z", "attendees": "a@example.com, b@example.com"}`.
`attendees` is optional.

## Processing Logic

Imports and calls `create_calendar_event()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "event_id": "...", "subject": "...", "start": "...", "end": "...", "attendees": [...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
