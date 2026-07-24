---
tool_id: 'list_onenote_pages'
title: 'List OneNote Pages'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/onenote]
---

# list-onenote-pages

> **Status:** Active. Requires a setting (`notebook_id`) before running — a Task, not a Process.

## Purpose

Lists the pages in a OneNote notebook. Mock-mode until an Azure AD app
registration exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"notebook_id": "..."}`. Get a
`notebook_id` from [[list_onenote_notebooks]].

## Processing Logic

Imports and calls `list_onenote_pages()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "notebook_id": "...", "pages": [{"id", "title"}, ...]}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. Feed a `page.id`
into [[get_onenote_page_content]].
