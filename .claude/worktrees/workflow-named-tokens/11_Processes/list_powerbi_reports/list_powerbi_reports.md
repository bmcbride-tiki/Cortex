---
tool_id: 'list_powerbi_reports'
title: 'List Power BI Reports'
classification: '05_Processes'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/process, domain/03-process, tier/zero-input, function/m365, scope/powerbi]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# list-powerbi-reports

> **Status:** Active. Zero-input, click-and-run Process (like [[generate_vault_map]]) — lists reports in the default Power BI workspace.

## Purpose

Lists reports (and their dataset ids) in the default Power BI workspace.
Mock-mode until an Azure AD app registration exists (see
[[m365_graph_bridge]]).

## Input

None. Running the script processes with no arguments.

## Processing Logic

Imports and calls `list_powerbi_reports()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess needed) and returns its result.

## Output

`{"success": true, "reports": [...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Feed a returned
`dataset_id` into [[refresh_powerbi_dataset]] to trigger a refresh.
