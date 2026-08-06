---
tool_id: 'abc_uploader'
title: 'Agentic Workflow Uploader (Agent Builder Console)'
classification: '07_Workflows'
data_policy: 'internal'
execution_engine: 'playwright'
tags: [type/workflow, domain/07-workflows, tier/single-input, function/automation, scope/agent-builder-console]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# abc-uploader

> **Status:** Active, adapted from a sibling project. Has a dedicated Cortex modal (not the generic shared one) plus a CLI / CoreRouter JSON-payload dual mode. The Agent Builder Console page selectors are unverified best-effort guesses -- see Known Limitations.

## Purpose

Keeps a registry of JSON workflow templates and automates opening `https://agentbuilderconsole.com` to upload a selected one via Playwright, mirroring the `copilot_bridge` adapter's persistent-profile pattern for sites that require login.

## Storage

* **Templates:** stored entirely in `brain_state.db` table `abc_templates` (`name`, `description`, `filename`, `content`, `created`, `updated`) -- `content` is the raw JSON text. There is no on-disk template file; the database is the single source of truth, so templates travel with `brain_state.db` (backups, sync, etc). At upload time the content is handed to Playwright as an in-memory buffer (`file_input.set_input_files({"name", "mimeType", "buffer"})`), never written to disk.
* **Target URL:** single value in `brain_state.db` table `abc_uploader_settings` (singleton row). Defaults to `https://agentbuilderconsole.com` the first time it's touched; override with `set-url` if it ever changes.
* **Browser profile:** `C:/Cortex/abc_uploader_browser_profile/` (persistent, outside the watched code tree -- same rationale as `copilot_browser_profile`, kept out of git via `.gitignore`). Log in once in headed mode and the session persists across runs.

## From the Cortex console (primary UI)

Registered in `core_router.py` under `06_Tasks`, so it shows up on the **Tasks** page. Unlike most tools it has its own purpose-built popup instead of the generic args-box launcher, living as a standalone fragment at `00_System/templates/popup/abc_uploader.html` (markup + its own `<script>`), not inlined into `tasks.html`. It's fetched once and cached client-side by the shared `window.loadPopup('abc_uploader', 'openAbcUploaderModal')` helper defined in `index.html` (served via `GET /page/popup/abc_uploader`, since `serve_subpage` accepts nested paths). Every future tool-specific popup should follow the same convention: one file per tool under `templates/popup/`, opened via `loadPopup`.

The popup itself:

* A scrollable, radio-selectable list of templates (name + description), each with a delete icon.
* An "Add Template" panel: file picker (`.json`, multi-select), Name (used only when exactly one file is chosen -- otherwise each file is auto-named from its filename), Description (applied to every file in the batch) -- posts one multipart request per file to the API below, with live per-file progress in the console log.
* A headless checkbox and a Run button (disabled until a template is selected), plus a console log of the result.

Backed by dedicated REST endpoints in `server.py` (called directly from the popup's JS, not through `/execute`):

| Endpoint | Purpose |
| --- | --- |
| `GET /api/abc-uploader/templates` | List templates + current service URL |
| `POST /api/abc-uploader/templates` | Add one (multipart: `file`, `name`, `description`) |
| `DELETE /api/abc-uploader/templates/{name}` | Remove one |
| `POST /api/abc-uploader/upload` | Run the Playwright upload (`{name, headless}`), dispatched through `CoreRouter.execute_app_logic` so the browser automation still runs as an isolated subprocess |

## CLI usage

```bash
python abc_uploader.py list
python abc_uploader.py add <path/to/template.json> --name NAME [--description DESC]
python abc_uploader.py remove <name>
python abc_uploader.py set-url <url>
python abc_uploader.py upload <name> [--headless]
```

CoreRouter / programmatic callers can instead pass a single JSON payload argument, matching the `copilot_bridge.py` pattern:

```bash
python abc_uploader.py "{\"action\": \"upload\", \"name\": \"my-template\", \"headless\": false}"
```

Supported actions: `list`, `add`, `remove`, `set_url`, `upload`. The payload mode always prints a single JSON result line to stdout. Note `add` in both CLI and payload mode takes a local file **path** (`add_template_from_path`, which reads the file then delegates to the same DB-writing `add_template` the API uses) -- the API endpoint instead reads the uploaded multipart bytes directly, with no intermediate file.

## Processing Logic (`upload`)

1. Look up the template's `content`/`filename` and the configured `service_url`; fail fast if either is missing.
2. Launch a persistent Chromium/Edge context against `abc_uploader_browser_profile` (headed by default, so an existing login/SSO session can be reused or established).
3. Navigate to the console URL, best-effort click a "Load/Upload/Choose File/Select File" button if present, then locate an `input[type="file"]` and attach the template's JSON as an in-memory buffer.
4. Best-effort click a submit-style button ("OK/Submit/Upload/Load").
5. Close the browser context immediately after the submit click (short fixed pause first so the site has time to process the request) -- no manual-review wait. Confirmed selectors and verified live, per the headed test run.

## Known Limitations

* **Selectors are unverified beyond one manual smoke test.** `DEFAULT_LOAD_SELECTORS` / `DEFAULT_FILE_INPUT_SELECTORS` / `DEFAULT_SUBMIT_SELECTORS` at the top of `abc_uploader.py` are generic guesses. They worked for at least one headed run against the real Agent Builder Console, but if the site's DOM changes or a different flow shows up, update them there.
