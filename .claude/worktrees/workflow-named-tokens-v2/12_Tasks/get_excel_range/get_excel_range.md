---
tool_id: 'get_excel_range'
title: 'Get Excel Range'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/excel]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# get-excel-range

> **Status:** Active. Requires settings (`file_path`, `worksheet`, `range_address`) before running — a Task, not a Process.

## Purpose

Reads a cell range from an Excel workbook via Microsoft Graph's Workbook
API (cell-level access, distinct from downloading/parsing the whole
file). Mock-mode until an Azure AD app registration exists (see
[[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg:
`{"file_path": "...", "worksheet": "...", "range_address": "A1:B10"}`.

## Processing Logic

Imports and calls `get_excel_range()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "values": [["Header A", "Header B"], [...]]}` — a 2D
array of cell values, mirroring Graph's real Workbook API response shape.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
