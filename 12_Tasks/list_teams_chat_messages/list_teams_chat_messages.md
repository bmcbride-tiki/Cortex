---
tool_id: 'list_teams_chat_messages'
title: 'List Teams Chat Messages'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/teams]
---

# list-teams-chat-messages

> **Status:** Active. Requires a setting (`chat_id`) before running — a Task, not a Process.

## Purpose

Lists messages in a 1:1 or group Teams chat. Mock-mode until an Azure AD
app registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"chat_id": "..."}`.

## Processing Logic

Imports and calls `list_chat_messages()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "chat_id": "...", "messages": [{"id", "from", "sent", "text"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Pairs with
[[send_teams_chat_message]].
