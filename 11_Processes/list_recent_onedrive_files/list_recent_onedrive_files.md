---
tool_id: 'list_recent_onedrive_files'
title: 'List Recent OneDrive Files'
classification: '05_Processes'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/process, domain/03-process, tier/zero-input, function/m365, scope/onedrive]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# list-recent-onedrive-files

> **Status:** Active. Zero-input, click-and-run Process (like [[generate_vault_map]]) — lists recently modified/accessed OneDrive files.

## Purpose

Lists recently modified/accessed OneDrive files. Mock-mode until an Azure
AD app registration exists (see [[m365_graph_bridge]]).

## Input

None. Running the script processes with no arguments.

## Processing Logic

Imports and calls `list_recent_onedrive_files()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "files": [{"name", "item_id", "last_modified"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Complements
[[list_m365_files]] (folder-scoped) with a recency-scoped listing.
