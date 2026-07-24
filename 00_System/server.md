---
tool_id: 'server'
title: 'Workbrain Cortex Server'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/web-server, scope/cortex-console, connects/core-router, connects/database, connects/workflow-engine, connects/gemini-bridge, connects/copilot-bridge, connects/schedule-analytics]
---

# server

> **Status:** Active. The FastAPI application behind the "Cortex" web console. Run directly: `python server.py` (from `00_System_Core`, or `python .\00_System_Core\server.py` from the repo root) launches Uvicorn on `http://127.0.0.1:8090` with hot-reload.

## Purpose

The single backend process for the whole vault's web UI. Serves the SPA shell (`templates/index.html`) and its page/popup HTML fragments, exposes every REST API the frontend calls (dashboard stats, the class-schedule analytics dashboard, the contacts CRM, process tags, Copilot context lookups, the Agentic Workflow Uploader, the Workflow Builder, and the generic automation-tool runner), and owns startup schema initialization via [[database|database.initialize_database()]].

## Processing Logic

### Boot

`lifespan()` runs `initialize_database()` before the app starts accepting requests, then prints boot/shutdown banners. `/images` and `/static` are mounted as `StaticFiles` from `templates/images` and `templates/static` (Tailwind build output + vendored Font Awesome/Chart.js).

### Live request activity log

**Added 2026-07-20.** `log_requests` (an `@app.middleware("http")` wrapper registered right after the `app = FastAPI(...)` line) prints one numbered line per request as it starts and another as it finishes, e.g. `[REQ #0002] --> GET /api/stats` then `[REQ #0002] <-- GET /api/stats :: 200 (14ms)`. This exists because `log_config=None` (see Operational notes below) silences Uvicorn's own access log entirely, which otherwise leaves the console showing only the boot banner with zero visibility into what the running app is doing as pages are clicked or automations are triggered.

### Page & popup serving

* `GET /` — serves `templates/index.html` (the SPA shell) verbatim.
* `GET /page/{page_name:path}` — reads `templates/{page_name}.html` and returns it raw. The `:path` converter lets `page_name` contain slashes, so this single route serves both top-level pages (`/page/workflows` → `templates/workflows.html`) and per-tool popups (`/page/popup/abc_uploader` → `templates/popup/abc_uploader.html`). Resolves the path and checks it stays inside `templates/` before reading, to block traversal via a crafted `page_name`. 404s (with an inline error `<div>`, not JSON) if the file is missing.
* `GET /apps` — thin wrapper returning `CoreRouter.get_visible_apps()`, the manifest the Processes/Tasks/Workflows pages render cards from.

### Generic automation execution

* `POST /execute/{category}/{tool_id}` — body `{"args": [...]}`. Delegates to `CoreRouter.execute_app_logic` (see [[core_router]]) via `await run_in_threadpool(...)`, running the target tool as a subprocess on a background worker thread and returning `{"success", "message"}`. **Fixed 2026-07-20:** this used to call `execute_app_logic` directly inside the `async def` route, which blocked the single shared event loop for the tool's *entire* run time -- a long [[gemini_bridge|Gemini]]/[[copilot_bridge|Copilot]] browser-automation call (which can take minutes) froze every other request to the whole server for as long as it ran, including totally unrelated pages. `run_in_threadpool` moves that blocking call off the event loop so the server stays responsive to everyone else in the meantime. `POST /api/workflow-builder/run` (below) had the identical problem and got the identical fix.

### Dashboard / stats / graph

* `GET /api/stats` — row counts across the main tracking tables, for the dashboard tiles.
* `GET /api/inbox` — lists pending `.xlsx` reports and `.txt`/`.docx` transcripts sitting in `01_inbox/`.
* `GET /api/network` — builds the force-graph dataset for the System page: nodes/edges spanning the database, server, router, inbox/vault folders, registered automation tasks, live `brain_state.db` tables (introspected via `sqlite_master`, not hardcoded), the class-schedule scraper's raw JSON outputs, and trade/class/exam nodes cross-referenced against `TARGET_TRADES_MAP`.

### Class schedule analytics (backs the Schedule dashboard's slicers/charts)

All under `/api/schedule/*`, all accept optional `trades`/`providers`/`years` comma-separated query params (parsed by `_split_param`) and build parameterized `IN (...)` clauses (`_in_clause`):

* `GET /api/schedule/filters` — distinct trade/provider/school-year values for the slicers.
* `GET /api/schedule/trade-provider-map` — distinct (trade, provider) pairs, for client-side cross-filtering.
* `GET /api/schedule/summary` — total/completed/remaining class counts (`end_date` vs today).
* `GET /api/schedule/class-results` — per-class average AIT exam mark, one series per provider plus a provincial average; trade names are translated from the schedule catalogue's vocabulary to the marks-correlation tables' vocabulary via [[schedule_analytics|resolve_marks_trades]].
* `GET /api/schedule/pass-fail` — pass (>=70) / fail counts.
* `GET /api/schedule/section-averages` — average mark per exam section, per provider + provincial average.
* `GET /api/schedule/supplemental-attempts` — counts re-written exam sections (more than one recorded score per apprentice/section/period, after de-duplicating literal re-import rows).

### Workflow Builder (backs the drag-and-drop pipeline canvas; see [[workflow_engine]])

* `SKILLS_REGISTRY` / `FUNCTIONS_REGISTRY` (module-level constants, not routes) — the static palette of "Skill" and "Function" node types the canvas can drag on, since those have no scanned folder/script the way Tasks/Processes do (see [[core_router]]). `FUNCTIONS_REGISTRY` includes the AI-bridge-backed nodes: `function_gemini_ask` / `function_google_search` / `function_image_generate` (→ [[gemini_bridge]]), and `function_copilot_image_generate` / `function_copilot_agent_ask` / `function_copilot_list_agents` (→ [[copilot_bridge]], added 2026-07-20 alongside that adapter's Designer-image and "@agent" mention support).
* `GET /api/skills` — returns `SKILLS_REGISTRY`.
* `GET /api/workflow-builder/node-registry` — flat, sorted list combining `CoreRouter.get_visible_apps()`'s Tasks/Processes with `SKILLS_REGISTRY` and `FUNCTIONS_REGISTRY`, tagged with `kind` — the full palette the canvas renders.
* `GET/POST/PUT/DELETE /api/workflow-builder/workflows[/{id}]` — CRUD over the `workflow_definitions` table (see [[database]]): save/load/rename/delete a diagram (Drawflow graph JSON).
* `POST /api/workflow-builder/run` — body `{"dry_run": bool, "graph_json": {...}}` or `{"workflow_id": int}`. Instantiates a fresh `WorkflowEngine` (see [[workflow_engine]]) and calls `engine.run(graph_json)` via `await run_in_threadpool(...)` (same blocking-call fix as `/execute/{category}/{tool_id}` above — a workflow containing an AI-bridge node can run for minutes). Returns the engine's full step-by-step execution log.

### Contacts CRM

Standard CRUD at `/api/contacts` (`GET`, `POST`), `/api/contacts/{id}` (`PUT`, `DELETE`), plus `POST /api/contacts/import-raw` which dynamically loads `contact_importer.py` (checked in both a `00_System_Core/adapters/contact-importer/` and a `30_Automation_Scripts/05_Processes/contact_importer/` location) to merge in bulk/pasted contact data.

### Copilot context bridge

`GET /api/copilot/transcripts` and `GET /api/copilot/transcript-content/{id}` expose `transcripts_metadata` rows and their vaulted text content as prompt-fillable context for the [[copilot_bridge]] adapter's UI.

### Tag registry (Processes / Tasks / Workflows)

`GET/POST /api/process-tags` and `POST /api/process-tags/assign` manage the colored tags used to group tools on the Processes, Tasks, and Workflows pages (auto-assigns a color from `PROCESS_TAG_COLOR_PALETTE` if none given). All three pages share the one tag registry, but `GET` takes a `category` query param and `POST .../assign` takes a `category` body field (`'process'` | `'task'` | `'workflow'`, defaults to `'process'`) so each page's assignments stay independent even when a tag name is reused across all three.

### Agentic Workflow Uploader (`abc_uploader`)

`GET/POST /api/abc-uploader/templates`, `DELETE /api/abc-uploader/templates/{name}`, `POST /api/abc-uploader/upload`. The GET/POST/DELETE handlers dynamically load `abc_uploader.py` (via `SourceFileLoader`, re-executed fresh per request so edits apply without a server restart) and call its DB-backed functions directly, in-process. `upload` instead goes through `CoreRouter.execute_app_logic("07_Workflows", "abc_uploader", ["upload", name, ...])` so the Playwright browser automation runs as an isolated subprocess, consistent with every other tool.

## Output

JSON (`JSONResponse`) from every `/api/*` and `/apps`/`/execute` route; raw HTML (`HTMLResponse`) from `/`, `/page/*`.

## Operational notes

* **Port 8090**, not the FastAPI/Uvicorn-typical 8000 or the project's original 8081 -- 8081 turned out to be permanently occupied by something outside this project's control on the primary dev machine (confirmed via `netstat`/`Get-Process`/`tasklist` all disagreeing about what, if anything, held it), so the whole stack moved to 8090.
* **`log_config=None`** is required in the `uvicorn.run(...)` call. Without it, Uvicorn's `--reload` crashes the newly spawned worker process on Windows/Python 3.13 (`logging.config.dictConfig` failing inside `_clearExistingHandlers` across the multiprocessing spawn boundary) every time a watched file changes -- a Windows-specific Uvicorn bug, unrelated to this project's own code.
* **`reload_excludes`** keeps the `--reload` file watcher from treating a tool's own runtime writes (browser profiles, `05_Processes`/`06_Tasks`/`07_Workflows` scripts writing their own output files, `node_modules`, compiled CSS, `*.db`) as source changes that should restart the server.
* `sys.dont_write_bytecode = True` at the top blocks `.pyc` writes inside the watched tree, for the same reason.

## Notes for AI reuse

To add a new REST endpoint for a tool-specific popup (following the `abc_uploader` pattern): dynamically load the tool's script with `SourceFileLoader`, call its plain Python functions directly for anything DB-only/fast, and only route through `CoreRouter.execute_app_logic` for anything that needs to run as an isolated subprocess (browser automation, long-running work). Register the popup's own page at `templates/popup/<tool_id>.html` -- no server-side change needed for that part, since `/page/{page_name:path}` already serves any nested template path.

Any new route that calls a blocking, potentially slow function (subprocess execution, browser automation, an external HTTP call with no timeout) must go through `await run_in_threadpool(...)` rather than calling it directly -- see the Generic automation execution note above for what happens when that's skipped. See [[core_router]] for the subprocess-dispatch layer, [[workflow_engine]] for the pipeline-execution layer, and [[database]] for the schema every `/api/*` route ultimately reads/writes.
