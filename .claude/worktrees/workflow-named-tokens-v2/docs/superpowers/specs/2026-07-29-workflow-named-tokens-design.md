# Workflow Builder Named I/O Tokens — Design

**Supersedes:** an earlier same-day version of this spec (title-based tokens, single-brace `{Name}` syntax, global scope across the whole graph, silent-empty on unresolved tokens, marked "Approved by user, ready for implementation plan") and its resulting unexecuted plan at `docs/superpowers/plans/2026-07-29-workflow-named-tokens.md` (no checkboxes checked, no files created). Both are deleted as part of this spec. Revisiting the same problem surfaced a different, more detailed use case (multi-input nodes that must never silently cross-wire) that argues for connection-scoped, hard-failing resolution instead. The old spec's `{`-triggered autocomplete UX idea is carried forward in adapted form.

## Goal

Let a Workflow Builder node output be given a custom, human-readable label (e.g. `CG-JSON`, `CG-Weighting`) that downstream nodes reference explicitly as `{{label}}` in their own settings fields, with the builder UI showing which labels are actually available (i.e. directly wired in) to the node currently selected. This replaces referencing outputs by raw, meaningless Drawflow node IDs.

This spec covers the token/labeling **engine and builder UI only**. It deliberately does not cover: the specific "Create Notebook LM" / "Prompt Builder" / "Run Notebook Prompt" node logic from the motivating example (trade+year extraction, block-splitting, weighting math, runtime multiplier prompt, timed dispatch) — those are separate future Task builds that will simply consume this token system, the same way every existing Task/Function/Adapter is invoked. It also doesn't cover the separately-requested "run the process map through Claude" gap-analysis feature, which needs its own spec (different technical surface — an LLM API call, not a data-flow mechanism) once real API wiring exists.

## Architecture

**Approach:** extend the existing engine in place — no new storage layer, no parallel token syntax.

- A custom **label** lives on each node's existing Drawflow `data` object (`workflow_engine.py:167-175` already reads `title`, `kind`, `params`, etc. from this same dict — `label` is added the same way, one more key).
- `WorkflowEngine.context` (`workflow_engine.py:127`) is keyed by **label** instead of node ID (currently keyed by node ID at the assignment `self.context[node_id] = output_text`, `workflow_engine.py:608`).
- Substitution is **scoped to direct connections only**, using `backward_edges` (`workflow_engine.py:132`, already computed by `_parse_graph` at line 141-189 and stored per run at line 580 — currently computed but never used to restrict substitution, only to find entry nodes and gather implicit upstream text).
- The existing `{{name}}` syntax and `TOKEN_PATTERN` regex (`workflow_engine.py:96`) are **reused as-is** — labels satisfy the same `[a-zA-Z0-9_\-]+` pattern already in place. No second brace syntax, no back-compat shim: there are no saved workflows yet to migrate (confirmed), so this is a direct behavior change, not an addition alongside the old one.

Considered and rejected: a separate workflow-level `{node_id: label}` registry independent of Drawflow's own node data. Rejected because it's a second source of truth that must stay in sync with Drawflow's existing export/import for no benefit over storing `label` directly in the node's own `data`.

## Behavior changes

1. **Context keying**: `self.context[node_id] = output_text` → `self.context[label] = output_text`, where `label` defaults to an auto-generated value (see below) if the user never renamed it.

2. **Scoped, hard-failing substitution**: `_substitute_tokens` (`workflow_engine.py:258-266`) changes from an unscoped `self.context.get(m.group(1), "")` lookup (silently returns `""` for anything unresolved, and can resolve *any* node's label regardless of wiring) to a per-node scoped lookup built from that node's `backward_edges` entries only. A `{{label}}` reference to anything outside that direct-predecessor set — whether the label doesn't exist at all, or exists on a node that isn't directly wired in — raises `MissingInputError(label)`. This is already caught by the existing per-node `try/except` in `run()` (`workflow_engine.py:613-617`) and reported as `status: "failed"`, `output: str(e)` — no new error-handling path, just a more specific exception than whatever occurred before (nothing did — it silently produced blank text).

3. **No implicit passthrough**: `_gather_upstream_text` (`workflow_engine.py:268-274`) is deleted. Its current call site at `_execute_node` (`workflow_engine.py:478`) and the `upstream_text` parameter threaded through `_execute_function_node` and its helpers go with it, **except** where "operate on whatever is directly connected" is a node type's entire defined purpose and it has no alternative settings field for that purpose — `function_concatenate` (`workflow_engine.py:511`, already reads `backward_edges` directly rather than calling `_gather_upstream_text`), `_run_logic_gate` (`workflow_engine.py:407-427`, the condition is evaluated *against* the connected input, that's the node's whole job), `_run_review_gate` (`workflow_engine.py:431-459`, same — it judges the connected input against criteria), and **skill nodes** (`_execute_node`'s `kind == "skill"` branch, `workflow_engine.py:489-491` — confirmed via `renderSkillPanel`, `workflow-builder.html:503-508`, that skill nodes have zero configurable fields; their fixed description plus "whatever upstream text flows in" is their only, by-design input mechanism, stated in the UI's own help text). Those four keep reading directly-connected node output as their core mechanic; nothing about labels changes how they work.

   What *does* change: the AI-prompt nodes (`function_google_search`, `function_gemini_ask`, `function_claude_ask`, `function_chatgpt_ask` — `workflow_engine.py:518-537`) currently auto-append whatever's upstream to the "instructions" field's content regardless of whether the user references it explicitly. Going forward, if a node's prompt should include upstream content, the user places `{{label}}` inside the "instructions" field text explicitly — nothing is auto-appended.

   Also changing: `_extract_json_field` (`workflow_engine.py:360-370`)'s use as an **automatic fallback when a field is left blank** (`function_notebooklm_upload_sources` / `function_notebooklm_prompt_loop`, `workflow_engine.py:550,560` — `self._substitute_tokens(params.get("notebook_id", "")) or self._extract_json_field(upstream_text, "notebook_id")`) goes away as a fallback. Instead, `_extract_json_field`-style parsing is applied to whatever value the explicit `{{label}}` token resolves to for that field — i.e. the user must explicitly bind `{{CreateNotebookLabel}}` into the `notebook_id` field, and if that upstream node's captured output is a JSON blob rather than a bare ID, the field's own handling still extracts `notebook_id` from it. The convenience is preserved; only the "field left blank → silently guess from whatever's connected" behavior is removed.

4. **Auto-generated, always-editable labels**: a node gets a default label (`"{tool_id}_{n}"`) the moment it's placed on the canvas — it's immediately usable downstream without the user doing anything. Renaming it later is just relabeling the same token.

5. **Duplicate labels auto-suffix** (`_2`, `_3`, …) rather than blocking — creation/rename never stalls on a naming collision.

6. **Rename cascades live, client-side**: editing a node's label rewrites every `{{oldLabel}}` occurrence to `{{newLabel}}` across every other node's settings, in the browser's in-memory Drawflow graph, immediately — no server round-trip, since Drawflow already lives entirely client-side until Save.

## Builder UI (`workflow-builder.html`)

- **Label field**: new input at the top of the node settings panel, prefilled with the auto-generated default, editable anytime. (Every node gets this — not a container-only control.)
- **Input(s) panel**: read-only list showing only the labels of nodes with a direct edge into the currently selected node (Drawflow already exposes each node's own incoming connections client-side — no new graph-walking needed beyond what `_parse_graph`'s backward-edges logic already does server-side).
- **Insertion**: both work — type `{{label}}` freehand in any text/textarea field, or click a label in the Input(s) panel to insert `{{label}}` at the field's current cursor position. (Adapted from the superseded spec's `{`-triggered autocomplete idea: triggering the same dropdown on typing `{{` is a reasonable enhancement, scoped to only the connected labels rather than every node in the graph — left as an implementation detail for the plan, not a hard requirement.)
- **Failure feedback**: `wfbRun`'s existing step-handling loop (`workflow-builder.html:1219-1222`) already receives `data.steps` with per-node `status`/`output` from the server. It gains: for any `step.status === "failed"`, find that node's DOM element and apply a red-outline CSS class plus a tooltip (`title` attribute) set to `step.output` — which is already the raw `MissingInputError` message (`"Missing input value: {{label}}"`), so no new message formatting is needed. Outline clears on the node's next run or edit. This applies uniformly whether triggered by a dry run or a live run — both already flow through the same `/api/workflow-builder/run` endpoint and `data.steps` shape.

## Testing

This repo has no top-level `tests/` directory; its actual convention is a co-located `test_<module>.py` file run directly (see `00_System/test_model_classifications.py`, `00_System/sandbox_smoke_test.py`). This spec follows that convention rather than introducing a new one:

- `00_System/test_workflow_engine_tokens.py` — plain assert-based, run via `python test_workflow_engine_tokens.py`, no fixtures/mocks (pure in-memory graph logic against the real `WorkflowEngine`). This covers only the Python engine's scoped-substitution behavior, since label generation, duplicate-suffixing, and rename-cascade are all client-side JS with no Python surface to test:
  1. A label resolves correctly when its node is a direct predecessor.
  2. A label that exists elsewhere in the graph but isn't a direct predecessor raises `MissingInputError`.
  3. A nonexistent label raises `MissingInputError`.
- Everything client-side — the Label field, Input(s) panel, click-to-insert, duplicate auto-suffix, rename cascade, and red outline/tooltip — has no browser test harness in this repo. It will be verified by running the app and using the builder directly, not claimed from reading the code.

## Explicitly out of scope

- The specific smart node implementations from the motivating example (JSON extraction, block-splitting, weighting math, runtime multiplier prompt, timed dispatch) — future Task builds.
- The in-app "run the process map through Claude" gap-analysis feature — future spec, depends on real LLM API wiring.
- Any migration path for pre-existing saved workflows — none exist yet.
