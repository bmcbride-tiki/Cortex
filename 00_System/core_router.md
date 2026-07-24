---
tool_id: 'core_router'
title: 'Core Router'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/routing, scope/automation-dispatch, connects/server, connects/workflow-engine, connects/gemini-bridge, connects/copilot-bridge]
---

# core-router

> **Status:** Active. Not a standalone script -- has no `__main__` block. Imported by [[server]], instantiated once (`router = CoreRouter()`), and reused for the lifetime of the process. Also imported independently by [[workflow_engine]] (its own `CoreRouter()` instance) to dispatch Task/Process/AI-bridge nodes.

## Purpose

Bridges the Cortex web console to the filesystem-based automation catalogue under `30_Automation_Scripts/`. It has two jobs: (1) build the manifest of runnable tools the frontend displays on the Processes/Tasks/Workflows pages, purely by scanning folder structure -- no manual registration file to keep in sync -- and (2) execute any one of those tools as an isolated subprocess when the console's "Run" button is clicked.

## Processing Logic

### `get_visible_apps() -> Dict[str, List[Dict]]`

1. Walk `30_Automation_Scripts/05_Processes`, `06_Tasks`, and `07_Workflows`. Every subfolder not starting with `_` or `.` becomes one manifest entry, keyed by folder name as `tool_id`.
2. Derive a display `title` by replacing underscores with spaces and title-casing the `tool_id`.
3. Auto-generate a generic one-line `description` from the category (`"process pipeline"` / `"automation task"` / `"multi-stage workflow"`) -- there's no per-tool override; the real explanation lives in that tool's own `.md` companion.
4. Record `md_path` as `<tool_folder>/<tool_id>.md` (POSIX-style path) so the UI's "MD" button can open it via the `mde://` protocol handler.
5. Separately scan `00_System_Core/adapters/`; any subfolder containing a `<folder-name-with-underscores>.py` script (e.g. `copilot-bridge/copilot_bridge.py`) is registered the same way, but always under the `05_Processes` bucket in the returned manifest, with a description noting it's a "Generative AI adapter".

### `execute_app_logic(category, tool_id, args=[]) -> (bool, str)`

1. Resolve the script path as `30_Automation_Scripts/<category>/<tool_id>/<tool_id>.py`. If that doesn't exist, fall back to `00_System_Core/adapters/<tool_id with underscores replaced by hyphens>/<tool_id>.py` (the adapter-folder-naming convention).
2. If neither resolves, return `(False, "Routing Error: ...")` immediately.
3. Otherwise build `[sys.executable, script_path, *args]` (all args stringified) and run it via `subprocess.run(..., capture_output=True, text=True, cwd=<repo root>)`. On Windows, `creationflags=CREATE_NEW_PROCESS_GROUP` decouples the child from the parent console so a Uvicorn `--reload` restart can't kill an in-flight Playwright/automation run.
4. `PYTHONDONTWRITEBYTECODE=1` is forced into the child's environment.
5. Combine stdout and (prefixed) stderr into one log string. Return `(True, "[SUCCESS]\n<log>")` on exit code 0, else `(False, "[PROCESS ABORTED] ...\n<log>")`.

## Output

* `get_visible_apps()`: `{"05_Processes": [...], "06_Tasks": [...], "07_Workflows": [...]}`, each entry `{tool_id, title, description, md_path}`. Consumed directly by [[server]]'s `GET /apps` endpoint.
* `execute_app_logic(...)`: a `(success, message)` tuple. Consumed by [[server]]'s `POST /execute/{category}/{tool_id}` endpoint (returned to the frontend as `{"success": ..., "message": ...}` for the shared process-launch modal's console log) and by [[workflow_engine]]'s `task`/`process` nodes and every AI-bridge helper ([[gemini_bridge]], [[copilot_bridge]]).

## Notes for AI reuse

A tool becomes runnable from Cortex purely by existing at `30_Automation_Scripts/<category>/<tool_id>/<tool_id>.py` (script name must match its parent folder name) with a same-named `.md` companion alongside it -- no code change to `core_router.py` itself is ever required to add a new tool. The same is true for adapters under `00_System_Core/adapters/` -- see [[gemini_bridge]] and [[copilot_bridge]] for the two currently registered this way.
