---
tool_id: 'list_sharepoint_lists'
title: 'List SharePoint Lists'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/sharepoint, scope/lists]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# list-sharepoint-lists

> **Status:** Active. Requires a setting (`site_id`) before running — a Task, not a Process.

## Purpose

Lists a SharePoint site's Microsoft Lists. Mock-mode until an Azure AD
app registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"site_id": "..."}`. Get a
`site_id` from [[list_sharepoint_sites]]/[[get_sharepoint_site]].

## Processing Logic

Imports and calls `list_sharepoint_lists()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "site_id": "...", "lists": [{"id", "name"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Feed a `list.id`
into [[list_sharepoint_list_items]]/[[create_sharepoint_list_item]].
