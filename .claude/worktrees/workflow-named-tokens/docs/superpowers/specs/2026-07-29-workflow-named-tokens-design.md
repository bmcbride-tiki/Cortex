# Workflow Builder Named Tokens — Design Spec

**Date:** 2026-07-29
**Status:** Approved by user, ready for implementation plan

## Background

`workflow_engine.py` already threads data between Workflow Builder nodes via
`{{node_id}}` token substitution (`_substitute_tokens`, `TOKEN_PATTERN`):
whatever text a node produces is stored keyed by that node's raw,
auto-generated Drawflow node ID, and any later node can reference it by
writing `{{that_node_id}}` into one of its own settings.

Two gaps surfaced while designing the exam-question generation pipeline
(Curriculum Guide → TOS → NotebookLM prompt loop → exam questions):

1. **Node IDs aren't human-friendly.** There's no UI today to discover what
   a given node's ID even is, so referencing it means guessing or inspecting
   the saved graph directly.
2. **Multi-input nodes can't disambiguate.** When a node has more than one
   direct upstream connection, `_gather_upstream_text` currently
   concatenates *all* of their outputs together — there's no way to pick
   just one specific upstream source (e.g. a node fed by both a "TOS" step
   and a "Prompts" step needs to tell them apart).

Every node already has an editable display title on the canvas (e.g.
containers have a "Save Name" control), just not one used as a token today.

## Decisions

* **Token name = the node's existing title field** (not a separate
  "output variable name" field). Renaming a node on the canvas is renaming
  its token.
* **New single-brace syntax `{Name}` coexists with today's `{{node_id}}`**
  — both keep working side by side. Nothing already saved breaks.
* **`{input}` is a reserved literal token**, always available, resolving to
  "every direct-upstream node's output, concatenated" — the exact same
  value `_gather_upstream_text` already computes today for the current
  blank-field auto-fill behavior. It now also works inline, mixed with
  other text in a field, not just as a whole-field default.

## Architecture (`workflow_engine.py`)

1. Build a `title_to_node_id: Dict[str, str]` map once during graph
   parsing — one entry per node with a non-empty title. As a
   defense-in-depth safety net (primary enforcement is in the UI, see
   below), the engine raises a clear `WorkflowRunError` at run start if it
   ever finds two nodes sharing a title.
2. `_substitute_tokens` gains an `upstream_text` argument and now resolves
   text in three passes, in order:
   1. Literal `{input}` → `upstream_text`.
   2. Single-brace `{Name}` → `title_to_node_id` lookup → `self.context`.
   3. Existing double-brace `{{node_id}}` → `self.context` (unchanged).
   A lookaround-protected regex for the single-brace pass —
   `(?<!\{)\{([^{}]+)\}(?!\})` — stops it from misfiring on the inner text
   of a `{{...}}` pair, so both syntaxes safely coexist in the same string.
3. Every existing call site that calls `_substitute_tokens(text)` gets
   `upstream_text` threaded through. It's already a local variable in
   scope at each call site today (computed once near the top of
   `_execute_node`), so this is mechanical — no behavior change for
   existing `{{node_id}}` usage.
4. Container flattening keeps each node's `title` attached through the
   rewire, so name-based tokens keep resolving correctly after a container
   is flattened into the main graph.

## UI (`workflow-builder.html`)

1. **Duplicate-title validation.** Saving a node's title checks it against
   every other node's title on the canvas; a duplicate blocks the save
   with an inline error (e.g. "A node named 'TOS' already exists — choose
   a different name").
2. **Autocomplete.** Typing `{` in any text/textarea param field opens a
   small suggestion list: `{input}` always first, then one entry per other
   titled node on the canvas. Selecting one inserts `{ThatTitle}` at the
   cursor.
   * Scope is deliberately "every titled node on the canvas," not just
     direct upstream ones — this matches how token lookup already works
     today: any node whose output has already landed in `self.context` by
     the time this node runs is resolvable, direct predecessor or not.
     Picking one that hasn't executed yet at that point in the graph just
     resolves to `""`, the same graceful-degradation behavior tokens
     already have.

## Testing

No test file exists yet for `workflow_engine.py`. Add a small, assert-based
`test_workflow_engine.py` (no framework, matching this project's existing
test convention) covering:

* Single-brace `{Name}` resolves via title lookup.
* Literal `{input}` resolves to concatenated direct-upstream output.
* Both syntaxes coexisting in one string resolve independently and
  correctly (double-brace pass doesn't get clobbered by the single-brace
  pass or vice versa).
* Duplicate titles raise `WorkflowRunError` at run start.

## Explicitly Out of Scope

* Renaming/aliasing a token independently of the node's display title (the
  "separate dedicated field" option was considered and declined).
* Restricting autocomplete suggestions to true graph ancestors of the
  current node (deferred — current scope is "every titled node," matching
  existing token-resolution behavior).
* Any change to how `{{node_id}}` itself resolves — it's untouched, just
  joined by the new single-brace syntax.
