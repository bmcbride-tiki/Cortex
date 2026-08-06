---
tool_id: 'post_teams_channel_message'
title: 'Post Teams Channel Message'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/teams]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# post-teams-channel-message

> **Status:** Active. Requires settings (`team_id`, `channel_id`, `message`) before running — a Task, not a Process.

## Purpose

Posts a message to a Microsoft Teams channel. Mock-mode until an Azure AD
app registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg:
`{"team_id": "...", "channel_id": "...", "message": "..."}`. Get
`team_id`/`channel_id` from [[list_m365_teams]]/[[list_teams_channels]].

## Processing Logic

Imports and calls `post_channel_message()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "message_id": "...", "status": "posted (mock)"}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
