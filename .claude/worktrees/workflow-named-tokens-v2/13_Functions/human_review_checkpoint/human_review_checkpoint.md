---
tool_id: 'human_review_checkpoint'
title: 'Human Review Checkpoint'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/human-in-the-loop, scope/workflow-builder]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# human-review-checkpoint

> **Status:** Active. Ends a Workflow Builder run at a human hand-off point — writes the upstream content to a real file for review and registers it in the "Awaiting Review" queue. Drag-and-droppable from `13_Functions/` onto the Workflow Builder canvas like any other Function node.

## Purpose

Some process maps need a real person in the loop before continuing (e.g. the
"AI Exam Builder" example: Part 1 produces a draft that a human reviews and
edits before Part 2 begins). This function is the hand-off point: it writes
whatever text fed into it out to a real file (docx/json/markdown), and adds
one row to the `workflow_checkpoints` table so it shows up on the Review
Queue page. Reaching this node is the end of that workflow run — continuing
the process (Part 2, etc.) means a person manually runs the next saved
workflow once their review is done. No automatic resume/repeat is built in.

## Input

One JSON payload, positional CLI arg (same convention as every other
migrated `13_Functions` script and the Adapters):

```json
{
    "content_text": "the text to write out, typically {{upstream_node_id}}",
    "output_dir": "folder to write the review file into",
    "filename": "base filename (extension added automatically per format)",
    "format": "docx (default if blank) | json | markdown -- PDF not supported",
    "instructions": "reviewer-facing guidance text, shown in the queue",
    "workflow_label": "which workflow/phase this came from, e.g. 'AI Exam Builder (Part 1)', shown in the queue"
}
```

Has a proper Workflow Builder config panel (see `ARG_FIELD_SCHEMAS` in
`workflow-builder.html`) — each field above is its own labeled input, not a
blind JSON textarea.

## Processing Logic

1. Validate `format` is one of `docx`/`json`/`markdown`.
2. Write `content_text` to `output_dir/filename.<ext>`:
   - `docx` — one paragraph per line (same shape as
     `workflow_engine.py`'s `_write_word_export`).
   - `json` — parsed and pretty-printed if valid JSON, else wrapped as
     `{"content": ...}` (same shape as `_write_json_export`).
   - `markdown` — written as-is.
3. Insert one row into `workflow_checkpoints` (`workflow_label`,
   `node_title` fixed to `"Human Review Checkpoint"`, `instructions`,
   `file_path`, `status='pending'`).
4. Print a report dict (`checkpoint_id`, `file_path`, `message`) — becomes
   the node's captured output text in the Workflow Builder run log.

## Output

* The written review file at `output_dir/filename.<ext>`.
* One new row in `cortex.db`'s `workflow_checkpoints` table (see
  `00_System/database.py`), visible on the Review Queue page until marked
  reviewed.

## Notes for AI reuse

* Dispatched via `workflow_engine.py`'s generic Task/Process/Adapter path
  (`kind == "function"` + `category == "09_Functions"` now also routes
  there) — no bespoke engine-level "checkpoint" node kind exists.
* On the Workflow Builder canvas, this specific `tool_id` gets a distinct
  warning-colored border and a person-check icon (see
  `HUMAN_CHECKPOINT_TOOL_IDS` in `workflow-builder.html`) so it's visually
  obvious on any process map where the automated part ends and a human
  step begins.
