---
tool_id: 'upload_notebooklm_sources'
title: 'Upload NotebookLM Sources'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/notebooklm]
---

# upload-notebooklm-sources

> **Status:** Active. Requires settings (`notebook_id`, `file_paths`) before running — a Task, not a Process. **Mock-mode** — no real NotebookLM API/MCP access configured yet.

## Purpose

Uploads source files (PDF/Docx/JSON) to a NotebookLM notebook. Uses
[[notebooklm_bridge]] directly — mock-mode until real API/MCP access
exists. Still validates that every given file path is a real file on disk,
even in mock mode (a real usage mistake should surface immediately).

## Input

One JSON payload, positional CLI arg:
`{"notebook_id": "...", "file_paths": ["C:\\...\\source1.pdf"]}`.

## Processing Logic

Imports and calls `upload_sources()` directly from
`14_Adapters/notebooklm_bridge/notebooklm_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "sources": [{"source_id": "...", "filename": "...", "status": "processed"}, ...]}`.

## Notes for AI reuse

Tagged `model: "notebooklm"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "NotebookLM: Upload Sources" function node
(`function_notebooklm_upload_sources` in `FUNCTIONS_REGISTRY`) — same
underlying `notebooklm_bridge.upload_sources()` call, now also
independently runnable outside a workflow. Typically chained after
[[create_notebooklm_notebook]].
