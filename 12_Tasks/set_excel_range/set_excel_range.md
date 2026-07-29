---
tool_id: 'set_excel_range'
title: 'Set Excel Range'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/excel]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# set-excel-range

> **Status:** Active. Requires settings (`file_path`, `worksheet`, `range_address`, `values`) before running — a Task, not a Process.

## Purpose

Writes a cell range in an Excel workbook via Microsoft Graph's Workbook
API. Mock-mode until an Azure AD app registration exists (see
[[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg:
`{"file_path": "...", "worksheet": "...", "range_address": "A1:B10", "values": [["a", "b"]]}`.

## Processing Logic

Imports and calls `set_excel_range()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "updated_range": "...", "row_count": N}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Pairs with
[[get_excel_range]] for read-transform-write Excel pipelines.
