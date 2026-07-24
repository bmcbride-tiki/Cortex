---
tool_id: 'list_sharepoint_list_items'
title: 'List SharePoint List Items'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/sharepoint, scope/lists]
---

# list-sharepoint-list-items

> **Status:** Active. Requires settings (`site_id`, `list_id`) before running — a Task, not a Process.

## Purpose

Gets a Microsoft List's items (each with a `fields` object of column
values). Mock-mode until an Azure AD app registration exists (see
[[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"site_id": "...", "list_id": "..."}`.
Get both from [[list_sharepoint_sites]]/[[list_sharepoint_lists]].

## Processing Logic

Imports and calls `list_sharepoint_list_items()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "site_id": "...", "list_id": "...", "items": [{"id", "fields"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
