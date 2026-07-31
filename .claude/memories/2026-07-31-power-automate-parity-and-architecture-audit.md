# 2026-07-31 — Power Automate Parity Build-Out, File Reorg, and Architecture Audit

## What Happened

Built four sequential slices toward Power Automate action parity in the Workflow Builder: (1) flow-control/data-op Function nodes (Compose, HTTP, Terminate, Delay, the array-op family — 20 new node types), (2) a named-variable store and Apply-to-Each/Do-Until loop execution (a real engine capability, not just new nodes — required extracting loop containers into private sub-graphs instead of the existing flatten-once model), (3) twelve Gemini-backed AI capability Tasks (sentiment, translation, OCR, etc. — all real today, no credentials needed, since `gemini_bridge.py` was already a working browser-session bridge), and (4) a Gemini Gems connector mirroring the existing Copilot Agents pattern. Also reorganized `00_System/tests/` into its own subfolder. Each slice went through spec → plan → TDD build; several real bugs were caught by tests before ever reaching the user (a loop-container extraction bug, a dry-run/cap ordering bug, a nested-loop double-processing bug).

Then a detailed "Cortex Operational Architecture Blueprint" was submitted for an audit-and-realignment pass. It described a system (React/`@xyflow/react`, MSAL+DPAPI already wired, Vertex AI, a `modules/ui/workflows` layout) that didn't match the real codebase in almost any particular. Investigating instead of executing it literally surfaced the session's biggest finding: `00_System/data_processing/` contains a complete, dormant second execution architecture (Pydantic `WorkflowPayload` contracts, an n8n-style canvas model, and — critically — a real, already-written MSAL client-credentials flow in `auth.py`) built during an earlier exploration and never wired into the live Drawflow-based app. This produced `CORTEX_ARCHITECTURE_BLUEPRINT.md` (v2.0, at repo root) and `CORTEX_DEVELOPMENT_ROADMAP.md` (8 stages), both meant to be read by any future session before it touches Cortex.

## Key Decisions

- **Path A/B resolution (blueprint §5):** `workflow_schema.py`, `enterprise_adapters.py`, `auth.py`, `user_identity.py` are retained and get actively wired in. `canvas_schema.py`, `canvas_parser.py`, `observer_transformer.py`, `observer_schema.py`, `theme_exporter.py`, `runtime_state.py` are to be archived under `data_processing/_archive_canvas_exploration/` — decided, not yet executed (that's Roadmap Stage 0).
- **Roadmap sequencing:** Stages 0–6 need zero tenant access and are fully mock-testable; Stage 7 (real Entra ID + Google Cloud credentials) is scoped narrowly to verification, not new development. See `[[project_cortex_roadmap_sequencing]]` in Claude's own memory.
- **Single shared app-identity** (client-credentials/app-only MSAL) for now, not per-Windows-user delegated auth — that's explicitly a separate, later initiative.
- **`database.py` is the primary DB interface** (`brain_state.db`); `cortex_database.py` is deliberately secondary, scoped only to `cortex_scrape.db`. Don't conflate them (an earlier draft of the blueprint did).
- **No React, no rewrite.** The live stack (FastAPI/Jinja2/Drawflow.js/`workflow_engine.py`) is staying; the blueprint's aspirational stack was reconciled against reality, not adopted literally.

## What's Next

Roadmap Stage 0 (archive the dormant Path B files) is the natural entry point — small, no tenant needed, unblocks the "what's live" question for every later stage. Stage 1 (M365 real-call wiring via the already-written `EnterpriseAuthManager`) is the highest-value stage after that. Full detail for every stage is in `CORTEX_DEVELOPMENT_ROADMAP.md` — read that before starting any of them, it's written to be actionable by a cold session.
