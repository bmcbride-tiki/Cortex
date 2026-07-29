---
tool_id: 'server'
title: 'Cortex Workbrain Operation Console'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/web-server, function/license-gating, scope/cortex-console, scope/workflow-builder, connects/core-router, connects/database, connects/workflow-engine, connects/data-processing, connects/gemini-bridge, connects/copilot-bridge]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# server

> **Status:** Active. The FastAPI application behind the "Cortex" web console. Run directly: `python 00_System/server.py` (or `python server.py` from inside `00_System/`) launches Uvicorn on `http://127.0.0.1:8080` with hot-reload. At ~1,560 lines this is the largest file in the project -- routes are grouped under `# --- SECTION NAME ---` comment banners; skim for those to find the relevant part.

## Purpose

The single backend process for the Cortex web UI. Serves the SPA shell (`templates/index.html`) and every page/popup HTML fragment, exposes every REST API the frontend calls, and owns startup schema initialization via [[database|database.initialize_database()]].

## Processing Logic

### Boot & live request log

`lifespan()` runs `initialize_database()` before the app accepts requests, then prints boot/shutdown banners. `log_requests` (an `@app.middleware("http")` wrapper) prints one numbered line per request as it starts and finishes (`[REQ #0002] --> GET /api/stats` / `[REQ #0002] <-- ... :: 200 (14ms)`), since `log_config=None` (see Operational notes) silences Uvicorn's own access log entirely. `/images`, `/generated-images`, and `/static` are mounted as `StaticFiles`.

### Dashboard / stats / graph

* `GET /api/stats` -- row counts across the main tracking tables.
* `GET /api/inbox` -- pending `.xlsx` reports and `.txt`/`.docx` transcripts sitting in `01_inbox/`.
* `GET /api/network` -- force-graph dataset for the Network page (database tables, tasks, trades/classes/exams, all introspected live rather than hardcoded).

### Copilot context bridge

`GET /api/copilot/transcripts` / `GET /api/copilot/transcript-content/{id}` -- expose `transcripts_metadata` rows and their vaulted text as prompt-fillable context for the [[copilot_bridge]] adapter's UI.

### App/tool discovery

* `GET /apps` -- thin wrapper over `CoreRouter.get_visible_apps()` (see [[core_router]]).
* `GET /api/skills` -- returns `SKILLS_REGISTRY` (module-level constant; Skills have no scanned folder, unlike Tasks/Processes).
* `GET /api/workflow-builder/node-registry` -- the full Workflow Builder palette: Tasks/Processes/Adapters/Functions from `CoreRouter.get_visible_apps()` plus `SKILLS_REGISTRY`/`FUNCTIONS_REGISTRY`, each entry enriched with:
  * `model` -- which AI backend it touches (via `TOOL_MODELS`/`ADAPTER_MODELS`), feeding `model_classifications.py`'s classification-ceiling badge client-side.
  * `required_capability`/`licensed` -- whether the *current* user (via [[user_identity]]'s `UserIdentityManager`) holds the license/SKU a node needs (`MODEL_CAPABILITY_MAP`; only `m365`→`M365_BASE` and `copilot`→`COPILOT_BASIC` are gated today -- gemini/claude/chatgpt/notebooklm run through their own signed-in bridge sessions, not an M365/Google entitlement).
  * `icon_source`/`svgl_icon_url`/`fa_icon` -- a real per-product logo (`TOOL_SVGL_MAP`, verified against the live SVGL API -- Outlook/Teams/SharePoint/OneNote/OneDrive/Excel/PowerPoint/Word/Copilot/Gemini/Claude/OpenAI each get their own, not one blanket "Microsoft" mark) or a semantic Font Awesome glyph (`TOOL_FA_ICON_MAP`, checked against the actually-installed FA6 Free icon set) for anything without a real brand logo (Power BI, NotebookLM, generic containers/logic/import-export).

### Workflow Builder (backs the drag-and-drop pipeline canvas; see [[workflow_engine]])

* `GET/POST/PUT/DELETE /api/workflow-builder/workflows[/{id}]` -- CRUD over the `workflow_definitions` table (see [[database]]): save/load/rename/delete a diagram (Drawflow graph JSON).
* `GET /api/workflow-builder/workflows/{id}/map` -- **new**: builds a read-only, stage-column structural map of a saved workflow for the Workflow Map page. Reuses `WorkflowEngine._parse_graph()`/`_find_entry_nodes()` (see [[workflow_engine]]) to get the real, container-flattened node graph rather than re-parsing the Drawflow export here, then layers nodes into stages by BFS depth from the entry node(s) (cycle-safe, since a Review Gate's loop-back edge is a valid cycle). Each node carries the same icon/license fields as the node-registry endpoint above, read from the saved node's own data if present (workflows saved before the icon feature existed fall back to the same `TOOL_SVGL_MAP`/`TOOL_FA_ICON_MAP` lookup).
* `POST /api/workflow-builder/run` -- body `{"dry_run": bool, "graph_json": {...}}` or `{"workflow_id": int}`. Runs a `WorkflowEngine` via `await run_in_threadpool(...)` (a workflow containing an AI-bridge node can run for minutes; this keeps the event loop responsive to everyone else meanwhile). Returns the engine's full step-by-step execution log -- also what the Workflow Map page's "Preview Dry-Run Trace" button calls to overlay real per-node status onto the map.

### Review checkpoints

`GET /api/workflow-checkpoints` (status filter: pending/reviewed/all) and `POST /api/workflow-checkpoints/{id}/resolve` -- the "Awaiting Review" queue written by a `human_review_checkpoint` workflow node when a run pauses for a human hand-off; backs the Review Queue page.

### Tag registry (Processes / Tasks / Functions / Adapters)

`GET/POST /api/process-tags` and `POST /api/process-tags/assign` -- colored tags shared across those pages, scoped per-category so the same tag name can be reused independently on each.

### Agentic Workflow Uploader (`abc_uploader`)

`GET/POST /api/abc-uploader/templates`, `DELETE .../templates/{name}`, `POST .../upload`. GET/POST/DELETE dynamically load `abc_uploader.py` (via `SourceFileLoader`) and call its DB-backed functions in-process; `upload` goes through `CoreRouter.execute_app_logic("06_Tasks", "abc_uploader", [...])` so the Playwright browser automation runs as an isolated subprocess.

### Dedicated task-popup uploads

`POST /api/uploads/exam-pass-fail`, `/transcripts`, `/word-to-excel-exam`, `/curriculum-guide-to-tos` -- each saves the uploaded file(s) into the right `01_inbox/` subfolder (collision-safe, via `_save_upload_collision_safe`), then dispatches the matching import/processing Task through `router.execute_app_logic`.

### In-app markdown reader/editor & run:// links

`GET/POST /api/md-editor/read` / `/save` -- read/write a vault-relative markdown file, guarded by `_resolve_vault_path` (resolves the path fully and checks it's still inside the project root, blocking `../` traversal from a crafted link). `POST /api/protocol/run` -- executes a `run://` link's target script via `router.execute_script`, same containment guard. `POST /execute/{category}/{tool_id}` -- the generic automation-tool runner, via `router.execute_app_logic`.

### Page & popup serving

`GET /` serves `templates/index.html` verbatim. `GET /page/{page_name:path}` reads `templates/{page_name}.html` raw (the `:path` converter lets it serve both top-level pages and nested popups, e.g. `/page/popup/abc_uploader`), with the same vault-containment check as the markdown/run:// endpoints, and a 404 (inline HTML error, not JSON) if the file is missing.

## Output

JSON (`JSONResponse`) from every `/api/*` and `/apps`/`/execute` route; raw HTML (`HTMLResponse`) from `/`, `/page/*`.

## Operational notes

* **Port 8080.** `reload=True` watches project files and restarts on change; `reload_excludes` keeps that watcher from treating a tool's own runtime writes (`*.db`, browser-automation profile folders, `11_Processes`/`12_Tasks`/`13_Workflows`/`14_Adapters` script output, `node_modules`, compiled CSS) as source changes.
* **`log_config=None`** avoids a Windows-specific Uvicorn `--reload` crash (`dictConfig` reconfiguration failing across the spawn boundary) -- unrelated to this project's own code.
* Every route that calls a blocking, potentially slow function (subprocess execution, browser automation) goes through `await run_in_threadpool(...)` rather than calling it directly, so one long-running call (a Gemini/Copilot browser-automation pass can take minutes) can't freeze the single shared event loop for every other request.
* `sys.dont_write_bytecode = True` blocks `.pyc` writes inside the watched tree.

## Notes for AI reuse

To add a new REST endpoint for a tool-specific popup: dynamically load the tool's script with `SourceFileLoader` for anything DB-only/fast, and only route through `CoreRouter.execute_app_logic`/`execute_script` for anything that needs to run as an isolated subprocess. Register the popup's own page at `templates/popup/<tool_id>.html` -- no server-side change needed, since `/page/{page_name:path}` already serves any nested template path.

See [[core_router]] for the subprocess-dispatch layer (and its separate, newer `CoreWorkflowRouter` in-process execution model), [[workflow_engine]] for the Drawflow pipeline-execution layer, [[database]] for the schema every `/api/*` route reads/writes, and `data_processing/user_identity.py`/`svgl_icon_manager.py` for the license-gating and icon-resolution logic the node-registry/workflow-map endpoints share.
