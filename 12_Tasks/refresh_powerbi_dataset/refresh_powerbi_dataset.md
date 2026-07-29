---
tool_id: 'refresh_powerbi_dataset'
title: 'Refresh Power BI Dataset'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/powerbi]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# refresh-powerbi-dataset

> **Status:** Active. Requires a setting (`dataset_id`) before running — a Task, not a Process.

## Purpose

Triggers a Power BI dataset refresh — the real way to run a Power Query
transformation programmatically (Power Query itself has no standalone
public API; see [[m365_graph_bridge]]'s notes on this). Mock-mode until an
Azure AD app registration exists.

## Input

One JSON payload, positional CLI arg: `{"dataset_id": "..."}`.

## Processing Logic

Imports and calls `refresh_powerbi_dataset()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "refresh_request_id": "...", "status": "..."}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Get a `dataset_id`
from [[list_powerbi_reports]].
