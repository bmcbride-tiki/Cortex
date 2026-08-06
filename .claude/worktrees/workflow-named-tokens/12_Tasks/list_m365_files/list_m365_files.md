---
tool_id: 'list_m365_files'
title: 'List M365 Files'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/onedrive, scope/sharepoint]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# list-m365-files

> **Status:** Active. Requires a setting (`folder_path`) before running — a Task, not a Process.

## Purpose

Lists files in a OneDrive/SharePoint folder. Mock-mode until an Azure AD
app registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"folder_path": "..."}`.

## Processing Logic

Imports and calls `list_files()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "files": [{"name", "item_id", "size", "web_url"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Feed a listed
`file_path`/`name` into [[download_m365_file]] to fetch its content.
