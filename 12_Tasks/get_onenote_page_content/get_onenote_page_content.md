---
tool_id: 'get_onenote_page_content'
title: 'Get OneNote Page Content'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/m365, scope/onenote]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# get-onenote-page-content

> **Status:** Active. Requires a setting (`page_id`) before running — a Task, not a Process.

## Purpose

Gets a OneNote page's content as HTML (Graph's real OneNote pages are
HTML-based, not plain text). Mock-mode until an Azure AD app registration
exists (see [[m365_graph_bridge]]).

## Input

One JSON payload, positional CLI arg: `{"page_id": "..."}`. Get a
`page_id` from [[list_onenote_pages]].

## Processing Logic

Imports and calls `get_onenote_page_content()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "page_id": "...", "content_html": "..."}`.

## Notes for AI reuse

Tagged `model: "m365"` in `server.py`'s `TOOL_MODELS`. The `content_html`
is raw HTML — feed it through an HTML-to-text step before treating it as
plain text if downstream tools expect that.
