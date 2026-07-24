---
tool_id: 'send_outlook_mail'
title: 'Send Outlook Mail'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/outlook]
---

# send-outlook-mail

> **Status:** Active. Requires settings (`to`, `subject`, `body`) before running — a Task, not a Process.

## Purpose

Sends an email via Outlook. Mock-mode until an Azure AD app registration
exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg:
`{"to": "a@example.com, b@example.com", "subject": "...", "body": "..."}`.

## Processing Logic

Imports and calls `send_mail()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "message_id": "...", "status": "sent (mock)"}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
