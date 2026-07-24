---
tool_id: 'search_outlook_email'
title: 'Search Outlook Email'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/outlook]
---

# search-outlook-email

> **Status:** Active. Requires settings (`query` and/or `sender`) before running — a Task, not a Process.

## Purpose

Searches Outlook for emails by topic (keyword) and/or sender — unlike a
plain unfiltered folder listing, this actually filters. Mock-mode until an
Azure AD app registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg:
`{"query": "curriculum", "sender": "registrar", "folder": "inbox", "top": 10}`.
At least one of `query`/`sender` is required.

## Processing Logic

Imports and calls `search_messages()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "folder": "...", "query": "...", "sender": "...", "messages": [...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
