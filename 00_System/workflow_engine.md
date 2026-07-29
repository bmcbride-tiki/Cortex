---
tool_id: 'workflow_engine'
title: 'Workflow Engine'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/workflow-execution, scope/workflow-builder, connects/server, connects/core-router, connects/gemini-bridge, connects/copilot-bridge, connects/notebooklm-bridge, connects/database]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# workflow-engine

> **Status:** Active. Not a standalone script -- has no `__main__` block. Imported by [[server]] and instantiated fresh (`WorkflowEngine(dry_run=...)`) per `POST /api/workflow-builder/run` request.

## Purpose

Actually runs a saved Workflow Builder diagram: a user-drawn graph of connected boxes ("nodes") built on the frontend's Drawflow canvas (`templates/workflow-builder.html`), saved as JSON into the `workflow_definitions` table (see [[database]]). This module walks that graph node by node, in the order the diagram's arrows dictate, running each node's real action (call an AI bridge, run a Task/Process script, export/import a file, branch on a condition, etc.) and threading each node's captured text output into whichever node(s) come next via `{{node_id}}` token substitution.

## Processing Logic

### Graph parsing (`_parse_graph`, `_flatten_containers`, `_find_entry_nodes`)

A Drawflow export is organized into "modules" (Home canvas + one per Container node's own sub-diagram); `_parse_graph` merges all of them into one flat node/edge map. `_flatten_containers` then splices every Container node out in place, rewiring its module's own entry/exit nodes directly to the container's former predecessors/successors -- repeated until no containers remain, so nested containers resolve too. This means the rest of the engine never has to treat a container specially; by the time `run()` starts walking, it's just a flat graph.

### Token substitution (`_substitute_tokens`, `_gather_upstream_text`)

Every node's captured output is stored keyed by that node's own ID in `self.context`. A later node can reference an earlier one's result via a `{{node_id}}` placeholder in its own settings text; `_gather_upstream_text` additionally auto-collects the output of every node feeding directly into a given node, as its default input, with no token needed.

### Per-node dispatch (`_execute_node` / `_execute_function_node`)

Four node `kind`s: `task`/`process` (dispatch through [[core_router]]'s `execute_app_logic`, same mechanism the rest of Cortex uses), `skill` (ask Copilot to act as a described persona), and `function` -- either a real script from `13_Functions/` (`category == "09_Functions"`, dispatched through the exact same `execute_app_logic` path as task/process/adapter) or one of the many built-in operations handled by a big if/elif ladder over `tool_id` in `_execute_function_node` (string ops, logic gates, JSON parse, file export/import (Word/PDF/JSON/Markdown via `docx`/`fpdf`/`pypdf`), web scraping, and the AI-bridge-backed functions listed below).

### AI bridge functions (`_ask_copilot`, `_ask_gemini`, `_ask_claude`, `_ask_chatgpt`, `_generate_image_gemini`, `_create_notebooklm_notebook`, `_upload_notebooklm_sources`, `_run_notebooklm_prompt_loop`)

**⚠ Corrected during this documentation pass:** this section previously listed `_ask_copilot_agent`, `_generate_image_copilot`, and `_list_copilot_agents` as methods here -- they don't exist in the current file. Those Copilot-agent-specific behaviors moved out to real Task/Process folders (`12_Tasks/ask_copilot_agent`, `12_Tasks/generate_copilot_image`, `11_Processes/list_copilot_agents`, dispatched the normal Task/Process way via [[core_router]]), leaving only the plain single-turn `_ask_copilot` here for the built-in "Skill" node kind. `_ask_claude`/`_ask_chatgpt` (mock-mode until real API keys exist) were missing from this list entirely and are documented here now.

Each one builds a JSON payload and dispatches it through `self.router.execute_app_logic("08_Adapters", "copilot_bridge"|"gemini_bridge"|"claude_bridge"|"chatgpt_bridge"|"notebooklm_bridge", [payload])` -- exactly the same adapter calls [[server]]'s Copilot/Gemini pages make directly. `_parse_bridge_json` (static helper) picks the single `{"success": ...}` JSON line out of the router's captured output rather than assuming the whole captured blob is valid JSON, since stderr logs can legitimately follow it (see [[core_router]]'s own notes on this).

### Loops and safety limits (`_run_review_gate`, `MAX_TOTAL_STEPS`)

A Review Gate node asks an AI to judge the upstream text against a plain-English pass/fail criteria; on fail (with attempts remaining), `run()`'s queue gets the loop-back target inserted at the front rather than the back, so it re-runs immediately ahead of anything else queued. Each gate has its own `max_attempts`; a global `MAX_TOTAL_STEPS = 200` additionally guards against a runaway loop even if a gate is misconfigured.

### Dry run mode (`dry_run: bool`)

Default `True`. Every AI call, file write, and web request instead returns a `"[DRY RUN] ..."` placeholder describing what would have happened -- lets a workflow's wiring/logic be validated instantly and safely before a real run (`dry_run=False`), which can be slow and has real side effects.

## Output

`run(graph_json) -> {"success": bool, "steps": [{"node_id", "title", "kind", "status", "output"}, ...]}` -- a full step-by-step execution log, returned as JSON by [[server]]'s `POST /api/workflow-builder/run` endpoint to the Workflow Builder's run-results panel.

## Notes for AI reuse

* To add a new *built-in* Function node type (no real script on disk): add a `FUNCTIONS_REGISTRY` entry in [[server]] (palette metadata) and a matching `tool_id == "..."` branch in `_execute_function_node` here. Follow the existing grouping-by-comment-header convention (String/logic, File export/import, Web, Gemini-backed, Copilot-backed).
* To add a new *file-based* Function (a real script under `13_Functions/`): just create the folder/script (matching a Task's shape, e.g. `human_review_checkpoint.py`) -- `server.py`'s node-registry endpoint auto-discovers everything under `13_Functions/` via [[core_router]] and merges it in with `category: "09_Functions"`, and this file's `_execute_node` already dispatches any `kind == "function"` node with that category through the generic `execute_app_logic` path. No engine code changes needed per new file-based function.
* Any new AI-bridge function should reuse `_parse_bridge_json` rather than re-implementing JSON-line extraction -- this is the one place that bug (parsing from the first `{"success"` match to the end of the string, rather than just that one line) was fixed project-wide.
* See [[core_router]] for how Task/Process/adapter dispatch actually works, [[gemini_bridge]], [[copilot_bridge]], and [[notebooklm_bridge]] for what the AI-bridge functions call into, and [[database]] for the `workflow_definitions` table this engine's inputs are loaded from.
* `function_notebooklm_create`/`function_notebooklm_upload_sources`/`function_notebooklm_prompt_loop` call into [[notebooklm_bridge]], which is mock-only (no live NotebookLM API/MCP access exists yet) -- `_extract_json_field` lets `upload_sources`/`prompt_loop` pull `notebook_id` straight out of an upstream Create Notebook node's JSON output when chained directly, without a hand-written `{{node_id}}` token.
