---
tool_id: 'list_m365_teams'
title: 'List M365 Teams'
classification: '05_Processes'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/process, domain/03-process, tier/zero-input, function/m365, scope/teams]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# list-m365-teams

> **Status:** Active. Zero-input, click-and-run Process (like [[generate_vault_map]]) — no settings, just lists the Teams the signed-in M365 user belongs to.

## Purpose

Lists the Microsoft Teams the signed-in user belongs to. Mock-mode until
an Azure AD app registration exists (see [[m365_graph_bridge]]).

## Input

None. Running the script processes with no arguments.

## Processing Logic

Imports and calls `list_teams()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess needed) and returns its result.

## Output

`{"success": true, "teams": [...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS` for the Workflow
Builder's classification system — see [[model_classifications]].
