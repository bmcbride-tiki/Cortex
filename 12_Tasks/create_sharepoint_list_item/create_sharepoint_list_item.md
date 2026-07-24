---
tool_id: 'create_sharepoint_list_item'
title: 'Create SharePoint List Item'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/sharepoint, scope/lists]
---

# create-sharepoint-list-item

> **Status:** Active. Requires settings (`site_id`, `list_id`, `fields`) before running — a Task, not a Process.

## Purpose

Adds a new item to a Microsoft List. Mock-mode until an Azure AD app
registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg:
`{"site_id": "...", "list_id": "...", "fields": {"Title": "...", "Status": "..."}}`.
`fields` is a JSON object of column name → value, matching the target
list's actual columns.

## Processing Logic

Imports and calls `create_sharepoint_list_item()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "item_id": "...", "fields": {...}}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
