---
tool_id: 'download_m365_file'
title: 'Download M365 File'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/onedrive, scope/sharepoint]
---

# download-m365-file

> **Status:** Active. Requires settings (`file_path`, `local_output_dir`) before running — a Task, not a Process.

## Purpose

Downloads a file from OneDrive/SharePoint to a local folder, for a
downstream tool (e.g. [[import_from_word]], [[read_powerpoint]]) to read.
Mock-mode until an Azure AD app registration exists (see
[[m365_graph_bridge]]) — still writes a real placeholder file even in mock
mode, so downstream real parsing has something real to chain onto.

## Input

One JSON payload, positional CLI arg:
`{"file_path": "...", "local_output_dir": "..."}`.

## Processing Logic

Imports and calls `download_file()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "local_path": "..."}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
