---
tool_id: 'list_onenote_notebooks'
title: 'List OneNote Notebooks'
classification: '05_Processes'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/process, domain/03-process, tier/zero-input, function/m365, scope/onenote]
---

# list-onenote-notebooks

> **Status:** Active. Zero-input, click-and-run Process (like [[generate_vault_map]]) — lists the signed-in user's OneNote notebooks.

## Purpose

Lists the signed-in user's OneNote notebooks. Mock-mode until an Azure AD
app registration exists (see [[m365_graph_bridge]]).

## Input

None. Running the script processes with no arguments.

## Processing Logic

Imports and calls `list_onenote_notebooks()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "notebooks": [{"id", "name"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Feed a `notebook.id`
into [[list_onenote_pages]].
