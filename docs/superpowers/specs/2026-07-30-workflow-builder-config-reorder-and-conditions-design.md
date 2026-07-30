# Workflow Builder: Node Config Reorder & Conditions Node — Design

## Goal

Two independent, small changes to the Workflow Builder (`00_System/templates/workflow-builder.html`, `00_System/workflow_engine.py`, `00_System/server.py`):

1. Reorder the right-hand "Node Configuration" panel so **Input(s)** is the top section, node-specific settings stay in the middle, and **Output Label** moves to the bottom (currently: Output Label → Input(s) → settings).
2. Add a new **Conditions** Function node: single input, up to 10 conditions (each either a simple field/operator/value rule or a free-form expression, chosen per-condition), each condition routing to its own "Go To" target node, a node-level toggle for whether the first matching condition wins or every matching condition fires, and a mandatory Default target for when nothing matches.

## Part 1 — Node Configuration panel reorder

**Current structure** (`workflow-builder.html:89-108`):
- `#wfb-panel-header` (one block, shown/hidden together) contains Output Label (93-100) then Input(s) chips (101-104).
- `#wfb-panel-body` (settings, injected per node type) comes after.

Because the desired order interleaves the settings panel *between* Input(s) and Output Label, this isn't a pure reorder — `#wfb-panel-header` has to be split into two independent blocks so `#wfb-panel-body` can sit between them in the DOM:

- `#wfb-panel-inputs-section` — Input(s) chips only — placed immediately before `#wfb-panel-body`.
- `#wfb-panel-label-section` — Output Label input + Save button only — placed immediately after `#wfb-panel-body`.

Both currently toggle visibility as one unit via `.hidden` in two places: `selectNode()` (`workflow-builder.html:1183-1184`, shows on node select) and `clearPanel()` (`workflow-builder.html:1208`, hides on deselect). Both call sites change from touching one `#wfb-panel-header` element to toggling both new section IDs together. No other JS references `#wfb-panel-header` by id (confirmed — it's only used at definition, line 1183, and line 1208), and nothing depends on DOM position for the label input or inputs box, only their own element ids (`#wfb-panel-label-input`, `#wfb-panel-inputs`) — so this is a safe, contained change.

No change to `wfbSaveLabel()`, `renderInputsChips()`, or any panel-rendering function — they already look up elements by id, not position.

## Part 2 — Conditions node

### Why extend `function_logic_gate` instead of building real multi-port nodes

The builder already has a working If/Else node (`function_logic_gate`) that branches without needing multiple Drawflow output handles. Every function node execution returns `Tuple[str, Optional[str]]` = `(output_text, jump_to_node_id)`; in `run()` (`workflow_engine.py:696-767`), when `jump_to` is truthy the engine queues **only that node** next (`queue.insert(0, jump_to)`, line 759) instead of following canvas edges (line 764) — branching is a lookup, not a wire. `_run_logic_gate` (`workflow_engine.py:481-502`) picks one of two node IDs from a param dict (`true_node_id`/`false_node_id`), populated by two "Go To" `<select>` dropdowns in `renderLogicGatePanel` (`workflow-builder.html:1128-1151`) built from `otherCanvasNodes()` (line 971), which lists every other node on the canvas by title — no drawn connection required.

Conditions is the same mechanism generalized from 2 named targets to a list of up to 10, plus a default. Building real multi-handle output ports instead would require touching Drawflow's `addNode` port count (currently hardcoded `1, 1` at `workflow-builder.html:420` for every node), port CSS, and drag-connection handling — a much larger change for an outcome the existing jump_to mechanism already produces.

### Param shape

```json
{
  "match_mode": "first_match",
  "default_target_node_id": "12",
  "conditions": [
    {
      "mode": "simple",
      "field": "status",
      "operator": "equals",
      "value": "approved",
      "target_node_id": "7"
    },
    {
      "mode": "expression",
      "expression": "total > 1000 and region == 'west'",
      "target_node_id": "9"
    }
  ]
}
```

- `match_mode`: `"first_match"` (evaluate rows top-to-bottom, stop at the first true one — switch-style) or `"all_matches"` (evaluate every row, collect every true one). Default `"first_match"`.
- `conditions`: 0-10 rows, each independently `mode: "simple"` or `mode: "expression"` — this is a per-condition choice, not a node-level one, matching the Power Automate-style mixed usage requested.
- `default_target_node_id`: required. Used when zero conditions match (in both match modes).
- Simple-mode `operator` set: reuses `function_logic_gate`'s three (`contains`, `equals`, `regex`) plus four numeric comparisons needed for real branching logic: `gt`, `gte`, `lt`, `lte` (numeric-parse both sides; a non-numeric value fails that condition rather than raising, consistent with "a condition that can't be evaluated just doesn't match").
- Simple-mode `field`: if blank, the whole upstream text is tested (identical to `function_logic_gate`'s behavior against `condition_value`). If set, the field is looked up in the upstream text parsed as a JSON object; if upstream text isn't valid JSON or lacks that key, the condition evaluates to false rather than erroring — a single misconfigured condition shouldn't halt the whole node when other conditions or the default can still resolve it.

### Expression mode — safe evaluator, stdlib only

A user-authored expression (`total > 1000 and region == 'west'`) must never be handed to `eval()` — that's arbitrary code execution from data the workflow author typed into a form. No dependency is added for this (no `simpleeval`/`asteval` in `requirements.txt` today, and none is needed): a new `_eval_condition_expression(expr: str, namespace: Dict[str, Any]) -> bool` in `workflow_engine.py` parses with `ast.parse(expr, mode="eval")` and walks the tree accepting only a fixed whitelist — `BoolOp` (`and`/`or`), `UnaryOp` (`not`), `Compare` with `Eq/NotEq/Lt/LtE/Gt/GtE/In/NotIn`, `Name` (resolved against `namespace` only), and literal `Constant`. Anything else (`Call`, `Attribute`, `Subscript`, imports, comprehensions, etc.) raises `WorkflowRunError` naming the disallowed construct — the same failure path every other misconfigured node already uses, no new error handling.

`namespace` is built from the upstream text: if it parses as a JSON object, each key is exposed as a variable; the raw upstream text is always additionally exposed as `input`. A `Name` not found in `namespace` raises `WorkflowRunError` (mirrors `MissingInputError`'s "tell the user exactly what's missing" style) rather than silently evaluating to `None`.

### Engine

`_run_conditions(node_id: str, params: Dict[str, Any]) -> Tuple[str, Optional[Union[str, List[str]]]]` in `workflow_engine.py`, alongside `_run_logic_gate` (dispatched from `_execute_function_node`, next to the `function_logic_gate` branch at line 590-591):

- Gathers `upstream_text = self._gather_upstream_text(node_id)` (same as logic_gate) and attempts `json.loads` once for simple-mode field lookups and expression-mode namespace.
- Iterates `conditions` in order (capped at 10 — extra rows beyond 10 are ignored defensively, though the UI never creates them), evaluating each per its `mode`.
- `first_match`: returns `(verdict, matched.target_node_id)` at the first true condition, or `(verdict, default_target_node_id)` if none match — single string, identical shape to today's `jump_to`.
- `all_matches`: collects every true condition's `target_node_id` in order; returns `(verdict, [ids...])` if non-empty, else `(verdict, default_target_node_id)`.
- `verdict` is a short human-readable summary (e.g. `"3 of 4 conditions matched (all_matches): -> node 7, node 9, node 12"` or `"Condition 2 matched (first_match): -> node 9"` or `"No condition matched -> default (node 3)"`) — same role as logic_gate's verdict string, shown in the run log.

**`run()` change** (`workflow_engine.py:756-759`): `jump_to` becomes `Optional[Union[str, List[str]]]` everywhere it's threaded (`_execute_node`, `_execute_function_node` return-type annotations only — every other handler keeps returning a plain `Optional[str]`, which is still valid under the widened type). At the one consuming site:
```python
if jump_to:
    if isinstance(jump_to, list):
        queue[0:0] = jump_to
    else:
        queue.insert(0, jump_to)
```
Order is preserved (first matched condition's target runs first). No other part of `run()` changes — `_pick_next`'s dependency-wait logic already just consumes whatever is in `queue`.

### Registry & icon

- `server.py` `FUNCTIONS_REGISTRY` (after `function_logic_gate`, ~line 221): `{"tool_id": "function_conditions", "title": "Conditions", "description": "Evaluates up to 10 conditions (simple rules or expressions) against upstream data and branches to each one's target node; supports first-match or all-matches, with a required default.", "model": None}`.
- `TOOL_FA_ICON_MAP` (`server.py:435` area): `"function_conditions": "fa-code-branch"`.

### UI (`workflow-builder.html`)

`renderConditionsPanel(nodeId, data)`, dispatched from `renderFunctionPanel` alongside the existing `function_logic_gate` check (line 1155), modeled on `renderLogicGatePanel` but with repeatable rows:

- **Match Mode** — a two-option `<select>` (`First Match Wins` / `All Matches Fire`) at the top, backing `match_mode`.
- **Condition rows** — starts with 1 row, "+ Add Condition" button appends more up to 10 (button disables/hides at 10), each row has a small "×" remove button. Each row: a Simple/Expression mode toggle; Simple shows Field (text input, placeholder "leave blank to test the whole input"), Operator (`<select>`: Contains/Equals/Regex/Greater Than/Greater or Equal/Less Than/Less or Equal), Value (text input); Expression shows one text input for the expression string. Every row ends with its own "Go To" `<select>`, built via the same `nodeOptions()` closure pattern already in `renderLogicGatePanel` (line 1132-1133).
- **Default — Go To** — one more `<select>` at the bottom, same `nodeOptions()` pattern, no "-- None --" default value accepted: `wfbSaveNodePanel`'s `"conditions"` branch blocks save with `alert(...)` if left empty, the same inline-validation style `wfbSaveLabel` already uses for empty/invalid labels (line 1083-1087) — consistent with the requirement that Default is mandatory, not optional.
- `body.dataset.readFn = "conditions"`; `wfbSaveNodePanel` (`workflow-builder.html:1245` area, new branch alongside `"logic-gate"`) reads `match_mode`, walks each row by a `data-condition-index` attribute to build the `conditions` array, and reads the default select — into the param shape above.

Rows are plain DOM elements re-rendered from `data.params.conditions` on open (same pattern the rest of this file already uses — no new client-side state container, no framework).

## Testing

Following this repo's existing convention (`00_System/test_model_classifications.py`, `00_System/sandbox_smoke_test.py` — co-located `test_<module>.py`, plain `assert`, run directly, no fixtures):

- `00_System/test_workflow_engine_conditions.py`:
  1. Simple mode, `first_match`: first true condition's target wins, later true conditions are never reached.
  2. Simple mode, `all_matches`: every true condition's target is returned, in order.
  3. No condition matches → `default_target_node_id` is returned, in both match modes.
  4. Expression mode: a boolean expression referencing parsed-JSON fields evaluates correctly.
  5. Expression mode, security boundary: an expression containing a disallowed construct (e.g. a function call) raises `WorkflowRunError` instead of executing anything.
  6. Numeric operators (`gt`/`gte`/`lt`/`lte`) on both matching and non-matching values.
- Client-side (row add/remove up to 10, mode toggle per row, save/read round-trip, mandatory-default validation) has no browser test harness in this repo (same as every other panel) — verified by running the app directly, not claimed from reading the code.
- Part 1 (panel reorder) is pure DOM/CSS with no Python surface — verified the same way, by running the app and selecting a node.

## Explicitly out of scope

- Real Drawflow multi-handle output ports / drawn branch wires — Conditions stays visually single-input/single-output like every other Function node; branching is via the "Go To" dropdowns, not canvas connections, exactly like `function_logic_gate` today.
- Nested/grouped boolean trees inside a single condition row (e.g. a visual AND/OR builder) — a condition is one simple rule or one expression string; `and`/`or` inside an expression already covers compound logic.
- Any change to how canvas nodes/edges are persisted (`database.py:328-332`'s single `graph_json` blob) — Conditions' params live in the node's existing `data.params`, same as every other Function node.
- Migrating any existing saved workflow — no existing workflow uses `function_conditions` since it doesn't exist yet.
