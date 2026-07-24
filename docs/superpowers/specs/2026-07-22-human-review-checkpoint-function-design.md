# Human Review Checkpoint Function — Design Spec

**Date:** 2026-07-22
**Status:** Approved by user, implementing directly

## Background

Following the NotebookLM adapter sub-project, the next piece of the "AI Exam
Builder"-style process-map example is a human-in-the-loop checkpoint: a
workflow step that hands its upstream content off to a person for review,
and — per the user — is the end of that workflow run. Later phases (Part 2,
Part 3, etc.) are separate saved workflows a person re-runs manually once
review is done; no automatic cross-run repeat/resume mechanism is needed.

Initial design considered a new engine-level node `kind: "checkpoint"` with
bespoke dispatch code in `workflow_engine.py`. The user redirected this:
implement it as a real script under `13_Functions/`, so it's a normal,
discoverable, reusable Function — consistent with `CLAUDE.md`'s own
taxonomy ("13_Functions: Automation utilities, transformation helpers, and
logic gates").

## Gap found while designing this

`13_Functions/` (the folder the "Functions" nav page already scans via
`CoreRouter.get_visible_apps()`) was never actually wired into the Workflow
Builder's node palette. `/api/workflow-builder/node-registry` in `server.py`
only merges `06_Tasks`, `05_Processes`, `08_Adapters`, `SKILLS_REGISTRY`, and
`FUNCTIONS_REGISTRY` (a hardcoded list of built-in engine node types) — never
`09_Functions`. That means no script placed in `13_Functions/` could ever be
dragged onto the canvas. Fixed as part of this change, since "so I can
easily add it to a workflow" requires it — and it benefits every future
`13_Functions` script, not just this one.

## Design

### 1. `workflow_checkpoints` table (`00_System/database.py`)

```sql
CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_label TEXT NOT NULL,
    node_title TEXT NOT NULL,
    instructions TEXT,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed TEXT
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON workflow_checkpoints(status);
```

One row per paused checkpoint — this is the "Awaiting Review" queue's data
source.

### 2. `server.py`: wire `09_Functions` into the Workflow Builder palette

`/api/workflow-builder/node-registry` gains one more merge loop, alongside
the existing Tasks/Processes/Adapters ones:

```python
for app_entry in manifest.get("09_Functions", []):
    entries.append({**app_entry, "kind": "function", "category": "09_Functions"})
```

`kind: "function"` (not a new kind) — it's badged/colored identically to the
existing hardcoded Functions in the palette, which is accurate: both *are*
functions, one set is file-based, one is built into the engine.

### 3. `workflow_engine.py`: dispatch `09_Functions` nodes like Task/Process/Adapter

`_execute_node`'s existing generic dispatch branch:

```python
if kind in ("task", "process", "adapter"):
    args = [self._substitute_tokens(str(a)) for a in (params.get("args") or [])]
    ...
    success, log_msg = self.router.execute_app_logic(node["category"], node["tool_id"], args)
```

extended to also catch `kind == "function"` nodes whose `category` is
`"09_Functions"`:

```python
if kind in ("task", "process", "adapter") or (kind == "function" and node.get("category") == "09_Functions"):
    ...  # unchanged body
```

Everything else (`kind == "function"` with `category is None`) still falls
through to the existing `_execute_function_node` if/elif ladder unchanged.
No new engine-level checkpoint concept, no new dispatch code path — this
reuses the exact mechanism Tasks/Processes/Adapters already use.

### 4. New Function: `13_Functions/human_review_checkpoint/human_review_checkpoint.py`

Plain positional CLI args (matching the Task convention, e.g.
`word_to_excel_exam.py`) rather than a JSON payload — this lets it be
configured entirely through the Workflow Builder's existing generic "Args"
box (one arg per line, each already `{{node_id}}`-token-substituted by the
engine before dispatch), with zero new config-panel code needed:

1. `content_text` — the text to write out for review (typically
   `{{upstream_node_id}}`).
2. `output_dir` — folder to write the review file into.
3. `filename` — base filename (extension added automatically per format).
4. `format` — `docx` (default if blank) / `json` / `markdown`.
5. `instructions` — reviewer-facing guidance text, shown in the queue.
6. `workflow_label` — which workflow this came from, shown in the queue
   (e.g. `"AI Exam Builder (Part 1)"`).

Behavior (`HumanReviewCheckpoint` class, same shape as
`import_transcripts.py`'s `TranscriptsImporter`: `run() -> dict` report,
`if __name__ == "__main__": print(importer.run())`):

1. Write `content_text` to a real file under `output_dir` in the requested
   `format` (docx: one paragraph per line, matching
   `workflow_engine.py`'s existing `_write_word_export`; json: parsed and
   pretty-printed if valid JSON else wrapped, matching
   `_write_json_export`; markdown: written as-is). PDF intentionally
   skipped — nothing in this pipeline needs it yet.
2. Insert one row into `workflow_checkpoints` (`workflow_label`,
   `node_title` — a fixed label since a Task script has no node id/title at
   dispatch time, `instructions`, `file_path`, `status='pending'`).
3. Print a human-readable summary (checkpoint id + file path) and return a
   report dict — becomes the node's captured output text in the run log,
   same as every other Task/Process node.

`.md` doc file + `test_human_review_checkpoint.py` (assert-based, no
framework) follow the same convention as `12_Tasks/import_documents/`.

### 5. Review Queue: new page + nav item

* `GET /api/workflow-checkpoints?status=pending|reviewed|all` — list rows.
* `POST /api/workflow-checkpoints/{id}/resolve` — sets `status='reviewed'`,
  `reviewed=datetime('now')`.
* `templates/review-queue.html` — flat list (not tag-grouped like
  Tasks/Functions/Adapters, since checkpoints are individual items, not
  registered tools), with Pending/Reviewed/All tabs and a "Mark Reviewed"
  button per row. Each row shows `workflow_label`, `instructions`,
  `file_path`, `created`.
* `templates/index.html` — new "Review Queue" nav button placed directly
  after "Workflow Builder" (closely related feature, no tag submenu needed).

### 6. Canvas visual distinction (`workflow-builder.html`)

Since this node is a normal `"function"` kind (not a bespoke kind), the
"show human in the loop" visual cue is keyed off its specific `tool_id`
(`human_review_checkpoint`) rather than off `kind` — generalizes to any
future similarly-special function without needing a new kind:

* A small `HUMAN_CHECKPOINT_TOOL_IDS` set checked in `nodeHtml()`/node
  creation, giving matching nodes a distinct warning-colored border (CSS
  class `kind-human-checkpoint`, solid, vs. Container's dashed primary
  border) and a person-check icon prefix on the card title — same visual
  treatment style as the existing Container icon prefix.

## Testing

* `test_human_review_checkpoint.py` — assert-based checks for each format
  writer + the DB insert, run via `python test_human_review_checkpoint.py`.
* Manual `WorkflowEngine(dry_run=False)` run of a small graph feeding a
  `09_Functions`/`human_review_checkpoint` node, confirming real dispatch
  through `CoreRouter`, a real file written, and a real
  `workflow_checkpoints` row inserted.
* Manual check of `/api/workflow-builder/node-registry` to confirm the new
  function is present with `category: "09_Functions"`, and of the Review
  Queue endpoints/page.

## Explicitly Out of Scope

* PDF output format for the checkpoint file.
* System-tracked repeat/loop scheduling across separate workflow runs
  (confirmed manual re-run is sufficient).
* Any resume-same-run capability — reaching this node ends that run;
  continuing the process map means manually running the next phase's
  workflow later.
* A field-partial config UI for this function (the generic Args box is
  sufficient, per the "reuse what's already there" decision above).
