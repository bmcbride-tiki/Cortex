---
tool_id: 'core_router'
title: 'Core Router'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/routing, function/workflow-execution, function/license-gating, scope/automation-dispatch, scope/workflow-builder, connects/server, connects/workflow-engine, connects/data-processing, connects/logger, connects/gemini-bridge, connects/copilot-bridge]
---

# core-router

> **Status:** Active. Not a standalone script -- has no `__main__` block. Imported by [[server]], which instantiates one `CoreRouter()` and reuses it for the process lifetime. Also imported independently by [[workflow_engine]] (its own `CoreRouter()` instance) to dispatch Task/Process/AI-bridge nodes. This file holds **two unrelated classes** -- see Purpose below.

## Purpose

This file has two distinct jobs, done by two separate classes that share a file only for historical reasons -- they don't call each other:

1. **`CoreRouter`** -- bridges the Cortex web console to the filesystem-based automation catalogue under the numbered category folders (`11_Processes/`, `12_Tasks/`, `13_Workflows/`, `13_Functions/`, `14_Adapters/`). Scans those folders to build the manifest the frontend displays, and launches any one of those tools as an isolated subprocess when triggered.
2. **`CoreWorkflowRouter`** -- an in-process (no subprocess) step executor for the newer `WorkflowPayload`-based execution model (see [[workflow_schema]] in `data_processing/`). Runs a single Python callable against a payload, enforces per-step license/capability gating via [[user_identity]], and logs through `logger.py`'s `CortexLogger`. Used by `canvas_parser.py`'s `VisualWorkflowExecutor` and exercised end-to-end by `sandbox_smoke_test.py`; not yet wired into the live Workflow Builder page (that page still runs through [[workflow_engine]], not this class).

## Processing Logic

### `CoreRouter.get_visible_apps() -> Dict[str, List[Dict]]`

1. Walk each category folder via `CATEGORY_DIR_MAP` -- a translation table from the frontend's old category keys (`05_Processes`, `06_Tasks`, `07_Workflows`, `09_Functions`, `08_Adapters`, still the API contract) to where those folders actually live today (`11_Processes`, `12_Tasks`, `13_Workflows`, `13_Functions`, `14_Adapters`). Every subfolder not starting with `_` or `.` becomes one manifest entry, keyed by folder name as `tool_id`.
2. Derive a display `title` from the `tool_id` (underscores -> spaces, title-cased), except for `TITLE_OVERRIDES` (full rename, e.g. `abc_uploader` -> "ABC Builder") and `ACRONYM_WORDS` (fixed per-word casing, e.g. "tos" -> "TOS").
3. Auto-generate a generic one-line `description` from the category (`"process pipeline"` / `"multi-stage workflow"` / `"AI bridge adapter"` / `"automation task"`) -- no per-tool override; the real explanation lives in that tool's own `.md` companion.
4. Record both `md_path` and `py_path` (vault-relative, POSIX-style) so the UI can open a tool's docs or launch it directly.

### `CoreRouter.execute_app_logic(category, tool_id, args=[]) -> (bool, str)`

Resolves `<category folder>/<tool_id>/<tool_id>.py` via `CATEGORY_DIR_MAP`, then hands off to `_run_script`. `execute_script(script_path, args)` is the sibling entry point for `run://` protocol links, where the path is already resolved and vault-containment already checked by [[server]]'s `_resolve_vault_path`.

### `CoreRouter._run_script(script_path, cwd, args) -> (bool, str)`

Launches the script as a completely separate OS process via `subprocess.run` (never imported in-process), so a crash or hang in the script can't take down the web server, and a Uvicorn `--reload` restart can't kill an in-flight run (`CREATE_NEW_PROCESS_GROUP` on Windows). Combines stdout and stderr into one text blob (stderr appended after a `[RUNTIME STDERR LOG]` marker) and returns `(True, "[SUCCESS]\n...")` or `(False, "[PROCESS ABORTED] ...")` based on exit code.

### `CoreWorkflowRouter.execute_block_async(block_func, payload, next_step_id, block_type, required_capability) -> WorkflowPayload`

1. Resolves the current user's entitlements onto `payload.context` if not already resolved (via [[user_identity]]'s `UserIdentityManager`).
2. If `required_capability` is set and the user isn't licensed for it, logs an error and raises `PermissionError` -- the step never runs.
3. Otherwise calls `block_func(payload.input)` (awaited if it's a coroutine function, called directly otherwise), folds any `new_files` in its returned dict into `payload.input.files` as real `FileReference`s, and calls `payload.transition_to_next_step(...)` to produce the next step's payload.
4. Every stage of this (start, success, failure) is logged as structured JSON via `logger.py`'s `CortexLogger`, tagged with the workflow's `workflow_id`/`correlation_id`.

### `CoreWorkflowRouter.get_building_block_availability(payload, block_capability_map) -> Dict[str, Dict]`

Given a `{block_name: CapabilityFlag}` map, returns each block's `enabled`/`status` (`AVAILABLE` or `GREYED_OUT`)/`required_capability`/`reason` for the current user -- what the Workflow Builder UI uses to grey out a palette entry or canvas node the user isn't licensed for.

## Output

* `CoreRouter.get_visible_apps()`: `{"05_Processes": [...], "06_Tasks": [...], ...}` (legacy keys), each entry `{tool_id, title, description, md_path, py_path}`. Consumed by [[server]]'s `GET /apps` and `GET /api/workflow-builder/node-registry` endpoints.
* `CoreRouter.execute_app_logic(...)` / `execute_script(...)`: a `(success, message)` tuple, surfaced to the frontend's console-log popups.
* `CoreWorkflowRouter.execute_block_async(...)`: a new `WorkflowPayload` for the next step, or a raised `PermissionError`/other exception on failure.

## Notes for AI reuse

A tool becomes runnable via `CoreRouter` purely by existing at `<category folder>/<tool_id>/<tool_id>.py` (script name must match its parent folder name) with a same-named `.md` companion alongside it -- no code change to this file is ever required to add a new one.

`CoreWorkflowRouter` is a separate, newer execution model living in the same file -- don't conflate the two. If a future change makes the live Workflow Builder page run through `CoreWorkflowRouter` instead of [[workflow_engine]], update this doc's Status line and `workflow_engine.md` together.
