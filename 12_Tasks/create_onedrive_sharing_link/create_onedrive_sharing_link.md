---
tool_id: 'create_onedrive_sharing_link'
title: 'Create OneDrive Sharing Link'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/onedrive]
---

# create-onedrive-sharing-link

> **Status:** Active. Requires a setting (`file_path`) before running — a Task, not a Process.

## Purpose

Creates a shareable link for a OneDrive file. Mock-mode until an Azure AD
app registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"file_path": "..."}`.

## Processing Logic

Imports and calls `create_onedrive_sharing_link()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "share_url": "...", "link_type": "view"}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Pairs with
[[upload_m365_file]] (upload, then share).
