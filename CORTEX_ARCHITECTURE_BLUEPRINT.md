# CORTEX Architecture Blueprint — Production Roadmap Edition

> **Document Version:** 2.0
> **Date:** 2026-07-31
> **Supersedes:** `CORTEX_FUNCTIONAL_STATUS_REPORT.md` and v1.0 of this document (see Appendix A)
> **Status:** The authoritative architecture reference for Cortex. Read this before adding any new capability, folder, or dependency.
> **Reading note:** Every claim below is explicitly labeled **[CURRENT]** (true today, verified against real files) or **[TARGET — Phase N]** (planned, not yet built). This distinction is the whole point of the document — the previous submitted blueprint's biggest problem wasn't wrong ideas, it was stating target-state aspirations as if they were already running. Don't let that regress here.

---

## 0. Document History

- **v1.0 (2026-07-31, earlier same day):** First realignment pass. Audited the real codebase against a submitted blueprint that assumed a React/`@xyflow/react`/WebSocket/DPAPI/Vertex-AI stack. Found none of that exists; found instead a dormant, fully-built parallel Pydantic-contract architecture in `data_processing/` that was never wired into the live app.
- **v2.0 (this document):** Incorporates a phased implementation roadmap and gap-analysis framing developed from v1.0's findings. Corrects several specifics that regressed toward the original blueprint's inaccuracies during that pass: a fictional `main.py` entry point, adapter files shown as flat rather than in their real per-bridge subfolders, and `cortex_database.py` misidentified as the primary database interface when `database.py` is actually primary. Also makes explicit, throughout, which capabilities are current versus planned — several had drifted into present tense.

---

## 1. Executive Summary & Architectural Transition Analysis

**[CURRENT]** The operational core of Cortex — Python, FastAPI, Drawflow.js, `workflow_engine.py`, and subprocess-isolated execution — is functional, tested (100+ passing tests across the engine test suite), and structurally sound. It runs as a **local, single-user, desktop-hosted application** on `127.0.0.1:8080`, serving server-rendered Jinja2 pages to one signed-in Windows user.

**[CURRENT]** Authentication today is achieved almost entirely through **browser session automation** (Playwright drives a real signed-in Edge/Chrome profile for Gemini, Copilot, and NotebookLM) rather than API keys or MSAL tokens. This already satisfies the *intent* behind "delegated user scope, zero unauthorized egress" — every AI call happens through a session the signed-in user could just as easily drive by hand. M365 Graph is the one exception: it is **fully mocked today**, with no real Microsoft Graph HTTP call anywhere in the codebase yet.

This document's approach: rather than replacing working code with an unbuilt React/Vertex-AI stack, Cortex adopts the *standards* a more ambitious blueprint aspired to — strict schema validation, deterministic phase boundaries, secure identity management — **directly within the existing codebase**, using infrastructure that in several cases already exists half-built and unused (see §4).

### 1.1 Gap Analysis: Submitted Blueprint vs. Live Architecture

```
Submitted Blueprint (Aspirational Model)          Live Architecture (Verified Baseline)
─────────────────────────────────────────         ──────────────────────────────────────
• React + @xyflow/react + TypeScript              • FastAPI + Jinja2 + Drawflow.js  [CURRENT]
• WebSocket Live Stream Updates                   • Full-result POST /run, colored post-hoc  [CURRENT]
• DPAPI Windows Token Caching                     • No persisted tokens exist yet to encrypt  [CURRENT]
• Google Vertex AI / Enterprise GCP               • Gemini Web API via Playwright (gemini_webapi)  [CURRENT]
• modules/ + ui/ + workflows/ + main.py layout    • 00_System/10_Skills/.../14_Adapters  [CURRENT]
• (not named in submitted blueprint)              • A dormant, fully-built Pydantic contract +
                                                     license-gated execution engine already exists
                                                     in data_processing/, unconnected to the above
```

### 1.2 Core Re-Alignments

- **Directory hierarchy enforced [CURRENT]:** The five-tier convention (`00_System/`, `10_Skills/`, `11_Processes/`, `12_Tasks/`, `13_Functions/`, `14_Adapters/`) is CLAUDE.md's own mandate and is what the entire codebase already follows. No new top-level folders (`modules/`, `ui/`, `workflows/`, `config/`) are introduced.
- **"Function" is two distinct things [CURRENT]** — see §3.4. Any future audit needs to check both.
- **Path A / Path B reconciliation [TARGET — Phase 1, decision required]:** The dormant engine in `data_processing/` (`workflow_schema.py`'s `WorkflowPayload`, `auth.py`'s `EnterpriseAuthManager`) will be **repurposed to serve the live execution path** — supplying strict Pydantic validation at specific chokepoints and real MSAL identity for M365 — rather than continuing to exist as a disconnected exploration. This is a decision this document makes explicitly (§5), not a fact about today's code.

---

## 2. Core Architectural Principles

1. **Deterministic Phase Boundaries [CURRENT].** Workflows execute as stateless, single-HTTP-request DAG runs. `WorkflowEngine.run()` processes the full graph and returns; there is no polling loop, no multi-week waiting state. `MAX_TOTAL_STEPS=200` and per-gate `max_attempts` bound every run.
2. **Programmatic First, AI Supported [CURRENT].** Deterministic work (OpenXML parsing, Excel calculation, file I/O) runs through `python-docx`/`openpyxl`/`python-pptx`. Generative AI is reserved for cognitive tasks (synthesis, extraction, reasoning) — no AI bridge is ever asked to lay out a document.
3. **Strict 5-Tier Abstraction Hierarchy [CURRENT].** `00_System/`, `10_Skills/`, `11_Processes/`, `12_Tasks/`, `13_Functions/`, `14_Adapters/`.
4. **Transparent Visual Auditing [CURRENT, but post-hoc not live].** Every run colors node borders `IDLE`→`SUCCESS`(green)/`FAILED`(red) once the full run completes and the browser receives the response. There is no per-node "now executing" pulse today — see §3.2 for exactly what exists versus what a live-streaming version would need (§4.6).

---

## 3. The Real Architecture

### 3.1 Request/Execution Flow **[CURRENT]**

```
Browser (Jinja2 page + vanilla JS + Drawflow.js canvas)
        │  fetch() — full request/response, not a live socket
        ▼
FastAPI server.py  (00_System/server.py, ~1,700 lines, single process, uvicorn --reload)
        │
        ├── GET  /api/workflow-builder/node-registry   → palette contents (CoreRouter scan + static registries)
        ├── POST /api/workflow-builder/run             → WorkflowEngine(dry_run).run(graph_json)
        ├── POST /execute/{category}/{tool_id}          → CoreRouter.execute_app_logic() (ad-hoc single-tool run)
        └── CRUD  /api/workflow-builder/workflows/*     → SQLite workflow_definitions table (database.py)
        │
        ▼
workflow_engine.py :: WorkflowEngine.run(graph_json)
        │  Parses a raw Drawflow export, flattens plain Containers, extracts
        │  loop Containers into private sub-graphs, walks the graph with a
        │  queue + _pick_next scheduler, threading {{label}} token
        │  substitution and a global self.variables store between nodes.
        │  Every node's output is a plain string (Dict[str, str] context).
        ▼
core_router.py :: CoreRouter.execute_app_logic(category, tool_id, args)
        │  Launches the target Task/Process/Adapter .py file as an isolated
        │  SUBPROCESS (sys.executable + script path), captures stdout/stderr.
        ▼
12_Tasks/<tool>/<tool>.py   or   14_Adapters/<bridge>/<bridge>.py
        │  Each prints exactly one line of JSON: {"success": bool, ...}.
        │  AI bridges drive a real signed-in browser session via Playwright,
        │  or run in MOCK_MODE (env-var gated, per-adapter) otherwise.
```

No step of this validates a Pydantic schema between stages, uses a WebSocket, or touches DPAPI. This is the accurate, current picture.

### 3.2 Visual State Auditing — what exists vs. what live-streaming would need **[CURRENT / TARGET note]**

`workflow-builder.html`'s `wfbRun()` POSTs the whole graph, waits for the complete `{success, steps, responses, terminated}` response, then colors every node's border in one pass based on the full `steps` array. This is real and useful as an audit trail. It is not live: a multi-minute Gemini Deep Research call gives no incremental "still running" signal beyond the run staying pending. §4.6 covers what a real live-streaming version would take.

### 3.3 THE CENTRAL FINDING: Two Parallel, Disconnected Architectures **[CURRENT]**

`00_System/data_processing/` contains a **complete second execution architecture**, built during what its own file headers call "an early visual-canvas exploration," almost entirely disconnected from the live path in §3.1:

| File | What it is | Wired into the live app? |
|---|---|---|
| `workflow_schema.py` | `WorkflowPayload`/`WorkflowContext`/`FileReference`/`StepHistory` — a complete Pydantic contract envelope with `transition_to_next_step()` and `validate_capability_access()` | **No** — only `sandbox_smoke_test.py` exercises it |
| `canvas_schema.py` | `WorkflowCanvasGraph`/`CanvasNode`/`CanvasEdge` — an n8n-style visual graph model, explicitly documented in its own header as "NOT the same graph format the real, running Workflow Builder page actually uses" | **No** |
| `canvas_parser.py` | `VisualWorkflowExecutor` — walks a `WorkflowCanvasGraph`, calls `core_router.py`'s `CoreWorkflowRouter`, updates per-node `SUCCESS`/`FAILED`/`GREYED_OUT` | **No** |
| `core_router.py` :: `CoreWorkflowRouter` (a class distinct from `CoreRouter`) | In-process step executor over `WorkflowPayload`, with license-gated block execution | **No** — its own docstring says so |
| `observer_transformer.py` / `observer_schema.py` | Converts a `WorkflowPayload` into a fixed 6-stage pipeline dashboard view | **No** |
| `enterprise_adapters.py` | `M365OneDriveAdapter`/`GoogleDriveAdapter` — translates Graph/Drive responses into `FileReference` | **No** (calls a "currently simulated" Graph request) |
| `auth.py` | `EnterpriseAuthManager` — **a real, already-written MSAL client-credentials flow** for M365, plus a real Google service-account flow, both env-var gated with a `mock_sandbox_...` fallback | **No** — not imported by `m365_graph_bridge.py` at all |
| `theme_exporter.py` | A ShadCN-style color palette "for a future n8n-style visual canvas" | **No** — nothing imports it; the real UI has its own CSS-variable theme |
| `runtime_state.py` | Save/load a `WorkflowPayload` to/from a JSON snapshot for pause/resume | **No** |

**What this means:** strict Pydantic contracts and license-gated execution aren't capabilities that need to be built from scratch — **they already exist, fully written**, just never finished being wired into the page a real user opens. Most consequentially: `data_processing/auth.py`'s `EnterpriseAuthManager.get_m365_access_token()` is a genuine, real MSAL `ConfidentialClientApplication` client-credentials implementation, using exactly the env var names (`M365_CLIENT_ID`, `M365_TENANT_ID`, `M365_CLIENT_SECRET`) any fresh M365 integration effort would otherwise re-invent — sitting one `import` away from being called by `m365_graph_bridge.py`. (`msal` itself isn't in `requirements.txt` yet, so today this path always falls through to its mock token regardless of env vars.)

This dormant architecture is well-designed and, in places, more rigorous than the live path. Its **silent, undocumented, permanent coexistence** alongside the live system — never reconciled, no record anywhere of which one was "real" — is the concrete shape of the drift this whole audit exists to address. §5 resolves it explicitly.

### 3.4 Two different things are both called "Function" **[CURRENT]**

- **`13_Functions/`** (15 folders) — standalone Python scripts, auto-discovered by `CoreRouter`, dispatched via subprocess exactly like a Task or Process.
- **Built-in `Function` nodes inside `workflow_engine.py`** (~35 `tool_id`s, e.g. `function_compose`, `function_filter_array`, `function_initialize_variable`) — pure in-process if/elif branches in `_execute_function_node`, registered in `server.py`'s `FUNCTIONS_REGISTRY`, with config-panel schemas in `workflow-builder.html`. No folder of their own — they exist only as code and dictionary entries.

### 3.5 Tier-by-Tier Current Inventory **[CURRENT]**

**11_Processes (8):** `generate_vault_map`, `list_copilot_agents`, `list_gems`, `list_m365_teams`, `list_onenote_notebooks`, `list_powerbi_reports`, `list_recent_onedrive_files`, `list_sharepoint_sites`.

**12_Tasks (56):** AI interaction (9: `ask_chatgpt`, `ask_claude`, `ask_copilot`, `ask_copilot_agent`, `ask_gemini`, `ask_gemini_gem`, `generate_copilot_image`, `generate_gemini_image`, `format_text_with_copilot`), AI capability actions (12: `summarize_text`, `sentiment_analysis`, `language_detection`, `text_translation`, `key_phrase_extraction`, `entity_extraction`, `category_classification`, `form_invoice_processing`, `business_card_id_reader`, `object_detection_ocr`, `image_description`, `predict`), M365/Graph (14), NotebookLM (3), document processing (4), data import/analysis (4), utility (3).

**13_Functions (15 folder scripts):** file format conversion (7), document processing (4), data transformation (3), workflow control (1: `human_review_checkpoint`).

**Built-in Function nodes (~35, inside `workflow_engine.py`):** flow control (`logic_gate`, `conditions`, `terminate`, `response`, `http`, `parse_json`, `compose`), variables (`initialize_variable`, `set_variable`, `increment_variable`, `append_variable`), loops (`kind: "container"` + `params.loop_type`, not a `function_` tool_id), array/data ops (`filter_array`, `select`, `join`, `sort`, `union`, `chunk`, `length`, `first`, `last`, `take`, `skip`, `create_csv_table`, `create_html_table`), AI prompt shortcuts (`google_search`, `gemini_ask`, `claude_ask`, `chatgpt_ask`, `image_generate`), NotebookLM (3), delay (`delay`, `delay_until`), plus `concatenate` and `builtin_review_gate`.

**14_Adapters (7 bridge folders + 1 standalone file):**

| Adapter (folder) | Real mechanism | Status |
|---|---|---|
| `gemini_bridge/gemini_bridge.py` | Playwright captures signed-in Gemini cookies once; `gemini_webapi` talks to Google directly afterward. Supports multimodal (`files=[...]`) and Gems | **Real**, working today |
| `copilot_bridge/copilot_bridge.py` | Full Playwright automation per call | **Real**, working today |
| `notebooklm_bridge/notebooklm_bridge.py` | Playwright automation | **Real**, working today |
| `m365_graph_bridge/m365_graph_bridge.py` | Every function raises `NOT_CONFIGURED_MESSAGE` unless `M365_MOCK_MODE=0` — and even then, no real Graph HTTP call exists in the file | **Mock only** — §4.2 is the fix |
| `claude_bridge/claude_bridge.py`, `chatgpt_bridge/chatgpt_bridge.py` | Mock, awaiting API keys | Mock |
| `airgap_adapter.py` (standalone file, not a folder) | Local offline fallback | Real (limited scope) |

---

## 4. Technical Challenges & Mitigation Strategies

| Technical Challenge | Current Risk / Impact **[CURRENT]** | Architectural Mitigation Strategy **[TARGET]** |
|---|---|---|
| **Data Contract Drift** | The live engine uses untyped string context (`Dict[str, str]`); several Function nodes already defensively `try/except json.loads(...)` for exactly this reason. | **Targeted Pydantic adapters** on JSON-producing nodes only (`function_parse_json`, `entity_extraction`, `key_phrase_extraction`, `form_invoice_processing`) — fail loud at the point of production. Not a full engine migration; see §4.4 for why. |
| **M365 Integration Gap** | `m365_graph_bridge.py` raises `NOT_CONFIGURED_MESSAGE` unconditionally; no real Graph REST call exists anywhere in the file. | Add `msal` to `requirements.txt`; wire `m365_graph_bridge.py` directly to the already-written `EnterpriseAuthManager` in `data_processing/auth.py`. See §4.2. |
| **Long-Running Task Auditing** | Node status updates are post-hoc (§3.2) — no feedback *during* a multi-minute AI call beyond the run staying pending. | One additive WebSocket route in `server.py`, fed by a callback `WorkflowEngine.run()` already has a natural hook point for (right after each `self.log.append(...)`). No UI canvas rewrite needed. See §4.6. |
| **Credential Security** | No tokens are persisted anywhere yet — this risk doesn't exist today, but will the moment §4.2 ships and a real access token needs to survive a process restart. | DPAPI (`win32crypt`) wrapper around the token-cache table, added when — not before — §4.2 produces a real token worth protecting. See §4.1. |

---

## 5. Path A / Path B Reconciliation — The Decision

This is the concrete answer to "how do we stop this from sliding into chaos," made explicit rather than left ambiguous:

- **`data_processing/workflow_schema.py`, `enterprise_adapters.py`, `auth.py`, and `user_identity.py` are retained and will be actively wired into the live path** — `auth.py` into `m365_graph_bridge.py` (§4.2), `workflow_schema.py`'s validation pattern into targeted JSON-producing nodes (§4.4). These four files are genuinely useful and stop being dormant under this plan.
- **`canvas_schema.py`, `canvas_parser.py`, `observer_transformer.py`, `observer_schema.py`, `theme_exporter.py`, and `runtime_state.py` are archived**, not deleted outright — move them under `data_processing/_archive_canvas_exploration/` with a short `README.md` explaining they were an early visual-canvas exploration superseded by the live Drawflow-based Workflow Builder, so nothing new gets built assuming they're live infrastructure. `sandbox_smoke_test.py` should be trimmed to stop exercising the archived modules once this move happens.
- This decision is final for planning purposes as of this document. Revisiting it requires a real, named reason (e.g., a concrete need for a second visual canvas), not silent re-accumulation.

---

## 6. Strategic Opportunities

1. **Leveraging pre-built infrastructure.** `data_processing/auth.py` already contains a working MSAL `ConfidentialClientApplication` flow. Activating it accelerates real M365 Graph integration (SharePoint, OneDrive, Teams, Outlook) without inventing new auth architecture.
2. **Headless, deterministic AI workflows.** Local OpenXML compilers (`python-docx`, `openpyxl`) handle formatting; Gemini/Copilot handle text generation. This split (already the current design, §2.2) guarantees brand-standard output and keeps AI token costs down — worth explicitly preserving as new capabilities are added, not just stated once.
3. **Controlled capability expansion.** A Feature Request module (`12_Tasks/submit_feature_request.py` + a SQLite backlog table) gives ungoverned growth a formal escape valve: a new capability gets logged and reviewed against this document before code gets written, rather than appearing as an unplanned addition. See §4.5.

---

## 7. Gap Analysis Detail — Evaluating Each Capability On Its Own Merits

### 4.1 DPAPI-encrypted credential storage **[TARGET — Phase 2, sequenced after 4.2]**

**Merit:** Real, but only once there's something to encrypt. Today zero enterprise tokens are persisted anywhere (Playwright keeps its own OS-permission-protected browser profile cookies; nothing else writes a token to disk).
**Plan:** Once §4.2 produces a real access token worth surviving a process restart, wrap its cache table (in `database.py`, not `cortex_database.py` — see §9's directory correction) with `win32crypt.CryptProtectData`/`CryptUnprotectData`. Add `pywin32` to `requirements.txt` (not there today).
**Recommendation:** Defer until §4.2 ships. Building the encryption wrapper before there's a real token to protect is exactly the speculative work this audit exists to prevent.

### 4.2 M365 real wiring (MSAL) **[TARGET — Phase 1]**

**Merit:** High — already scoped as the next major slice, and this audit found the auth code already half-written.
**Exists already:** `EnterpriseAuthManager.get_m365_access_token()` in `data_processing/auth.py` — real MSAL client-credentials flow, env-var gated, mock-fallback.
**Missing:** `msal` isn't in `requirements.txt` (silently falls back to mock even with real env vars); `m365_graph_bridge.py` doesn't import `EnterpriseAuthManager` at all, and has no real `requests.get("https://graph.microsoft.com/...")` call anywhere.
**Plan:** (1) add `msal` to `requirements.txt`; (2) wire `m365_graph_bridge.py` to call `EnterpriseAuthManager.get_m365_access_token({})` and use the bearer token in real Graph REST calls, per existing function (`list_files`, `send_mail`, etc.), reusing the same request pattern already proven for the `function_http` Function node; (3) only after live against a real tenant, revisit client-credentials (app-only) vs. a true per-user delegated flow. This is wiring, not new architecture.

### 4.3 Enterprise GCP Vertex AI **[Not recommended unless a real use case names it]**

**Merit:** Low as a replacement for the working, free `gemini_bridge`. Vertex AI is a different product entirely — paid, project-scoped, different SDK/auth/quota model.
**When it's worth it:** A genuine need for a persistent RAG corpus over a document set, or a data-residency requirement a personal Gemini account can't meet. Neither is true today.
**Recommendation:** If ever needed, build as a new `14_Adapters/vertex_ai_bridge/`, alongside — not replacing — `gemini_bridge`.

### 4.4 Strict Pydantic contracts on the live path **[TARGET — Phase 2, incremental only]**

**Merit:** High in principle; `workflow_schema.py` already demonstrates what "done" looks like structurally. The cost of a full migration is real: `workflow_engine.py`'s `Dict[str, str]` context is asserted on directly by 100+ existing tests.
**Recommendation:** Don't migrate the engine. Apply the *pattern* only at JSON-producing nodes (`function_parse_json`, `entity_extraction`, `key_phrase_extraction`, `form_invoice_processing`) — validate before returning, raise `WorkflowRunError` on mismatch. Real safety benefit, zero engine-core risk.

### 4.5 Feature Request Module **[TARGET — Phase 3]**

**Merit:** Directly addresses the governance concern this whole audit was commissioned to solve. Cheap to build.
**Plan:** `12_Tasks/submit_feature_request.py` (needs input, so a Task not a Process) appends `{title, description, requested_capability, submitted_by, timestamp, status: "proposed"}` to a new table in `database.py` (the primary DB — see §9), plus a list/vote page mirroring the existing Tag Registry page.

### 4.6 WebSocket live node-state streaming **[TARGET — Phase 3]**

**Merit:** Moderate — the real gap is only *during*-run feedback for long AI calls, not the audit trail itself (already complete, §3.2).
**Plan:** `websockets` is already in `requirements.txt` (currently an unused transitive uvicorn dependency). Add one `@app.websocket("/ws/workflow-run/{run_id}")` route; give `WorkflowEngine.run()` an optional per-step callback (a small, additive change at the exact point it already does `self.log.append(...)`) that pushes over the socket. No canvas rewrite.

---

## 8. Recommended Implementation Sequence

```text
 PHASE 1: Consolidation & Auth      PHASE 2: Validation & Guardrails    PHASE 3: UI & Feature Expansion
┌─────────────────────────────────┐ ┌─────────────────────────────────┐ ┌─────────────────────────────────┐
│ 1. Archive Path B canvas files  │ │ 3. Targeted Pydantic checks on  │ │ 5. Feature Request Task +       │
│    (§5) with a README pointer.  │ │    JSON-producing nodes only    │ │    backlog table + list page.   │
│ 2. Add 'msal' dependency; wire  │ │    (§4.4) — no engine rewrite.  │ │ 6. WebSocket live step          │
│    EnterpriseAuthManager into   │ │ 4. DPAPI-wrap the real M365     │ │    streaming (§4.6).            │
│    m365_graph_bridge.py (§4.2). │ │    token cache (§4.1).          │ │ 7. Google Workspace real wiring │
└─────────────────────────────────┘ └─────────────────────────────────┘ │    (same shape as Phase 1).     │
                                                                          └─────────────────────────────────┘
                                                                          Vertex AI (§4.3): only if a real
                                                                          RAG/data-residency need arises.
```

Each phase is a real prerequisite for the next: Phase 1's decision changes what "done" means for Phase 2's validation work; Phase 2's real token is what makes Phase 1's DPAPI wrapper meaningful rather than speculative.

---

## 9. Corrected System Directory Layout

```text
Cortex/
├── .claude/                             # Claude Code's OWN tooling for this dev environment — not Cortex app code
│   ├── settings.local.json
│   └── skills/                          # Installed Claude Code plugin skills (gstack, cso, etc.) — unrelated to Cortex's architecture
├── 00_System/                           # Core engine — server, router, engine, database, core logic. Nothing core lives outside this folder.
│   ├── server.py                        # FastAPI app + all routes (~1,700 lines). THE application entry point — there is no main.py.
│   ├── workflow_engine.py               # WorkflowEngine — the real DAG walker (loops, variables, flow control)
│   ├── core_router.py                   # CoreRouter (live subprocess dispatch) + CoreWorkflowRouter (dormant Path B class, §3.3)
│   ├── database.py                      # PRIMARY database interface — brain_state.db — workflow_definitions, contacts, everything else
│   ├── cortex_database.py               # SECONDARY, deliberately separate — cortex_scrape.db, web-scrape data only
│   ├── model_classifications.py         # AI model → data-classification-level mapping
│   ├── logger.py / health.py            # health.py is invoked directly by an external Dockerfile — never move it
│   ├── tests/                           # All 00_System-level tests (moved here 2026-07-31)
│   ├── data_processing/                 # See §3.3 — real utilities (user_identity, enterprise_adapters, auth, workflow_schema) + archived exploration (§5)
│   └── templates/                       # Jinja2 pages, static assets, Drawflow.js, vendored Font Awesome
├── 10_Skills/                           # Empty today — real skill registry is server.py's SKILLS_REGISTRY
├── 11_Processes/                        # 8 zero-input Processes
├── 12_Tasks/                            # 56 configurable Tasks
├── 13_Functions/                        # 15 standalone Function scripts (distinct from workflow_engine.py's ~35 built-in Function nodes, §3.4)
├── 14_Adapters/                         # 7 bridge SUBFOLDERS (gemini_bridge/gemini_bridge.py, not a flat .py file) + airgap_adapter.py standalone
├── 01_inbox/ 02_vault/ 99_Outbox/       # File staging/storage
├── docs/superpowers/{specs,plans}/      # Design-doc-before-code convention — every new capability gets one of these before code
└── CLAUDE.md                            # Project instructions — the checked-in source of truth for conventions
```

---

## 10. Core Engine Functional Specifications **[CURRENT — describes what runs today]**

### 10.1 Task Dispatch Router (`00_System/core_router.py` :: `CoreRouter`)
- Subprocess isolation: every Task/Process/Adapter runs as its own `sys.executable` subprocess — a crash or hang can't take down the server, and it's immune to the dev server's own file-watch auto-reload mid-run.
- Captures combined `stdout`+`stderr`; every script is expected to print exactly one line of JSON (`{"success": bool, ...}`).
- Non-zero exit codes and malformed output are caught and surfaced as a failed step to `workflow_engine.py`, not a crash.

### 10.2 Execution Engine (`00_System/workflow_engine.py` :: `WorkflowEngine`)
- Parses raw Drawflow JSON, flattens plain Containers, extracts loop Containers (`params.loop_type`) into private sub-graphs re-run once per array item or until a condition holds.
- `self.variables: Dict[str, Any]` — a named, global (not connection-scoped) variable store, addressed via `{{var.name}}` tokens, distinct from the connection-scoped `{{label}}` system.
- ~35 built-in Function nodes dispatch in-process (no subprocess) via a single large if/elif ladder — this is deliberate for the ones with no external dependency (string/array ops, flow control), not an oversight.

### 10.3 Authentication Provider (`00_System/data_processing/auth.py` :: `EnterpriseAuthManager`) — **[TARGET once wired per §4.2; the code itself already exists today]**
- `get_m365_access_token()`: MSAL `ConfidentialClientApplication` client-credentials flow against `M365_CLIENT_ID`/`M365_TENANT_ID`/`M365_CLIENT_SECRET`, falling back to a `mock_sandbox_...`-prefixed token when unconfigured or `msal` isn't installed.
- `get_google_access_token()`: `google.oauth2.service_account` flow against `GOOGLE_SERVICE_ACCOUNT_JSON`, same mock-fallback convention. (`google-auth` — which provides this submodule — is already installed; `msal` is not.)
- **Not yet called by anything in the live path** — see §3.3 and §4.2 for the wiring plan.

---

## 11. Operational Security & Guardrails

1. **Strict local execution [CURRENT].** FastAPI binds to `127.0.0.1:8080` only; no external network interface is exposed.
2. **Encrypted token caching [TARGET — Phase 2, §4.1].** Once real tokens exist to persist, they must be DPAPI-wrapped (`win32crypt`) before being written to `database.py`'s cache table. Not applicable today — nothing is persisted yet.
3. **Data boundary protection [CURRENT for browser-automation bridges; TARGET for M365].** No document content or prompt payload may reach a non-enterprise endpoint. Already true for Gemini/Copilot/NotebookLM (the user's own signed-in session is the only channel). Becomes true for M365 the moment §4.2 routes exclusively through the organization's own Entra ID tenant.
4. **Managed Feature Request pipeline [TARGET — Phase 3, §4.5].** New capability blocks must be logged via `12_Tasks/submit_feature_request.py` and reviewed against this document before implementation, once that Task exists.
5. **Before adding any new folder, dependency, or parallel data model [CURRENT — process guardrail, effective immediately]:** ask (a) does something like this already exist, dormant, in `data_processing/`? (b) will this be wired into the live path or will it sit unused? (c) does it fit the five-tier convention? — and write a spec under `docs/superpowers/specs/` before writing code, per the convention already working well through this project's recent history.

---

## Appendix A: Disposition of Prior Documents

- **`CORTEX_FUNCTIONAL_STATUS_REPORT.md`** (2025-07-29, untracked): stale tool counts (35 Tasks vs. the current 56, no `tests/` folder), but its live-path architectural description was accurate at the time. Recommend deleting or archiving under `docs/` — not done automatically, since this document didn't originate that file and shouldn't unilaterally remove it.
- **v1.0 of this document:** superseded in full by this v2.0. No action needed — git history retains it.

## Appendix B: Path B Files — Final Disposition (§5)

**Retained, to be actively wired in:** `data_processing/workflow_schema.py`, `enterprise_adapters.py`, `auth.py`, `user_identity.py`.
**Archived under `data_processing/_archive_canvas_exploration/`:** `canvas_schema.py`, `canvas_parser.py`, `observer_transformer.py`, `observer_schema.py`, `theme_exporter.py`, `runtime_state.py`. `sandbox_smoke_test.py` to be trimmed to stop exercising the archived set once the move happens.
