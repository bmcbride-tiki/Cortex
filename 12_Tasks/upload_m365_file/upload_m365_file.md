---
tool_id: 'upload_m365_file'
title: 'Upload M365 File'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/onedrive, scope/sharepoint]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# upload-m365-file

> **Status:** Active. Requires settings (`local_path`, `destination_path`) before running — a Task, not a Process.

## Purpose

Uploads a local file to OneDrive/SharePoint. Mock-mode until an Azure AD
app registration exists (see [[m365_graph_bridge]]) — still validates
`local_path` is a real, existing file even in mock mode.

## Input

One JSON payload, positional CLI arg:
`{"local_path": "...", "destination_path": "..."}`.

## Processing Logic

Imports and calls `upload_file()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "item_id": "...", "web_url": "..."}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Pairs with
[[export_to_word]]/[[write_powerpoint]]/etc. for "generate a file, then
push it to M365" workflows.
