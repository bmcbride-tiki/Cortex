# CORTEX Development Roadmap — Current State → Target State

> **Document Version:** 1.0
> **Date:** 2026-07-31
> **Companion to:** `CORTEX_ARCHITECTURE_BLUEPRINT.md` (v2.0) — read that first for the *why*; this document is the *how*, broken into stages.
> **Organizing principle:** Every stage below is sequenced by one rule: **build and mock-test everything that doesn't require real Entra ID / Google Cloud tenant access first.** Real tenant access gets one final, short verification stage (Stage 7) at the end — not scattered "waiting" throughout. By the time real credentials exist, the only work left should be pointing already-finished code at them and fixing whatever a real API does differently than its mock.

---

## How to Use This Document

Each stage below is written to be **self-contained enough for a fresh Claude Code session — one with no memory of this conversation — to pick up and start working from.** Every stage that involves writing code still goes through this project's established discipline (confirmed working across every prior slice this project has built):

1. **Brainstorm** the stage's specific design decisions that aren't already settled below (there are usually a few — this roadmap sets direction, not every line of code).
2. **Write a spec** to `docs/superpowers/specs/YYYY-MM-DD-<stage-name>-design.md`.
3. **Get it reviewed** (by you, the project owner) before implementation.
4. **Write a plan** to `docs/superpowers/plans/YYYY-MM-DD-<stage-name>.md` (TDD, task-by-task).
5. **Execute** the plan, committing after each task, running the full existing test suite before and after.

A session starting a stage should say, in effect: *"Read `CORTEX_ARCHITECTURE_BLUEPRINT.md` and `CORTEX_DEVELOPMENT_ROADMAP.md`, then let's build Stage N."* Each stage entry below gives that session everything it needs to start the brainstorming conversation productively instead of re-deriving context from scratch.

**Definition of Done, every stage:** all new code has tests; the full existing test suite still passes (currently: `00_System/tests/test_workflow_engine_*.py` ×4, `test_model_classifications.py`, `sandbox_smoke_test.py`, plus every `12_Tasks/*/test_*.py` and `14_Adapters/*/test_*.py`); a live manual check through the running server confirms the new capability actually works end-to-end in whatever mode is available (mock, until Stage 7).

---

## The Target State, Stated Plainly

By the end of Stage 6, Cortex should be a system where:
- Every M365 and Google Workspace action Cortex claims to support has **real, working request-construction code** behind it — not a `NOT_CONFIGURED_MESSAGE` stub — gated by the exact same `MOCK_MODE` convention already used everywhere else, verified with mocked HTTP responses.
- Any token a real auth flow produces is **encrypted at rest** before it touches disk, using the OS-native mechanism (DPAPI) already scoped for this in the architecture blueprint.
- Every workflow node that's supposed to produce structured JSON **validates its own output** before handing it downstream, instead of letting malformed JSON silently propagate.
- A long-running workflow step gives **live, incremental feedback** in the UI instead of a silent wait until the whole run finishes.
- New capability ideas have a **formal intake path** (the Feature Request module) instead of appearing as unplanned additions.
- The dormant "Path B" exploration code is **either actively used or clearly archived** — nothing sits in an undocumented, ambiguous state.

Stage 7 is then genuinely small: acquire real credentials, flip four environment variables, run the existing test suite's live-mode path, fix whatever a real tenant does differently than the mocks assumed, and ship.

---

## Stage 0 — Path B Resolution (Housekeeping) = DONE

**Goal:** Execute the architecture blueprint's §5 decision. No new capability — this is cleanup that makes every later stage's "what's real" question unambiguous.

**Why first:** Every later stage that touches `data_processing/` needs to know which files in there are live infrastructure versus archived exploration. Deciding this in a document (already done, blueprint §5) and *not yet executing it* is exactly the kind of half-finished state this whole effort is trying to eliminate.

**Scope:**
- Create `00_System/data_processing/_archive_canvas_exploration/`.
- Move `canvas_schema.py`, `canvas_schema.md`, `canvas_parser.py`, `canvas_parser.md`, `observer_transformer.py`, `observer_transformer.md`, `observer_schema.py`, `observer_schema.md`, `theme_exporter.py`, `theme_exporter.md`, `runtime_state.py`, `runtime_state.md` into it (via `git mv`, preserving history — same pattern used for the `00_System/tests/` reorg).
- Add one `README.md` in the new folder: what this was (an early n8n-style visual canvas exploration), why it's archived (never wired into the live Drawflow-based Workflow Builder — see blueprint §3.3), and that `workflow_schema.py`/`enterprise_adapters.py`/`auth.py`/`user_identity.py` are the four files from this same folder that are *not* archived, because Stages 1–2 below actively use them.
- Update `00_System/tests/sandbox_smoke_test.py`: it currently exercises the archived modules (`test_visual_canvas`, `test_observer_pipeline` per its own docstring). Either remove those two checks or update their imports to the new archive path — confirm with whoever picks up this stage which makes more sense once the file is actually re-read (the smoke test's remaining checks, `test_data_flow` and `test_licensing`, exercise the *retained* files and should keep running).

**Not in scope:** Any change to `workflow_schema.py`, `enterprise_adapters.py`, `auth.py`, or `user_identity.py` themselves — those are touched starting Stage 1.

**Testing (no tenant needed):** Run `sandbox_smoke_test.py` after the move and confirm it still passes (or passes with the two archived-module checks cleanly removed, not silently broken). Run the full existing test suite to confirm nothing else imports the moved files (a quick `grep` for each archived filename across the repo before moving is the cheap way to be sure).

**Estimated effort:** Small — one session, well under the size of any slice built so far this project.

---

## Stage 1 — M365 Real-Call Wiring (Mock-Verified, Tenant-Pending) - DONE

**Goal:** Every M365 Graph/Power BI action Cortex exposes gets real HTTP request-construction code, using the already-written MSAL auth in `data_processing/auth.py`, fully testable today via mocked HTTP responses — with zero real tenant access required to finish this stage.

**Why this order:** Highest-value, most "already half-built" item per the blueprint's own gap analysis. `EnterpriseAuthManager.get_m365_access_token()` already exists; this stage is wiring, not new architecture.

**What already exists (read these before starting):**
- `00_System/data_processing/auth.py` :: `EnterpriseAuthManager.get_m365_access_token(auth_references: Dict[str, str]) -> str` — real MSAL client-credentials flow against `M365_CLIENT_ID`/`M365_TENANT_ID`/`M365_CLIENT_SECRET`, mock-token fallback.
- `14_Adapters/m365_graph_bridge/m365_graph_bridge.py` — every function currently does `if not MOCK_MODE: raise RuntimeError(NOT_CONFIGURED_MESSAGE)`. This stage replaces that raise with a real call, function by function.
- `00_System/workflow_engine.py`'s `function_http` node — the existing, tested pattern for "make a real `requests` call, handle non-2xx as a failure" to follow for consistency (30s timeout, clear error messages including status code + body).

**Scope — functions to wire, in this order (roughly cheapest/most-used first):**
1. `list_files` / `download_file` / `upload_file` (OneDrive/SharePoint via `/me/drive` or `/sites/{id}/drive` Graph endpoints)
2. `send_mail` / `list_messages` / `search_messages` (Outlook `/me/sendMail`, `/me/messages`)
3. `list_calendar_events` / `create_calendar_event` (`/me/events`)
4. `list_teams` / `list_channels` / `post_channel_message` / `list_chat_messages` / `send_chat_message` (Teams Graph endpoints)
5. `list_sharepoint_sites` / `get_sharepoint_site` / `list_sharepoint_lists` / `list_sharepoint_list_items` / `create_sharepoint_list_item`
6. `list_onenote_notebooks` / `list_onenote_pages` / `get_onenote_page_content` / `create_onenote_page`
7. `get_excel_range` / `set_excel_range` (Excel Workbook API — requires a `driveItem` id, confirm exact request shape against current Graph docs when implementing, don't assume the exact endpoint from memory)
8. `refresh_powerbi_dataset` / `list_powerbi_reports` (Power BI REST API — a different base URL, `api.powerbi.com`, not `graph.microsoft.com`; same MSAL token likely won't have the right scope — confirm the correct scope/audience when implementing)
9. **New functions, not yet stubbed at all** (per the blueprint's original scoping): Planner (`Create Task`, `Update Task`), Forms (`Get Response`), Dataverse (`Add Row`, `Update Row`), Word Online (`Populate Template`), Power BI (`Execute Query`) — each needs a new function in `m365_graph_bridge.py` plus a new `12_Tasks/` wrapper, following the exact pattern every existing M365 Task already uses.

**Key design decisions already settled (don't re-litigate these unless something concrete argues otherwise):**
- Single shared app-identity via env vars (client-credentials/app-only), not per-Windows-user delegated auth — that's explicitly a separate, later initiative per this project's own history.
- `MOCK_MODE` stays the toggle (`M365_MOCK_MODE` env var, already the convention) — real code lives behind it, not instead of it.
- App-only auth has no signed-in "me": every function that today implicitly assumes `/me/...` will need an explicit target user (UPN) parameter once real — decide per-function whether that's a new required parameter or a sensible default, and update each function's Task wrapper's parameter list to match.

**Testing (no tenant needed):** Mock `requests.request`/`requests.get`/etc. via `unittest.mock.patch`, exactly like this project's `function_http` node tests already do (see `00_System/tests/test_workflow_engine_flow_and_data_ops.py`'s `test_http_live_success`/`test_http_non_2xx_raises` for the pattern). For each wired function: one test asserting the correct URL/headers/body get constructed from a mocked successful response, one test asserting a non-2xx response raises clearly. Also add `msal` to `requirements.txt` and confirm `import msal` succeeds (`pip install -r requirements.txt`).

**What can't be finished without a tenant:** Confirming the mocked request shapes exactly match what the real Graph API expects (exact field names, exact response envelope shape) — that's Stage 7's job. Write the code as close to the documented Graph API contract as possible, but don't treat this stage as "proven," only as "ready."

**Estimated effort:** Large — comparable to or larger than this project's flow-control-and-data-operations slice (20 nodes). Consider splitting into two plan-execution passes: existing-function wiring first, new-function additions second.

---

## Stage 2 — Google Workspace Bridge (Mock-Verified, Tenant-Pending)

**Goal:** A new `14_Adapters/google_workspace_bridge/` mirroring `m365_graph_bridge`'s shape exactly, covering Gmail, Calendar, Drive, Sheets, Contacts, and Tasks, using the already-written Google auth in `data_processing/auth.py`.

**Why after Stage 1, not before or in parallel:** Same shape of work, so Stage 1 is where the "mock the HTTP call, verify request construction" pattern gets proven out once; Stage 2 reuses that proven pattern rather than inventing it twice simultaneously.

**What already exists:**
- `data_processing/auth.py` :: `EnterpriseAuthManager.get_google_access_token()` — real `google.oauth2.service_account` flow against `GOOGLE_SERVICE_ACCOUNT_JSON`, mock-fallback. Note: `google-auth` (which provides `google.oauth2.service_account`) is **already in `requirements.txt`** — unlike `msal`, no new dependency is needed for this stage's auth path.
- No existing Google Workspace bridge folder or Task wrappers exist yet at all — this is new, not wiring an existing stub.

**Scope — new adapter + Task wrappers, mirroring the M365 Task-per-action convention:**
- Gmail: `Send Email`, `Get Emails`, `Create Draft`.
- Google Calendar: `Create Event`, `Get Events`.
- Google Drive: `Create File`, `Get File`, `Copy File`.
- Google Sheets: `Add Row`, `Get Rows`, `Update Row`.
- Google Contacts: `Create Contact`, `Get Contact`.
- Google Tasks: `Create Task`, `Complete Task`.

**Key design decisions to settle in this stage's own brainstorming (not yet decided — genuinely open):**
- Credential shape: a domain-wide-delegated service account (needed to act "as" a specific user's Gmail/Calendar/Drive, which a bare service account without delegation cannot do) versus OAuth2 client credentials. `data_processing/auth.py`'s current implementation is a plain service-account flow with no delegation `subject` parameter — confirm whether that needs to change before this stage can act on behalf of a specific user's data, or whether the initial scope is deliberately limited to what a bare service account *can* reach (e.g., a shared Drive, not a personal Gmail inbox).
- Whether `MOCK_MODE` for this new bridge gets its own env var (`GOOGLE_WORKSPACE_MOCK_MODE`, matching the `M365_MOCK_MODE`/`GEMINI_MOCK_MODE` per-adapter convention already established) — yes, almost certainly, for consistency; confirm and move on rather than treating as open.

**Testing (no tenant needed):** Same mocked-HTTP-response pattern as Stage 1.

**Estimated effort:** Large, similar shape to Stage 1's "new function additions" half.

---

## Stage 3 — DPAPI Credential Caching

**Goal:** Any access token Stages 1–2 produce gets encrypted at rest via Windows DPAPI before being written to disk, and decrypted transparently on read — built and fully tested *now*, using a synthetic token string, with zero dependency on a real credential existing yet.

**Why this doesn't need to wait for Stage 7:** DPAPI encrypt/decrypt is a pure round-trip operation (`win32crypt.CryptProtectData` / `CryptUnprotectData`) — it doesn't care whether the string being protected is a real bearer token or the word `"test"`. Building and testing this now, ready to receive Stage 1/2's real tokens the moment they exist, is exactly the "build to the highest level of completion while waiting for access" instruction behind this whole roadmap.

**Scope:**
- Add `pywin32` to `requirements.txt` (provides `win32crypt`; not currently a dependency).
- A new small module (e.g. `00_System/data_processing/token_vault.py`) with `encrypt_token(plaintext: str) -> bytes` / `decrypt_token(ciphertext: bytes) -> str`, wrapping `win32crypt.CryptProtectData`/`CryptUnprotectData`.
- A new table in `database.py` (the primary DB — **not** `cortex_database.py`, see architecture blueprint §9) storing `{service: str, encrypted_token: BLOB, cached_at: timestamp}`, keyed by service name (`"m365"`, `"google"`).
- Wire `EnterpriseAuthManager` (or a thin wrapper around it) to check this cache before making a fresh MSAL/service-account call, and to write a freshly-acquired token into it afterward.

**Testing (no tenant needed):** Round-trip test — encrypt a synthetic string, decrypt it, assert equality. A cache-hit test — seed the DB table directly with an encrypted synthetic token, confirm `EnterpriseAuthManager` returns it without attempting a fresh MSAL/service-account call (mock those calls and assert they're *not* invoked). A cache-miss test — empty table, confirm the underlying auth call *is* invoked and its result gets cached.

**Estimated effort:** Small–medium.

---

## Stage 4 — Targeted Pydantic Validation on JSON-Producing Nodes

**Goal:** Nodes whose entire job is producing structured JSON validate their own output against a small Pydantic model before returning it, per architecture blueprint §4.4's "incremental, not a rewrite" recommendation.

**Why not a full engine migration:** `workflow_engine.py`'s `Dict[str, str]` context is asserted on directly by 100+ existing tests; a full migration to typed payloads is a different, much larger project with its own cost/benefit case that hasn't been made. This stage gets the real safety benefit (fail loud at the point of production) without touching that core model at all.

**Scope — nodes to add validation to:**
- `function_parse_json` (the built-in Function node) — already does a `json.loads` check; extend with an optional Pydantic-schema-string parameter for stricter validation than "required keys present," if a real use case wants it (open question for this stage's brainstorming — don't over-build past what's needed).
- `entity_extraction`, `key_phrase_extraction`, `form_invoice_processing`, `business_card_id_reader`, `object_detection_ocr` (the Gemini-backed AI capability Tasks that already ask for JSON output) — each gets a small Pydantic model matching its documented expected shape (e.g., `entity_extraction`'s `List[{"text": str, "type": str}]`), validated after the Gemini call returns, raising a clear error naming exactly which field failed rather than silently passing through whatever Gemini actually said.

**Key design decision:** Since these are Tasks (not Function nodes), a validation failure should follow the same `{"success": False, "response": "<clear error>"}` convention every Task already uses — not a new error-handling pattern.

**Testing (no tenant needed):** For each node — one test with a mocked well-formed AI response that passes validation, one test with a mocked malformed response that fails validation clearly (naming the missing/wrong field, not just "invalid").

**Estimated effort:** Small–medium, cleanly parallelizable per node if split across a few sessions.

---

## Stage 5 — Feature Request Module

**Goal:** A formal intake path for new capability ideas, directly addressing the governance concern behind this whole roadmap.

**Scope:**
- `12_Tasks/submit_feature_request/submit_feature_request.py` — a Task (needs input: `title`, `description`, `requested_capability`, `submitted_by`) that inserts a row into a new table in `database.py`: `{id, title, description, requested_capability, submitted_by, timestamp, status}` (`status` starting at `"proposed"`).
- A new page (mirroring the existing Tag Registry page's pattern in `server.py`/`templates/`) listing open feature requests, with a simple upvote count and status filter.
- A couple of new endpoints: `POST /api/feature-requests`, `GET /api/feature-requests`, maybe `POST /api/feature-requests/{id}/vote`.

**Testing (no tenant needed):** Standard Task test (missing-required-param failure, happy-path insert) plus a couple of endpoint tests confirming the list/vote routes work against the new table.

**Estimated effort:** Small–medium, no dependency on any other stage.

---

## Stage 6 — WebSocket Live Node-State Streaming

**Goal:** Incremental, live feedback during a run — not just the current post-hoc full-result coloring — for long-running steps (a multi-minute Gemini Deep Research call, say).

**Scope:**
- One `@app.websocket("/ws/workflow-run/{run_id}")` route in `server.py`.
- `WorkflowEngine.run()` gains an optional `on_step` callback parameter, invoked at the exact point it already does `self.log.append(...)` for each node — additive, doesn't change the existing return-value contract anything else relies on.
- `workflow-builder.html`'s `wfbRun()` opens a socket alongside its existing POST, updating node borders as each step event arrives instead of (or in addition to) the current all-at-once coloring after the POST resolves.

**Testing (no tenant needed):** A test asserting `WorkflowEngine.run(graph, on_step=callback)` invokes the callback once per node in the right order with the right payload shape. Manual browser verification for the actual live-coloring behavior (this project's established pattern: verify UI behavior in the running app, not just via automated tests, per CLAUDE.md's own UI-testing instruction).

**Estimated effort:** Small–medium. Genuinely optional relative to Stages 1–5 — revisit priority if a real long-running-node pain point hasn't actually shown up in practice by the time this stage comes up.

---

## Stage 7 — Live Tenant Cutover & Verification (Requires Real Access)

**Goal:** The only stage that actually needs the Entra ID app registration and Google Cloud service account. Everything built in Stages 1–6 should already be code-complete and mock-tested; this stage is verification and fixing real-world surprises, not open-ended development.

**Prerequisites (must exist before starting):** A real Entra ID app registration (tenant ID, client ID, client secret, Graph + Power BI API permissions, admin consent granted) and a real Google Cloud service account key (with domain-wide delegation if Stage 2's brainstorming determined that's needed) — per your own stated plan to do this in a sandbox environment first, mimicking the production tenant's constraints.

**Scope (per your project's own established testing philosophy — one tool at a time, in the sandbox, before touching live data):**
1. Set the real env vars (`M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CLIENT_SECRET`, `GOOGLE_SERVICE_ACCOUNT_JSON`) in the sandbox environment.
2. Flip `M365_MOCK_MODE=0` (and the Google equivalent from Stage 2).
3. Work through Stage 1's function list one at a time against the real sandbox tenant, comparing actual Graph API responses against what Stage 1's mocks assumed — fix any real-world discrepancies (field name differences, pagination the mock didn't model, actual required scopes).
4. Repeat for Stage 2's Google functions against the real sandbox project.
5. Confirm Stage 3's DPAPI token caching correctly persists and reuses a *real* acquired token across a process restart.
6. Only once the sandbox is fully green: repeat against the real production tenant, per your own stated caution about moving from sandbox to live data.

**This stage should not involve writing new capabilities** — if something is missing at this point, that's a sign a Stage 1–6 gap was missed, worth going back and fixing at the source (adding a proper mock-tested implementation) rather than patching live-only code that skips the testing discipline every other stage followed.

---

## Summary Table

| Stage | Needs tenant access? | Depends on | Size |
|---|---|---|---|
| 0. Path B Resolution | No | — | Small |
| 1. M365 Real-Call Wiring | No (mock-tested only) | Stage 0 (clean `data_processing/`) | Large |
| 2. Google Workspace Bridge | No (mock-tested only) | Stage 1 (proven pattern) | Large |
| 3. DPAPI Credential Caching | No (synthetic tokens) | Stages 1–2 (something to eventually cache) | Small–medium |
| 4. Targeted Pydantic Validation | No | None (independent) | Small–medium |
| 5. Feature Request Module | No | None (independent) | Small–medium |
| 6. WebSocket Live Streaming | No | None (independent) | Small–medium |
| 7. Live Tenant Cutover | **Yes** | Stages 1–3 | Small (verification, not development) |

Stages 3–6 have no hard dependency on Stages 1–2 finishing first and can be reordered or run in parallel across sessions if that's more convenient — they're listed in this order because it roughly matches value density, not because of a strict technical dependency (Stage 3 is the one soft exception: it's more meaningful once Stage 1 or 2 exists to give it a real token to eventually cache, but the caching mechanism itself has zero technical dependency on either).
