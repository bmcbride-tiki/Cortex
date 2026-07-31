# CORTEX Architecture Blueprint — Realigned Edition

> **Document Version:** 1.0 (Realigned)
> **Date:** 2026-07-31
> **Supersedes:** `CORTEX_FUNCTIONAL_STATUS_REPORT.md` (dated 2025-07-29, now stale — see Appendix A)
> **Status:** This is the authoritative architecture reference for Cortex going forward. Read this before adding any new capability, folder, or dependency. Its purpose is exactly what prompted it: **stop architectural drift** by giving every future session (human or AI) one accurate picture of what exists, what's dormant, and what's actually worth building next.

---

## 0. Why This Document Exists

A detailed blueprint was proposed as a target architecture for Cortex — React/`@xyflow/react` frontend, a `modules/`/`ui/`/`workflows/` directory layout, MSAL + DPAPI-encrypted credential storage, WebSocket live node streaming, enterprise GCP Vertex AI as the AI backend. That document does not describe Cortex as it exists. It describes a plausible enterprise automation platform in the abstract, but several of its foundational claims (directory structure, which file does what, which auth libraries are wired up) don't match a single file in this repository.

Running an "alignment pass" against that document literally would have meant discarding a large amount of real, tested, working code — including everything built in the sessions immediately preceding this one (the entire flow-control/variable/loop engine, twelve AI capability Tasks, the Gems connector) — in favor of a rewrite to a stack (React, TypeScript build tooling, Vertex AI enterprise billing) that doesn't exist here and wasn't asked for by name until this document.

Rather than execute that, this document does what was actually asked: **take the blueprint's underlying intent seriously — strict contracts, deterministic execution, visual auditing, security guardrails, a disciplined building-block hierarchy — and re-ground every section in Cortex's real files.** Section 3 below covers reconciliation of the submitted blueprint section-by-section. Section 4 evaluates which of its aspirational capabilities are worth building and how, given what already exists. Section 5 is the guardrails section — the actual answer to "how do we stop this from sliding into chaos."

**The single most important finding in this whole audit is in Section 2.3.** Read that section before anything else.

---

## 1. Executive Summary — What Cortex Actually Is Today

Cortex is a **local, single-user, desktop-hosted FastAPI application** (not a client/server enterprise deployment) that runs on `127.0.0.1:8080`, serves server-rendered Jinja2 HTML pages, and lets one signed-in Windows user build and run visual automation workflows against a five-tier library of Python building blocks. It talks to Microsoft 365 and Google services almost entirely via **browser automation** (Playwright driving a real signed-in Edge/Chrome session) rather than API keys or enterprise service principals — this is a deliberate, working design choice, not a placeholder, for every AI bridge except the M365 Graph/Power BI file and data operations, which are genuinely still mocked pending a real Azure AD app registration.

There is no React, no TypeScript, no `@xyflow/react`, no WebSocket push, no DPAPI, no Vertex AI, and no `modules/`/`ui/`/`workflows/` directory anywhere in this codebase. There is a Drawflow.js canvas, a `workflow_engine.py` DAG walker with 100+ passing tests, and a five-tier folder convention (`00_System/`, `10_Skills/`, `11_Processes/`, `12_Tasks/`, `13_Functions/`, `14_Adapters/`) that CLAUDE.md itself mandates and that the entire codebase already follows.

**Current scale** (verified by direct folder count, 2026-07-31):

| Tier | Folder | Count | Notes |
|---|---|---|---|
| System core | `00_System/` | 8 core files + `data_processing/` (11 modules) + `tests/` (6 files) | server, database (×2), engine, router, logger, health, classifications |
| Skills | `10_Skills/` | 0 | Empty — hand-written registry in `server.py` (`SKILLS_REGISTRY`) stands in for it today |
| Processes | `11_Processes/` | 8 | Zero-input, click-and-run discovery Tasks |
| Tasks | `12_Tasks/` | 56 | Configurable, parameterized automation units |
| Functions | `13_Functions/` | 15 (folder scripts) + ~35 (built-in `Function` nodes inside `workflow_engine.py`) | Two distinct meanings of "Function" — see §2.4 |
| Adapters | `14_Adapters/` | 7 bridges + 1 standalone (`airgap_adapter.py`) | 5 real (browser automation), 2 mock (Claude/ChatGPT, awaiting API keys), M365 Graph mock pending Azure AD app |

---

## 2. The Real Architecture

### 2.1 Request/Execution Flow (as it actually runs)

```
Browser (Jinja2 page + vanilla JS + Drawflow.js canvas)
        │  fetch() — NOT WebSocket
        ▼
FastAPI server.py  (00_System/server.py, ~1,700 lines, single process, uvicorn --reload)
        │
        ├── GET  /api/workflow-builder/node-registry   → palette contents (CoreRouter scan + static registries)
        ├── POST /api/workflow-builder/run             → WorkflowEngine(dry_run).run(graph_json)
        ├── POST /execute/{category}/{tool_id}          → CoreRouter.execute_app_logic() (ad-hoc single-tool run)
        └── CRUD  /api/workflow-builder/workflows/*     → SQLite workflow_definitions table
        │
        ▼
workflow_engine.py :: WorkflowEngine.run(graph_json)
        │  Parses a raw Drawflow export (nodes + connections), flattens plain
        │  Containers, extracts loop Containers into private sub-graphs,
        │  walks the graph with a queue + _pick_next scheduler, threading
        │  {{label}} token substitution and a global self.variables store
        │  between nodes. Every node's output is a plain string.
        ▼
core_router.py :: CoreRouter.execute_app_logic(category, tool_id, args)
        │  Launches the target Task/Process/Adapter .py file as an
        │  ISOLATED SUBPROCESS (sys.executable + the script path), captures
        │  stdout/stderr, returns (success, combined_output_text).
        ▼
12_Tasks/<tool>/<tool>.py  or  14_Adapters/<bridge>/<bridge>.py
        │  Each prints exactly one line of JSON: {"success": bool, ...}.
        │  AI bridges (gemini/copilot/claude/chatgpt/notebooklm) drive a
        │  real signed-in browser session via Playwright, OR run in
        │  MOCK_MODE (env-var gated, per-adapter) when no session/API key
        │  exists yet.
```

No step of this uses Pydantic validation between stages, no step uses WebSockets, and no step uses DPAPI. That is the accurate picture of the live system as of this document.

### 2.2 What "visual state auditing" actually looks like today

The blueprint's Section 5 describes live WebSocket-driven node border colors (neutral → pulsing blue → green/red). The real implementation (`workflow-builder.html`'s `wfbRun()`) is **post-hoc, not live**: the browser POSTs the whole graph to `/api/workflow-builder/run`, waits for the complete response, then colors every node's border based on the full `steps` array that comes back all at once. There is no per-node "now executing" pulse — a node either hasn't run yet, or the whole run has already finished and it's green/red. This is a real, working, useful audit trail; it is not what the blueprint describes.

### 2.3 THE CENTRAL FINDING: Cortex has two parallel, disconnected architectures

This is the most important thing in this document. `00_System/data_processing/` contains a **complete second execution architecture** that was built during what its own file headers call "an early visual-canvas exploration," and it is almost entirely disconnected from the live application described in §2.1:

| File | What it is | Wired into the live app? |
|---|---|---|
| `workflow_schema.py` | `WorkflowPayload`/`WorkflowContext`/`FileReference`/`StepHistory` — a full Pydantic contract envelope, with `transition_to_next_step()` and `validate_capability_access()` | **No.** Only `sandbox_smoke_test.py` exercises it. |
| `canvas_schema.py` | `WorkflowCanvasGraph`/`CanvasNode`/`CanvasEdge` — an n8n-style visual graph model, explicitly documented as "NOT the same graph format the real, running Workflow Builder page actually uses" | **No.** |
| `canvas_parser.py` | `VisualWorkflowExecutor` — walks a `WorkflowCanvasGraph`, calls `core_router.py`'s `CoreWorkflowRouter`, updates per-node `SUCCESS`/`FAILED`/`GREYED_OUT` status | **No.** |
| `core_router.py` :: `CoreWorkflowRouter` (class, distinct from `CoreRouter`) | In-process step executor over `WorkflowPayload`, with license-gated block execution | **No** — its own docstring says so explicitly. |
| `observer_transformer.py` / `observer_schema.py` | Converts a `WorkflowPayload` into a fixed 6-stage pipeline dashboard view | **No.** |
| `enterprise_adapters.py` | `M365OneDriveAdapter`/`GoogleDriveAdapter` — translates Graph/Drive API responses into `FileReference` | **No** (calls a "currently simulated" Graph request). |
| `auth.py` | `EnterpriseAuthManager` — **a real, already-written MSAL client-credentials flow** for M365, and a real Google service-account flow, both env-var gated with a `mock_sandbox_...` fallback | **No** — not imported by `m365_graph_bridge.py` at all. |
| `theme_exporter.py` | A ShadCN-style color token palette "for a future n8n-style visual canvas" | **No** — the real UI has its own separate CSS variable theme. Nothing imports this file. |
| `runtime_state.py` | Save/load a `WorkflowPayload` to/from a JSON snapshot for pause/resume | **No.** |

**What this means:** the blueprint's Section 8/9 vision — strict Pydantic contracts, license-gated execution, a documented `WorkflowContext` — isn't something that needs to be built. **It already exists, fully written, in `data_processing/`.** It was simply never finished being wired into the page a real user actually opens. Worse: `data_processing/auth.py`'s `EnterpriseAuthManager.get_m365_access_token()` is a genuine, real MSAL `ConfidentialClientApplication` client-credentials implementation using exactly the env var names (`M365_CLIENT_ID`, `M365_TENANT_ID`, `M365_CLIENT_SECRET`) that any future "wire M365 up for real" effort would otherwise re-invent from scratch — and it's sitting completely unused, one `import` away from being called by `m365_graph_bridge.py`. (`msal` itself isn't in `requirements.txt` yet, so today this path always falls through to its mock token regardless of env vars — an easy, cheap fix, see §4.2.)

This dormant architecture is not necessarily bad — it's well-designed, well-documented, and genuinely more rigorous than the live path in several ways (typed contracts, license gating baked into the payload itself). But **its silent, permanent coexistence alongside the live system, never reconciled, is exactly the kind of drift that makes a codebase feel like it's sliding into chaos** — two ways to represent a workflow, two ways to run a step, two auth strategies, and no document until now saying which one is real. §5 makes a concrete recommendation on what to do about it.

### 2.4 Two different things are both called "Function"

The blueprint's 5-tier model (§3 of the submitted document) names "Function" as the bottom, atomic-script tier. Cortex actually has two distinct concepts sharing that name, and any future work needs to keep them straight:

- **`13_Functions/`** (15 folders) — real, standalone Python scripts (`export_to_word`, `human_review_checkpoint`, `web_scrape`, etc.), auto-discovered by `CoreRouter` exactly like a Task or Process, dispatched via subprocess.
- **Built-in `Function` nodes inside `workflow_engine.py`** (33 `tool_id`s, e.g. `function_compose`, `function_filter_array`, `function_initialize_variable`, `function_terminate`) — pure in-process Python branches in one large if/elif ladder (`_execute_function_node`), registered in `server.py`'s `FUNCTIONS_REGISTRY`, with their own config-panel schema in `workflow-builder.html`. These have no folder of their own at all — they only exist as code inside `workflow_engine.py` and dictionary entries in `server.py`.

Both are real, both are "Function" in conversation, and this document is the first place that distinction is written down. Any future skill/task/function audit needs to check both.

### 2.5 Tier-by-tier current inventory

**11_Processes (8, zero-input discovery):** `generate_vault_map`, `list_copilot_agents`, `list_gems`, `list_m365_teams`, `list_onenote_notebooks`, `list_powerbi_reports`, `list_recent_onedrive_files`, `list_sharepoint_sites`.

**12_Tasks (56):** AI interaction (`ask_chatgpt`, `ask_claude`, `ask_copilot`, `ask_copilot_agent`, `ask_gemini`, `ask_gemini_gem`, `generate_copilot_image`, `generate_gemini_image`, `format_text_with_copilot`), AI capability actions added this cycle (`summarize_text`, `sentiment_analysis`, `language_detection`, `text_translation`, `key_phrase_extraction`, `entity_extraction`, `category_classification`, `form_invoice_processing`, `business_card_id_reader`, `object_detection_ocr`, `image_description`, `predict`), M365/Graph (14 tasks — Outlook, Teams, SharePoint, OneNote, OneDrive, Excel, Power BI), NotebookLM (3), document processing (4), data import/analysis (4), utility (3: `abc_uploader`, `refresh_powerbi_dataset`, `search_outlook_email`).

**13_Functions (15 folder scripts):** file format conversion (7: import/export ×3 formats + markdown), document processing (4: templates, PowerPoint), data transformation (3), workflow control (1: `human_review_checkpoint`).

**Built-in Function nodes (33, inside `workflow_engine.py`):** flow control (`logic_gate`, `conditions`, `terminate`, `response`, `http`, `parse_json`, `compose`), variables (`initialize_variable`, `set_variable`, `increment_variable`, `append_variable`), loops (handled via `kind: "container"` + `params.loop_type`, not a `function_` tool_id), array/data ops (`filter_array`, `select`, `join`, `sort`, `union`, `chunk`, `length`, `first`, `last`, `take`, `skip`, `create_csv_table`, `create_html_table`), AI prompt shortcuts (`google_search`, `gemini_ask`, `claude_ask`, `chatgpt_ask`, `image_generate`), NotebookLM (`notebooklm_create`, `notebooklm_upload_sources`, `notebooklm_prompt_loop`), delay (`delay`, `delay_until`), plus `concatenate` and `builtin_review_gate`.

**14_Adapters (7 bridges + 1 standalone):**

| Adapter | Real mechanism | Status |
|---|---|---|
| `gemini_bridge` | Playwright captures signed-in Gemini session cookies once; `gemini_webapi` talks to Google directly afterward. Supports multimodal (`files=[...]`) and Gems (`fetch_gems`/`generate_content(gem=...)`) | **Real**, working today |
| `copilot_bridge` | Full Playwright browser automation per call (no cookie-caching shortcut) | **Real**, working today |
| `notebooklm_bridge` | Playwright browser automation | **Real**, working today |
| `m365_graph_bridge` | Every function raises `NOT_CONFIGURED_MESSAGE` unless `M365_MOCK_MODE=0` — and even then, there's no real Graph HTTP call anywhere in the file | **Mock only** — see §4.2 for the real fix |
| `claude_bridge` / `chatgpt_bridge` | Mock, awaiting `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` | Mock |
| `airgap_adapter.py` | Local offline fallback | Real (limited scope) |

---

## 3. Section-by-Section Reconciliation of the Submitted Blueprint

### §1 Executive Summary / Core Intent
**Submitted:** Delegated User Scope, DPAPI-bound tokens, zero unauthorized egress, M365 + Google Enterprise.
**Reality:** The *intent* (single signed-in user, no service principals, no data egress outside what the user's own session can already reach) is already true today — it's just achieved via browser-session automation and per-adapter `MOCK_MODE` flags, not MSAL delegated tokens or DPAPI. No token is stored anywhere yet, encrypted or not, except Playwright's own browser profile cookie jars (`*_browser_profile/` folders next to each bridge).
**Corrected framing:** "Cortex runs as the signed-in Windows user by construction, because every AI/enterprise call is either a browser automation session using that user's own login, or (for M365 Graph, not yet live) will use MSAL delegated auth. There is no service-principal or app-only path anywhere in the design." DPAPI is a real, worthwhile future addition (§4.1) but nothing today writes plaintext secrets to disk to protect against, since there ARE no persisted enterprise tokens yet.

### §2 Core Architectural Principles
**Deterministic phase boundaries:** Accurate today. `WorkflowEngine.run()` is a single, complete, non-polling execution per HTTP request; `MAX_TOTAL_STEPS=200` and per-gate `max_attempts` bound every run.
**Delegated authority:** Aspirational for M365 (see §4.2); already true for every browser-automation bridge.
**Programmatic first, AI supported:** Accurately describes the real system — `python-docx`/`openpyxl`/`python-pptx` do every layout/formatting job; AI bridges are only ever asked for text/reasoning/generation, never asked to lay out a document.
**Transparent visual auditing:** True in spirit, false in mechanism — see §2.2. No WebSockets exist.

### §3 The 5-Tier Building Block Architecture
Real, and already the load-bearing convention (CLAUDE.md mandates it, every folder follows it). The one correction: **"Function" is two things, not one** (§2.4). "Skill" is currently a hand-maintained Python list (`SKILLS_REGISTRY` in `server.py`), not `SKILL.md` files — `10_Skills/` is empty. "Adapter" in the submitted blueprint means a Pydantic schema-transform layer; in the real system it means a third-party bridge script (`14_Adapters/`). The Pydantic-schema-transform meaning does exist, just under a different name and location: `data_processing/enterprise_adapters.py` and the whole `workflow_schema.py` contract (§2.3).

### §4 Reference Workflow (Curriculum-to-Exam Pipeline)
This describes a real business process Cortex already automates (`curriculum_guide_to_tos`, `word_to_excel_exam` Tasks exist), but the pipeline mechanics described (`modules/m365/word_engine.py`, a GCP Vertex AI RAG corpus push) don't match any real file. The equivalent real files are `13_Functions/populate_word_template_from_json`, `13_Functions/fill_docx_template`, and `12_Tasks/curriculum_guide_to_tos`/`word_to_excel_exam` — programmatic `python-docx`/`openpyxl`, no Vertex AI, no RAG corpus, question generation would go through `ask_gemini`/`ask_gemini_gem` today, not a dedicated Vertex AI Search corpus.

### §5 UI/UX Architecture
Real component: Drawflow.js canvas in `workflow-builder.html`, a run log terminal (`#wfb-run-log`), post-hoc node border coloring. Not real: React, `@xyflow/react`, live WebSocket pulsing during execution, a separate "Linear Step List" view toggle (the real page has one canvas view only — the Workflow *Map* page, a different route, offers a read-only stage-column view of a saved workflow, not a live toggle on the builder itself).

### §6 Development & System Guardrails
**Guardrail 1 (zero egress):** Same correction as §1 above — true by construction today via browser sessions, not yet true via a governed MSAL/Graph tenant boundary for M365 (because M365 isn't live yet at all).
**Guardrail 2 (strict Pydantic contracts):** **Not enforced on the live path today.** `workflow_engine.py`'s `self.context` is `Dict[str, str]` — every node's output is a plain string; nothing validates it against a schema before the next node consumes it. The strict-contract system this guardrail describes is real — it's `workflow_schema.py`'s `WorkflowPayload` — but it's the dormant Path B (§2.3), not what the live Workflow Builder enforces. This is the single biggest concrete gap between the blueprint's stated guardrails and reality; see §4.4.
**Guardrail 3 (DPAPI):** Aspirational; no tokens are persisted yet at all (§1 above). Real future work, see §4.1.
**Guardrail 4 (Feature Request Module):** Doesn't exist. See §4.5.

### §7 Directory Structure
Corrected in full in §2 above and the tree in Appendix B. The `.claude/skills/gstack/`, `cso/`, `office-hours/`, `ship/`, etc. entries are **Claude Code's own installed plugin skills** (this development environment's tooling), not Cortex application directories — they should never appear in a description of Cortex's own architecture. `.claude/skills/docx-style-skill.md` similarly doesn't exist; document styling rules live, if anywhere, as prose in the relevant `13_Functions/*.md` companion docs.

### §8 & §9 Data Contracts / Core Router Specification
Both sections describe `data_processing/workflow_schema.py` and `core_router.py`'s `CoreWorkflowRouter` almost exactly as they're actually written — **this is the closest the submitted blueprint comes to accurately describing a real file**, because it's describing the dormant Path B system (§2.3), not the live one. The one material inaccuracy: it attributes DAG traversal, WebSocket broadcasting, and node-level visual state to `core_router.py` — the real `CoreWorkflowRouter` doesn't traverse a DAG at all (it executes one block per call, called externally by `canvas_parser.py`'s `VisualWorkflowExecutor`) and neither of them touches a WebSocket.

### §10 Summary for Claude Code
The four architectural rules stated here (stateless phases, building-block hierarchy, visual feedback, directory rules) are all good rules **in principle** and mostly already true of the live system, modulo the WebSocket claim and the directory paths. Restated accurately: stateless phases ✅ true, building-block hierarchy ✅ true (with the Function/Function distinction noted), visual feedback ⚠️ true but post-hoc not live-streamed, directory rules ❌ wrong paths, right idea (00_System/10_Skills/11_Processes/12_Tasks/13_Functions/14_Adapters, not modules/ui/workflows).

---

## 4. Gap Analysis — Evaluating the Blueprint's New Capabilities Against Real Cortex

Each of these is evaluated on its own merits — not "does the blueprint want it" but "would Cortex, as a single-user desktop tool, actually benefit, and what's the smallest real step toward it."

### 4.1 DPAPI-encrypted credential storage

**Merit:** Real and worth doing, but only once there's something to encrypt. Today there are zero persisted enterprise tokens anywhere (browser bridges keep cookies in Playwright's own profile folders, which are already OS-file-permission-protected the same as any browser profile; nothing else writes a token to disk). DPAPI protects against a *different* threat model (another user account on the same machine, or a stolen unencrypted config file) than "should a mock token be prefixed clearly" (already solved, see `data_processing/auth.py`'s `mock_sandbox_...` convention).
**When it becomes worth building:** The moment `EnterpriseAuthManager` (§2.3) starts being called for real and its `access_token` result needs to survive a process restart (so the user doesn't re-authenticate every single run). At that point, wrap `cortex_database.py`'s token-cache table (or a new one) with `win32crypt.CryptProtectData`/`CryptUnprotectData` before writing, and the reverse on read. This is a small, well-bounded addition (`pywin32` needs adding to `requirements.txt` — it isn't there today) once §4.2 makes it relevant.
**Recommendation:** Defer until §4.2 ships. Building the encryption wrapper before there's a real token to protect is exactly the kind of speculative work this whole audit is trying to prevent.

### 4.2 M365 real wiring (MSAL delegated auth)

**Merit:** High — this was already scoped as the next major slice before this audit started, and this audit found the auth code already half-written.
**What already exists:** `data_processing/auth.py`'s `EnterpriseAuthManager.get_m365_access_token()` — a real MSAL `ConfidentialClientApplication` client-credentials flow, gated on `M365_CLIENT_ID`/`M365_TENANT_ID`/`M365_CLIENT_SECRET`, falling back to a clearly-labeled mock token. `msal` is referenced but **not in `requirements.txt`**, so today this silently always falls back to mock even with real env vars set.
**What's missing:** `m365_graph_bridge.py` doesn't import or call `EnterpriseAuthManager` at all — every function in it raises `NOT_CONFIGURED_MESSAGE` unconditionally in non-mock mode, with no actual `requests.get("https://graph.microsoft.com/...")` call written anywhere.
**Concrete plan (small, in this order):**
1. Add `msal` to `requirements.txt`.
2. Wire `m365_graph_bridge.py` to call `EnterpriseAuthManager.get_m365_access_token({})` and use the returned bearer token in real `requests` calls to `https://graph.microsoft.com/v1.0/...` for each existing mocked function (`list_files`, `send_mail`, etc.) — the exact same pattern already proven out for the HTTP Function node (`function_http`) in `workflow_engine.py`.
3. Only after that's live and tested against a real tenant: revisit whether `EnterpriseAuthManager`'s client-credentials (app-only) model is really what's wanted, versus a delegated-user MSAL flow (device code or interactive), per the earlier decision in this project's history to keep a single shared app identity for now and treat true per-Windows-user delegated identity as a separate, later initiative.
This is wiring existing code together, not new architecture.

### 4.3 Enterprise GCP Vertex AI (replacing the Gemini browser bridge)

**Merit:** Low, as a wholesale replacement. `gemini_bridge.py` is real, working, and free (no GCP billing, no service account, no project setup) — it uses the same consumer Gemini account a human would sign into. Vertex AI is a genuinely different product: paid, project-scoped, different SDK (`google-cloud-aiplatform`), different auth (service account or workload identity), different model catalog and quota rules. Swapping to it is not an upgrade to the existing bridge, it's standing up an entirely separate integration.
**When it's actually worth it:** If/when Cortex needs a RAG corpus (uploading a trade's curriculum materials as a persistent, queryable knowledge base rather than stuffing them into one prompt) or needs data-residency guarantees a personal Gemini account can't offer. Neither is true of the system today.
**Recommendation:** Don't build this speculatively. If a real workflow genuinely needs RAG-over-a-document-corpus, that's its own scoped feature (`14_Adapters/vertex_ai_bridge/`, alongside — not replacing — `gemini_bridge`), evaluated when a real use case names it.

### 4.4 Strict Pydantic contracts on the live execution path

**Merit:** High in principle, but the real cost is significant and the dormant Path B system (§2.3) already shows what "done" looks like structurally — the question is migration cost, not design.
**The real gap:** `workflow_engine.py`'s `self.context: Dict[str, str]` treats every node's output as an opaque string. Nothing stops a node from producing malformed JSON that the next node silently mishandles (several Function nodes already defensively `try: json.loads(...) except: fall back to raw string` for exactly this reason — see `function_set_variable`, `function_append_variable`). A full migration to `WorkflowPayload`-style validation between every node would be a genuine rewrite of the engine's core data-passing model, not an incremental patch — 100+ existing tests assert on the current string-based contract directly.
**Recommendation — incremental, not a rewrite:** Don't migrate the whole engine. Instead, apply the *pattern* `workflow_schema.py` already demonstrates in the one place it matters most: any node whose job is specifically to produce structured data for consumption elsewhere (`function_parse_json`, the AI capability Tasks that already ask Gemini to reply as JSON — `entity_extraction`, `key_phrase_extraction`, `form_invoice_processing`) could validate their own output against a small Pydantic model *before* returning it, raising `WorkflowRunError` on a schema mismatch instead of silently passing malformed JSON downstream. This gets the real safety benefit (fail loud at the point of production, not three nodes later) without touching the engine's core string-based token/context model at all.

### 4.5 Feature Request Module

**Merit:** Genuinely good idea, directly addresses the user's stated concern about ungoverned growth, and is cheap to build.
**Concrete plan:** A new `11_Processes/log_feature_request` (zero-input won't work since it needs input — make it a `12_Tasks/submit_feature_request` Task instead) that appends a structured row (`title`, `description`, `requested_capability`, `submitted_by`, `timestamp`, `status: "proposed"`) to a new SQLite table in `cortex_database.py` (or `database.py` — see §5's naming-cleanup note), plus a simple list/vote page mirroring the existing Tag Registry page's pattern. This is a small, well-scoped addition using patterns that already exist elsewhere in the codebase (a new DB table, a new page, a couple of endpoints) — no new architecture needed.

### 4.6 WebSocket live node-state streaming

**Merit:** Moderate. The current post-hoc coloring (§2.2) already gives a complete audit trail; the gap is only that a long-running workflow (a multi-minute Gemini Deep Research call, say) gives no feedback *during* the wait beyond the existing run-log terminal's step-by-step `wfbLog()` lines, which do already appear progressively today via the `(data.steps || []).forEach(...)` loop **after** the whole run finishes — there is genuinely no live/incremental feedback while a run is in flight.
**Concrete plan, if wanted:** `websockets` is already in `requirements.txt` (a transitive uvicorn dependency, currently unused by the app). Add one `@app.websocket("/ws/workflow-run/{run_id}")` route in `server.py`; have `WorkflowEngine.run()` accept an optional callback invoked after each node completes (a small, additive change — it already appends to `self.log` at exactly that point) that pushes the step over the socket instead of (or alongside) waiting for the whole run to finish. This is a genuinely incremental, bounded addition — not a rewrite — should the wait-time problem on long-running nodes actually become a real pain point.

---

## 5. Guardrails — Actually Preventing Drift

This is the direct answer to "how do we stop this from sliding into chaos."

1. **This document is the single source of truth for architecture questions**, effective immediately. `CORTEX_FUNCTIONAL_STATUS_REPORT.md` is superseded — see Appendix A for what to do with it.

2. **Before adding any new folder, dependency, or parallel data model, answer three questions first:**
   - Does something like this already exist in `data_processing/` or elsewhere, dormant? (§2.3 exists precisely because this question wasn't asked before.)
   - Will this be wired into the live path (`server.py` → `workflow_engine.py` → `core_router.py`), or is it another exploration that will sit unused? If the latter, don't build it yet — write the plan (as §4 does above) and get it approved first.
   - Does it fit the existing five-tier convention, or does it need its own justification for why not?

3. **Resolve the Path A / Path B split explicitly, on a real timeline, rather than let it continue silently:**
   - **Option A (recommended given current priorities):** Formally mark `data_processing/canvas_schema.py`, `canvas_parser.py`, `observer_transformer.py`, `observer_schema.py`, `theme_exporter.py`, and `runtime_state.py` as an **archived exploration** — move them under a clearly-named `data_processing/_archive_canvas_exploration/` (or delete them, since `sandbox_smoke_test.py` is their only consumer and could be trimmed to stop exercising them) so nothing new gets built assuming they're live infrastructure. Keep `workflow_schema.py`, `enterprise_adapters.py`, `auth.py`, and `user_identity.py` — those four are genuinely useful and directly relevant to §4.2/§4.4's real next steps.
   - **Option B:** Commit to actually finishing the integration (wire `canvas_parser.py`'s `VisualWorkflowExecutor` into a real page) — but only choose this if there's a real reason the Drawflow-based Workflow Builder isn't sufficient, since it would mean maintaining two visual canvases.
   - Either way, **decide, write the decision here, and stop leaving it ambiguous.**

4. **Naming debt worth cleaning up when next touched (not urgent, just tracked so it doesn't compound):** `database.py`'s own header calls it "Legacy Database Compatibility Middleware" *and* the submitted blueprint's directory listing separately calls it that — worth confirming with a quick read whether `database.py` and `cortex_database.py` should be consolidated or genuinely need to stay separate (the earlier audit this session found `cortex_database.py` manages a second, deliberately-separate `cortex_scrape.db` for web-scrape data — that split looks intentional and fine, just worth a one-line confirmation next time either file is touched).

5. **Every new capability gets a design doc before code**, per the existing `docs/superpowers/specs/` + `docs/superpowers/plans/` convention already established and used consistently through this session's own work (flow-control, variables/loops, AI capability Tasks, Gems). That discipline is working — the drift risk isn't from following it, it's from the pre-existing dormant Path B code that predates it.

---

## 6. Prioritized Roadmap

Given everything above, in the order that compounds best (each step makes the next one easier or is a prerequisite for it):

1. **Decide Path A/B (§5.3)** — a decision, not code. Do this first; it changes what "done" means for §4.2 and §4.4.
2. **M365 real wiring (§4.2)** — the highest-value, most-scoped, most "already half-built" item. Add `msal` to `requirements.txt`, wire `EnterpriseAuthManager` into `m365_graph_bridge.py`.
3. **Targeted Pydantic validation on JSON-producing nodes (§4.4, incremental version only)** — cheap, high-signal, doesn't touch the engine core.
4. **DPAPI token caching (§4.1)** — once step 2 produces a real token worth caching across restarts.
5. **Feature Request Module (§4.5)** — small, valuable, no dependencies on the above.
6. **WebSocket live streaming (§4.6)** — nice-to-have, revisit if long-running nodes actually become a felt pain point in practice.
7. **Google Workspace real wiring** — same shape as step 2, once step 2 is proven out end-to-end against a real tenant.
8. **Vertex AI (§4.3)** — only if a real use case (RAG over a document corpus, data residency requirement) actually names it. Not before.

---

## Appendix A: Disposition of `CORTEX_FUNCTIONAL_STATUS_REPORT.md`

That file (dated 2025-07-29, untracked in git) is a snapshot from before this session's flow-control/variables-loops/AI-capabilities/Gems work — its tool counts (35 Tasks, 7 Adapters, no `tests/` folder) are now stale, though its architectural description of the *live* path (workflow engine capabilities, license gating, MCP-readiness assessment) was accurate at the time and is a reasonable historical record. Recommend either deleting it (superseded in full by this document) or moving it to `docs/` as a dated historical snapshot if there's value in keeping the MCP-server-architecture sketch it contains (§"Recommended MCP Server Architecture," not reproduced here since it wasn't asked for by name and remains a reasonable future sketch on its own merits). Not deleted as part of this audit — flagging for an explicit decision rather than removing a file whose provenance/intent this document didn't originate.

## Appendix B: Corrected Directory Tree (replaces the submitted Blueprint's §7)

```text
Cortex/
├── .claude/                         # Claude Code tooling for THIS dev environment (not Cortex app code)
│   ├── settings.local.json
│   └── skills/                      # Installed Claude Code plugin skills (gstack, etc.) — unrelated to Cortex's own architecture
├── 00_System/                       # Core engine — server, router, engine, database, core logic lives here, nowhere else
│   ├── server.py                    # FastAPI app, ~1,700 lines, all routes
│   ├── workflow_engine.py           # The real DAG walker (WorkflowEngine)
│   ├── core_router.py               # CoreRouter (subprocess dispatch) + CoreWorkflowRouter (dormant, §2.3)
│   ├── database.py / cortex_database.py   # cortex.db / cortex_scrape.db
│   ├── model_classifications.py     # AI model → data-classification-level mapping
│   ├── logger.py / health.py
│   ├── tests/                       # All 00_System-level tests, moved here 2026-07-31
│   ├── data_processing/             # See §2.3 — contains BOTH real utilities (user_identity, enterprise_adapters, auth, workflow_schema) AND a dormant parallel canvas/execution system
│   └── templates/                   # Jinja2 pages + static assets + Drawflow.js + vendored Font Awesome
├── 10_Skills/                       # Empty — real skill registry is server.py's SKILLS_REGISTRY today
├── 11_Processes/                    # 8 zero-input Processes
├── 12_Tasks/                        # 56 configurable Tasks
├── 13_Functions/                    # 15 standalone Function scripts (distinct from workflow_engine.py's 33 built-in Function nodes, §2.4)
├── 14_Adapters/                     # 7 bridges + airgap_adapter.py
├── 01_inbox/ 02_vault/ 99_Outbox/    # File staging/storage (not shown in submitted blueprint at all)
├── docs/superpowers/{specs,plans}/  # Design-doc-before-code convention (§5.5)
└── CLAUDE.md                        # Project instructions — the actual, checked-in source of truth for conventions
```
