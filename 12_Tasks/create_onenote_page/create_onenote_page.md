---
tool_id: 'create_onenote_page'
title: 'Create OneNote Page'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/onenote]
---

# create-onenote-page

> **Status:** Active. Requires settings (`section_id`, `title`) before running — a Task, not a Process.

## Purpose

Creates a new OneNote page in a section. Mock-mode until an Azure AD app
registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg:
`{"section_id": "...", "title": "...", "content": "<p>...</p>"}`. `content`
is HTML, matching Graph's real OneNote page format.

## Processing Logic

Imports and calls `create_onenote_page()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "page_id": "...", "title": "...", "status": "created (mock)"}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`.
