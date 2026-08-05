# _archive_canvas_exploration/

## What this was

An early, n8n-style visual workflow canvas built as a standalone exploration:
a graph model (`canvas_schema.py`), an executor that walks that graph through
`CoreWorkflowRouter` (`canvas_parser.py`), a run-history-to-approval-pipeline
view (`observer_schema.py`, `observer_transformer.py`), a ShadCN color theme
for rendering it (`theme_exporter.py`), a disk save/load for its payloads
(`runtime_state.py`), and the SVGL brand-icon lookup it used for node logos
(`svgl_icon_manager.py`).

## Why it's archived

It was never wired into the live Workflow Builder page. The real, running
builder saves/loads a raw Drawflow.js export and is parsed by
`workflow_engine.py` — a different graph format entirely. This folder's
`CanvasNode`/`CanvasEdge` model is a parallel design that stayed dormant
alongside the live path with no record of which one was "real." See
`CORTEX_ARCHITECTURE_BLUEPRINT.md` §3.3 and §5 (Path A / Path B
Reconciliation) for the full audit and decision.

Nothing here is deleted — it's a real, working design, just not the one in
production. Revisiting it requires a concrete new reason (e.g. an actual
second visual canvas requirement), not silent re-accumulation.

## What's *not* archived

Four other files that used to sit alongside these in `data_processing/` are
**not** archived and remain active: `workflow_schema.py`,
`enterprise_adapters.py`, `auth.py`, and `user_identity.py`. Those are
genuinely live utilities, actively wired into the real path starting with the
roadmap's later stages — do not move or treat them as part of this
exploration.
