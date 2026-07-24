---
tool_id: 'get_sharepoint_site'
title: 'Get SharePoint Site'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/sharepoint]
---

# get-sharepoint-site

> **Status:** Active. Requires a setting (`site_path`) before running — a Task, not a Process.

## Purpose

Gets a specific SharePoint Online site's details, for targeting its Lists
or document library. Mock-mode until an Azure AD app registration exists
(see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"site_path": "example.sharepoint.com:/sites/apprenticeship"}`.

## Processing Logic

Imports and calls `get_sharepoint_site()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "id": "...", "name": "...", "web_url": "..."}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Feed the returned
`id` into [[list_sharepoint_lists]].
