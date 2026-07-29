---
tool_id: 'web_scrape'
title: 'Web Scrape'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/web]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# web-scrape

> **Status:** Active. Standalone-capable utility, also drag-and-droppable onto the Workflow Builder canvas (category `09_Functions`).

## Purpose

Fetches a URL and extracts its visible, readable text. Moved out of
`workflow_engine.py`'s built-in function ladder (`function_web_scrape`,
`_scrape_url`) since it needs nothing from a graph. Only use this for pages
you have the right to access.

## Input

One JSON payload, positional CLI arg: `{"url": "https://..."}`.

## Processing Logic

1. Fetches the page (30s timeout, a plain browser-like User-Agent).
2. Strips `<script>`/`<style>` blocks via `lxml`.
3. Joins remaining visible text nodes, capped at 5000 characters so one
   scrape can't flood a downstream step.

## Output

`{"success": true, "text": "..."}` on success, or
`{"success": false, "response": "<error>"}` (non-zero exit code) on
failure (bad URL, network error, non-2xx response).

## Notes for AI reuse

Dispatched by [[workflow_engine]] via the generic `09_Functions` path (same
mechanism as Task/Process/Adapter) — see [[core_router]].
