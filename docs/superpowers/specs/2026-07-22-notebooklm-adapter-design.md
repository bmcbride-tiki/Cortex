# NotebookLM Adapter + Workflow Nodes — Design Spec

**Date:** 2026-07-22
**Status:** Approved by user, ready for implementation plan

## Background

The long-term goal (tracked in `CLAUDE.md`) is a set of workflows that mirror
real business process maps — chaining document conversion, AI research, a
human review step, and final formatted output. The first concrete example is:

```
[Docx File Input]
└──> Convert Docx to cg.json                              (already works: curriculum_guide_to_tos.py)
└──> Transform cg.json to TOS (.xlsx)                      (already works)
└──> Create Gemini NotebookLM notebook                     <- THIS SPEC
    ├──> Upload sources (PDFs, Docx, cg.json)               <- THIS SPEC
    ├──> Execute prompt loop sequentially                   <- THIS SPEC
    └──> Scrape responses into stem.json                    <- THIS SPEC (via existing function_export_json)
└──> Convert stem.json to .docx                            (future sub-project)
└──> [Human Review Gate]                                   (future sub-project — new engine capability)
└──> Convert reviewed .docx to .xlsx (final layout)         (future sub-project)
```

`CLAUDE.md` proposed a new architecture from scratch (Pydantic `BaseWorkflowNode`
ABCs, SQLAlchemy async, a mock-mode framework) to build this. That would
duplicate `00_System/workflow_engine.py`, which already is a working,
general-purpose node-graph workflow engine — it runs saved Workflow Builder
diagrams node-by-node, supports dry-run mode, `{{node_id}}` token-passing
between steps, loop-back "Review Gate" nodes with attempt limits, and already
has function nodes for Word/PDF/JSON import-export, a Gemini "ask" node, and
a Copilot "ask" node.

**Decision:** extend the existing engine rather than build a parallel one.
Since there is no live Gemini Enterprise/NotebookLM API or MCP access today,
the new adapter is built mock-mode-first (per `CLAUDE.md`'s mocking
guidelines) — real interface and call shape now, real backend swapped in
later purely inside the adapter file.

This spec covers **sub-project 1 only**: the NotebookLM adapter and its 3 new
workflow node types, ending at `stem.json` (mocked) production. The
docx-conversion, human-review-gate, and final-xlsx steps are separate future
sub-projects, each getting their own spec/plan cycle.

## Bug fixed in passing

`workflow_engine.py`'s existing Gemini/Copilot-backed function nodes (`_ask_copilot`,
`_ask_copilot_agent`, `_generate_image_copilot`, `_list_copilot_agents`,
`_ask_gemini`, `_generate_image_gemini`) all call:

```python
self.router.execute_app_logic("05_Processes", "gemini_bridge", [payload])
```

`CATEGORY_DIR_MAP["05_Processes"]` is `"11_Processes"`, but `gemini_bridge.py`
and `copilot_bridge.py` physically live under `14_Adapters/`. Real
(non-dry-run) execution of any of these nodes currently fails with a routing
error; this has gone unnoticed because `dry_run=True` is the default and
short-circuits before ever reaching that call. Fixed to `"08_Adapters"` as
part of this change, since the new NotebookLM dispatch calls sit right next
to the buggy ones and must not copy the mistake.

## New Adapter: `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`

Same CLI contract as `gemini_bridge.py`: one JSON payload argument in,
exactly one JSON line of output, `main()` dispatches on `action`.

```python
MOCK_MODE = os.environ.get("NOTEBOOKLM_MOCK_MODE", "1") != "0"  # default on
```

### Actions

* **`create_notebook`** — params: `title`. Mock: generates a fake
  `notebook_id` (e.g. `nb_<uuid4 hex[:12]>`). Returns
  `{"success": true, "notebook_id": ..., "title": ...}`.
* **`upload_sources`** — params: `notebook_id`, `file_paths` (list). Mock
  still validates every path in `file_paths` actually exists on disk (a real
  usage mistake should still surface even in mock mode — matches
  `CLAUDE.md`'s "realistic data contracts" principle) and returns
  `{"success": true, "sources": [{"source_id": ..., "filename": ..., "status": "processed"}, ...]}`.
* **`ask`** — params: `notebook_id`, `prompt`. Mock returns a clearly-labeled
  placeholder answer: `{"success": true, "response": "[MOCK NotebookLM response] ..."}`.
* **`prompt_loop`** — params: `notebook_id`, `prompts` (list of strings).
  Mock loops the same mock-ask logic per prompt. Returns
  `{"success": true, "qa_pairs": [{"prompt": ..., "response": ...}, ...]}`.

When `MOCK_MODE` is `False`, every action returns
`{"success": false, "response": "NotebookLM API/MCP access is not configured yet..."}`
rather than pretending to succeed (graceful degradation, per `CLAUDE.md`
principle 4).

`14_Adapters/notebooklm_bridge/notebooklm_bridge.md` documents it, matching
every other adapter/task's companion doc convention.

## `workflow_engine.py` changes

3 new private helpers, mirroring `_ask_gemini`'s dry-run/real-dispatch shape:

* `_create_notebooklm_notebook(title) -> str` (JSON text)
* `_upload_notebooklm_sources(notebook_id, file_paths) -> str` (JSON text)
* `_run_notebooklm_prompt_loop(notebook_id, prompts) -> str` (JSON text, the
  `qa_pairs` array — this is what becomes `stem.json`)

Each dispatches via
`self.router.execute_app_logic("08_Adapters", "notebooklm_bridge", [payload])`
and parses the result with the existing `_parse_bridge_json`.

3 new `tool_id` branches in `_execute_function_node`:

* `function_notebooklm_create` — params: `title` (token-substituted).
* `function_notebooklm_upload_sources` — params: `notebook_id` (token-substituted;
  if blank, pulled from upstream JSON via a small `_extract_json_field(text, key)`
  helper so it can chain directly from a Create node), `file_paths`
  (newline-separated, token-substituted).
* `function_notebooklm_prompt_loop` — params: `notebook_id` (same resolution
  as above), `prompts` (newline-separated, token-substituted).

`function_notebooklm_prompt_loop`'s output feeds directly into the existing
`function_export_json` node to write `stem.json` — no new export node needed.

Deriving prompts automatically from `cg.json`'s internal structure is
explicitly **out of scope** here — `prompts` is user-supplied text (with
token substitution, so it can reference upstream node output) rather than
algorithmically generated from curriculum topics. That mapping is a separate
design question for whichever future sub-project wires this into the full
example pipeline.

## `server.py` changes

3 new entries in `FUNCTIONS_REGISTRY` (`tool_id`/`title`/`description`),
matching the shape of every existing entry, so the new nodes are
discoverable in the Workflow Builder's node palette
(`/api/workflow-builder/node-registry`).

## `workflow-builder.html` changes

3 new entries in `FUNCTION_FIELD_SCHEMAS` — the existing declarative
field-schema mechanism every function node's config panel already uses.
No new template/partial files needed.

```js
function_notebooklm_create: [
    { key: "title", label: "Notebook Title", type: "text", placeholder: "e.g. Electrician Curriculum Review" },
],
function_notebooklm_upload_sources: [
    { key: "notebook_id", label: "Notebook ID (optional if chained from Create)", type: "text", mono: true },
    { key: "file_paths", label: "File Paths (one per line)", type: "textarea", mono: true, placeholder: "C:\\...\\source1.pdf\nC:\\...\\source2.docx" },
],
function_notebooklm_prompt_loop: [
    { key: "notebook_id", label: "Notebook ID (optional if chained from Create)", type: "text", mono: true },
    { key: "prompts", label: "Prompts (one per line)", type: "textarea", placeholder: "What are the key topics in Period 1?" },
],
```

## Testing

* A small `test_notebooklm_bridge.py` (assert-based, no framework, matching
  `12_Tasks/import_documents/test_import_documents.py`'s existing convention)
  exercising `create_notebook` → `upload_sources` → `prompt_loop` in mock
  mode.
* Manual `WorkflowEngine(dry_run=False)` run of a 3-node graph
  (create → upload → prompt_loop → export_json) to confirm real (mock-mode)
  end-to-end dispatch through `CoreRouter`, not just dry-run placeholders.

## Explicitly Out of Scope (future sub-projects)

* Real Gemini Enterprise/NotebookLM API or MCP wiring (adapter is mock-only
  for now, by explicit decision).
* `stem.json` → `.docx` conversion.
* The human-review-gate engine capability (pause workflow, human edits a
  real file, resume) — a new node kind, not a variant of the existing
  AI-judged Review Gate.
* Reviewed `.docx` → final-layout `.xlsx` conversion.
* Any M365/Power Platform/Copilot Premium agent adapters beyond the existing
  `copilot_bridge`.
* Automatically deriving NotebookLM prompts from `cg.json`'s structure.
