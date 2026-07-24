---
tool_id: 'send_teams_chat_message'
title: 'Send Teams Chat Message'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/teams]
---

# send-teams-chat-message

> **Status:** Active. Requires settings (`chat_id`, `message`) before running — a Task, not a Process.

## Purpose

Sends a message in a 1:1 or group Teams chat. Mock-mode until an Azure AD
app registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"chat_id": "...", "message": "..."}`.

## Processing Logic

Imports and calls `send_chat_message()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "message_id": "...", "status": "sent (mock)"}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
