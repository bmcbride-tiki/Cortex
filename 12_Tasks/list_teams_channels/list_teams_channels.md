---
tool_id: 'list_teams_channels'
title: 'List Teams Channels'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/teams]
---

# list-teams-channels

> **Status:** Active. Requires a setting (`team_id`) before running — a Task, not a Process.

## Purpose

Lists a Microsoft Teams team's channels. Mock-mode until an Azure AD app
registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"team_id": "..."}`. Get a
`team_id` from [[list_m365_teams]].

## Processing Logic

Imports and calls `list_channels()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "team_id": "...", "channels": [{"id", "name"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Feed a `channel_id`
into [[post_teams_channel_message]].
