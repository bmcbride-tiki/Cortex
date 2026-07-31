# Variables & Loop Containers (Apply to Each / Do Until) — Design

## Goal

Add the two remaining Power Automate "Built-In" primitives the engine has no equivalent for: **named mutable Variables** (Initialize/Set/Increment/Append) and **loop execution** (Apply to Each / Do Until). Everything built in the previous slice (`docs/superpowers/specs/2026-07-30-flow-control-and-data-operations-design.md`) was additive to the existing single-pass DAG walker. This slice is not — it requires a real new engine capability: a named global variable store, and a way to run a sub-graph more than once at runtime.

Touches: `00_System/workflow_engine.py`, `00_System/server.py`, `00_System/templates/workflow-builder.html`.

## Part 1 — Variables: a genuinely new, separate store

Every other piece of state in this engine is keyed by node **label**, scoped to direct connections (`{{label}}` only resolves for a directly-wired predecessor). Power Automate's variables don't work that way: `Initialize Variable` creates a name once; separate `Set`/`Increment`/`Append Variable` nodes *elsewhere in the graph* — not the same node, not necessarily directly connected — mutate it by name, and anything anywhere downstream can read it by name. That's a fundamentally different addressing model, so it gets its own store: `self.variables: Dict[str, Any] = {}`, global for the whole run, not connection-scoped.

### Token syntax: `{{var.name}}`

The current token regex (`workflow_engine.py:100`) is `\{\{\s*([a-zA-Z0-9_\-]+)\s*\}\}` — no dot allowed, which also matches what `workflow-builder.html`'s `wfbSaveLabel` enforces on labels today. Widening it to `[a-zA-Z0-9_.\-]+` is a strict superset: no existing label can contain a dot, so a token containing a dot can *only* ever be a new reserved namespaced form, never collide with a real label. Two namespaces are reserved: `var.<name>` (this section) and `loop.item` / `loop.index` (Part 2).

`_substitute_tokens` (`workflow_engine.py:370-396`) changes from "look up in `_current_scope`, else `MissingInputError`" to:
1. If the name starts with `var.`: look up `self.variables.get(name[4:], _MISSING)`. Found → render via `_array_item_to_text` (already handles dict/list/scalar/None correctly — reused, not reinvented). Not found → `WorkflowRunError(f"Unknown variable: {name} -- initialize it with an Initialize Variable node first.")` (not `MissingInputError`; this isn't a wiring problem, it's a real name lookup, so it gets its own message rather than borrowing the "isn't directly connected" language).
2. Else if the name is `loop.item` or `loop.index`: see Part 2.
3. Else: existing `_current_scope` / `MissingInputError` behavior, unchanged.

### The four Variable nodes

All are `kind: "function"`, dispatched in `_execute_function_node`. All read/write `self.variables`, and additionally return their own new value as their normal node output (so a Variable node can *also* be referenced positionally via `{{label}}` by whatever's directly wired to it — two ways to reach the same value, matching how Power Automate's variable actions have both a name-addressable value and a normal action output).

| tool_id | params | Behavior |
|---|---|---|
| `function_initialize_variable` | `{"name": str, "type": "String"\|"Number"\|"Boolean"\|"Array"\|"Object", "value": str}` | `WorkflowRunError` if `name` is already in `self.variables` (catches copy-paste mistakes — Power Automate itself rejects duplicate variable names at save time). `value` is token-substituted, then coerced per `type`: String → as-is; Number → `float(value)`; Boolean → `value.strip().lower() in ("true", "1", "yes")`; Array/Object → `json.loads(value)` (`WorkflowRunError` on invalid JSON, naming the type). Sets `self.variables[name]`. |
| `function_set_variable` | `{"name": str, "value": str}` | `WorkflowRunError` if `name` not yet initialized. `value` substituted; `json.loads` attempted for type fidelity (so setting an array/object/number stays that type), falls back to the raw string on parse failure. Overwrites `self.variables[name]`. |
| `function_increment_variable` | `{"name": str, "increment_by": str}` (default `"1"`) | `WorkflowRunError` if `name` not initialized or current value isn't numeric (`float()`-parseable). `new = float(current) + float(increment_by)`; stored as `int(new)` if `new.is_integer()` else `new` (keeps whole-number counters looking like counters, not `3.0`). |
| `function_append_variable` | `{"name": str, "value": str}` | `WorkflowRunError` if `name` not initialized or current value isn't a `list`. `value` substituted, `json.loads` attempted (so appending an object/array/number works, not just strings) falling back to the raw string. `self.variables[name].append(...)` in place. |

Field schemas (all fit the existing declarative `FUNCTION_FIELD_SCHEMAS` table):
```javascript
function_initialize_variable: [
    { key: "name", label: "Name", type: "text", mono: true },
    { key: "type", label: "Type", type: "select", options: ["String", "Number", "Boolean", "Array", "Object"] },
    { key: "value", label: "Value", type: "textarea", mono: true },
],
function_set_variable: [
    { key: "name", label: "Name", type: "text", mono: true },
    { key: "value", label: "Value", type: "textarea", mono: true },
],
function_increment_variable: [
    { key: "name", label: "Name", type: "text", mono: true },
    { key: "increment_by", label: "Increment By", type: "text", mono: true, placeholder: "1" },
],
function_append_variable: [
    { key: "name", label: "Name", type: "text", mono: true },
    { key: "value", label: "Value", type: "textarea", mono: true },
],
```

## Part 2 — Loop containers: Apply to Each / Do Until

### Why extend Container instead of a new node type

Per your call: these reuse the existing `Container` node visually (drag it, double-click to open its own collapsible sub-diagram — same UX as today) rather than introducing a new canvas interaction. What changes is *execution*: today, `_flatten_containers` (`workflow_engine.py:285-343`) permanently splices every container's inner steps into the main flow **once**, at graph-parse time, before anything runs. A loop container's inner steps instead need to run **more than once at runtime** — once per array item (Apply to Each) or until a condition holds (Do Until) — which flatten-and-splice fundamentally can't express: there's no "the graph" to splice into more than once.

A container becomes a loop container via a new `params.loop_type` field (`"apply_to_each"` | `"do_until"`, absent/`None` = today's plain grouping behavior — fully backward compatible with every existing saved workflow, since none of them can have this field set).

### Engine: extracting loop bodies instead of flattening them

New engine state: `self.loop_subgraphs: Dict[str, Dict[str, Any]] = {}` (populated during parse, one entry per loop container: its own private `nodes`/`forward_edges`/`backward_edges`/`entry_ids`/`exit_ids`) and `self.loop_stack: List[List[Any]] = []` (a stack, so nested loops resolve `{{loop.item}}`/`{{loop.index}}` to the innermost enclosing loop — each frame is `[current_item, current_index]`).

`_flatten_containers` gains a **Step A** that runs before its existing splice-loop (which becomes Step B, unchanged except its filter now explicitly excludes loop containers):

```python
def _flatten_containers(self, nodes, forward_edges, backward_edges, module_nodes):
    # Step A: pull every loop container's inner module OUT of the shared graph
    # into its own private, self-contained subgraph -- recursively flattening
    # that private copy first, so anything nested inside a loop's body (a
    # plain container, or another loop) resolves correctly before the loop
    # itself is treated as one opaque node by whatever contains it.
    loop_container_ids = [
        nid for nid, n in nodes.items()
        if n.get("kind") == "container" and (n.get("params") or {}).get("loop_type")
    ]
    for cid in loop_container_ids:
        module_name = nodes[cid].get("module_name")
        inner_ids = [nid for nid in module_nodes.get(module_name, []) if nid in nodes]
        sub_nodes = {nid: nodes[nid] for nid in inner_ids}
        sub_forward = {nid: list(forward_edges.get(nid, [])) for nid in inner_ids}
        sub_backward = {nid: list(backward_edges.get(nid, [])) for nid in inner_ids}
        self._flatten_containers(sub_nodes, sub_forward, sub_backward, module_nodes)  # recursive
        entry_ids = [nid for nid in sub_nodes if not sub_backward.get(nid)] or list(sub_nodes)[:1]
        exit_ids = [nid for nid in sub_nodes if not sub_forward.get(nid)] or list(sub_nodes)[-1:]
        self.loop_subgraphs[cid] = {
            "nodes": sub_nodes, "forward_edges": sub_forward, "backward_edges": sub_backward,
            "entry_ids": entry_ids, "exit_ids": exit_ids,
        }
        for nid in inner_ids:
            del nodes[nid]
            forward_edges.pop(nid, None)
            backward_edges.pop(nid, None)
        # The loop container node `cid` itself is NOT removed or rewired --
        # unlike a plain container, it stays in `nodes` as a real, single
        # executable unit; only its inner module's nodes are pulled out.

    # Step B: existing behavior, filter narrowed to exclude loop containers
    # (already fully handled by Step A above).
    while True:
        container_ids = [
            nid for nid, n in nodes.items()
            if n.get("kind") == "container" and not (n.get("params") or {}).get("loop_type")
        ]
        if not container_ids:
            break
        ...  # unchanged from workflow_engine.py:309-342
```

**Why recursion here is safe and sufficient:** module names are assigned uniquely per container instance at creation time (`workflow-builder.html:401`, `container_${Date.now()}_${counter}`), so no two containers' modules ever share a node id — a loop's `module_nodes[module_name]` lookup is unaffected by what happens to any sibling or ancestor container's own flattening. Processing every loop container's extraction independently, each against a private copy, means nesting order never matters: a loop-inside-a-loop resolves because the outer loop's recursive `_flatten_containers` call finds and extracts the inner loop from the private copy before the outer loop is finalized; a plain-container-inside-a-loop resolves the same way via Step B running on that same private copy.

### Dispatch: a new `kind == "container"` branch

Every node kind reaching `run()` today is `task`/`process`/`adapter`/`skill`/`function` — a plain container never survives to be dispatched (it's always fully spliced away before `run()` sees it). A loop container now does survive, so `_execute_node` (`workflow_engine.py:682-716`) gains one new branch, checked alongside the existing ones:

```python
if kind == "container":
    return self._execute_loop_container(node_id, node), None
```

```python
def _execute_loop_container(self, node_id: str, node: Dict[str, Any]) -> str:
    params = node.get("params") or {}
    loop_type = params.get("loop_type")
    subgraph = self.loop_subgraphs.get(node_id)
    if not subgraph or not subgraph.get("nodes"):
        raise WorkflowRunError(f"Loop container '{node.get('title', node_id)}' has no steps inside it.")

    if loop_type == "apply_to_each":
        items_text = self._substitute_tokens(params.get("items", ""))
        try:
            items = json.loads(items_text)
        except (TypeError, ValueError) as e:
            raise WorkflowRunError(f"Apply to Each: Items must be a JSON array: {e}")
        if not isinstance(items, list):
            raise WorkflowRunError(f"Apply to Each: Items must be a JSON array, got {type(items).__name__}.")

        results = []
        self.loop_stack.append([None, None])
        try:
            for index, item in enumerate(items):
                self.loop_stack[-1] = [item, index]
                results.append(self._run_loop_iteration(subgraph))
        finally:
            self.loop_stack.pop()
        return json.dumps(results, indent=2)

    if loop_type == "do_until":
        condition = params.get("condition", "")
        max_iterations = int(params.get("max_iterations") or 60)  # 60 matches Power Automate's own default
        results = []
        self.loop_stack.append([None, None])
        try:
            index = 0
            while index < max_iterations:
                self.loop_stack[-1] = [None, index]
                results.append(self._run_loop_iteration(subgraph))
                namespace = dict(self.variables)
                namespace["loop_index"] = index
                if _eval_condition_expression(condition, namespace):
                    break
                index += 1
        finally:
            self.loop_stack.pop()
        return json.dumps(results, indent=2)

    raise WorkflowRunError(f"Unknown loop_type: {loop_type!r} for container '{node.get('title', node_id)}'.")
```

`_run_loop_iteration(subgraph) -> str` runs one pass over the extracted private subgraph, reusing the existing `_pick_next` scheduler (`workflow_engine.py:795-838`, unchanged) and appending to the SAME `self.log`/`self.context` the top-level run uses -- so iteration steps show up in the run report exactly like any other step, `{{label}}` references to a loop-body node resolve engine-wide (each iteration overwrites that label's `self.context` entry, so a reference *after* the loop sees the *last* iteration's value -- the natural, expected behavior of a value produced inside a loop), and `MAX_TOTAL_STEPS` (`workflow_engine.py:103`) continues to guard the *whole run* including loop iterations for free, with no separate cap needed for Apply to Each itself:

```python
def _run_loop_iteration(self, subgraph: Dict[str, Any]) -> str:
    nodes, forward_edges, backward_edges = subgraph["nodes"], subgraph["forward_edges"], subgraph["backward_edges"]
    # A full swap, not a merge, is correct here: Drawflow connections are drawn
    # within one module's own canvas view, so an inner node's edges can only
    # ever point at other inner nodes in the same private subgraph -- there is
    # nothing in the outer graph's backward_edges an inner node could need.
    saved_backward_edges, self.backward_edges = self.backward_edges, backward_edges
    try:
        queue = list(subgraph["entry_ids"])
        finished = set()
        last_output = ""
        while queue:
            node_id = self._pick_next(queue, forward_edges, backward_edges, finished)
            queue.remove(node_id)
            node = nodes.get(node_id)
            if node is None:
                continue
            try:
                output_text, jump_to = self._execute_node(node_id, node)
            except WorkflowTerminate:
                raise  # Terminate ends the whole run, even from inside a loop -- never caught here
            except Exception as e:
                self.log.append({
                    "node_id": node_id, "title": node.get("title", node_id), "kind": node.get("kind"),
                    "status": "failed", "output": str(e),
                })
                raise WorkflowRunError(f"Loop iteration failed at '{node.get('title', node_id)}': {e}")
            label = self.node_labels.get(node_id, node_id)
            self.context[label] = output_text
            self.log.append({
                "node_id": node_id, "title": node["title"], "kind": node["kind"],
                "status": "success", "output": (output_text or "")[:600],
            })
            finished.add(node_id)
            if node_id in subgraph["exit_ids"]:
                last_output = output_text
            if jump_to:
                # Same pattern as run()'s own top-level jump_to handling
                # (workflow_engine.py:914-918) -- a Conditions node inside a
                # loop body in all_matches mode returns a list of targets.
                if isinstance(jump_to, list):
                    for t in reversed(jump_to):
                        if t not in queue:
                            queue.insert(0, t)
                else:
                    queue.insert(0, jump_to)
            else:
                queue.extend(t for t in forward_edges.get(node_id, []) if t not in queue)
        return last_output
    finally:
        self.backward_edges = saved_backward_edges
```

*Why this isn't unified with `run()`'s own loop:* the two have genuinely different failure semantics. `run()`'s top-level loop deliberately swallows a node failure and keeps going (a failure on one branch shouldn't block an unrelated branch, per the existing `MissingInputError`/branching design) -- fail-fast would be *wrong* there. A loop iteration is the opposite: one bad node aborts the whole loop container immediately, since "half-run the body, silently skip the rest" would produce a partial, misleading `results` array. Forcing one shared method to serve both would need a fail-fast flag threaded through anyway, which is no simpler than two small, purpose-built loops. `self.backward_edges` is temporarily merged (not replaced) for the duration of one iteration, because `_build_scope`/`_execute_node` reference `self.backward_edges` directly rather than taking it as a parameter -- restoring the saved copy in `finally` (even on the `WorkflowRunError`/`WorkflowTerminate` paths above) keeps the top-level run's own scoping intact once the loop returns or re-raises.

### `{{loop.item}}` / `{{loop.index}}`

Added to `_substitute_tokens`'s dispatch (Part 1): a token named exactly `loop.item` or `loop.index` resolves from `self.loop_stack[-1]` (`[item, index]`) if the stack is non-empty; `item` is rendered via `_array_item_to_text` (so a JSON object/array item is still usable downstream, a scalar item substitutes unquoted). Referencing either name outside any loop (empty stack) raises `WorkflowRunError("{{loop.item}}/{{loop.index}} can only be used inside an Apply to Each or Do Until container.")`. `loop.index` is available in Do Until too (always `None` for `loop.item`, since Do Until has no per-item concept) — useful for debugging/labeling which pass produced a given log line.

### Container panel UI (`workflow-builder.html`)

`renderContainerPanel` (`workflow-builder.html:1162-1171`) gains a **Loop Type** dropdown (`None` / `Apply to Each` / `Do Until`) above the existing Container Name field and Open Container button. Selecting a type reveals its own fields inline in the same panel (not a separate node type, so no palette change, no new `FUNCTION_FIELD_SCHEMAS` entry needed — this is bespoke like `renderLogicGatePanel`/`renderConditionsPanel`, not the generic declarative table, since `kind` stays `"container"` throughout):

- **None** (default): no extra fields — today's behavior, byte-for-byte.
- **Apply to Each**: one field, **Items** (textarea, `{{label}}`-substitutable, placeholder `e.g. {{label}} or a literal JSON array`).
- **Do Until**: two fields, **Condition** (text, mono, e.g. `total >= 100` — same expression language as Conditions/Filter Array, evaluated against current `self.variables` plus `loop_index`) and **Max Iterations** (number, placeholder `60`).

`wfbSaveNodePanel`'s `"container-name"` branch (`workflow-builder.html:1386-1392`) extends to also read the loop type and its fields into `params: {loop_type, items}` or `params: {loop_type, condition, max_iterations}` alongside the existing title-rename behavior.

## Testing

New file `00_System/test_workflow_engine_variables_and_loops.py`, same convention as every prior test file (plain `assert`, run directly, no fixtures):

1. **Variables:** Initialize (String/Number/Boolean/Array/Object each), duplicate-name raises, Set on uninitialized raises, Set changes type correctly (string → later JSON array), Increment on uninitialized/non-numeric raises, Increment produces whole-number ints not floats, Append on uninitialized/non-list raises, Append preserves JSON types of appended values, `{{var.name}}` resolves correctly mid-graph and unknown-name raises.
2. **Loop extraction:** a saved-graph-shaped fixture with a plain container nested inside an Apply to Each container's module flattens/extracts correctly (the nested plain container's inner nodes end up inside the loop's private subgraph, not lost) — this is the specific correctness risk the recursive Step A design was built to avoid, so it gets a dedicated test rather than just trusting the reasoning.
3. **Apply to Each end-to-end:** a real `graph_json` fixture (container with `loop_type: "apply_to_each"`, 2-3 inner nodes, wired before/after in the outer graph) run via `engine.run(...)`, asserting: correct number of iterations, `{{loop.item}}`/`{{loop.index}}` resolve per-iteration, the container's own output is the expected JSON array of per-iteration exit values, and a downstream node reading a loop-body label sees the *last* iteration's value.
4. **Apply to Each failure propagation:** an inner node configured to fail (e.g. `function_parse_json` given bad JSON) aborts the whole loop — no further iterations run, the container's own step is logged as failed.
5. **Do Until end-to-end:** condition becomes true before the cap → correct iteration count, cap reached without the condition ever becoming true → stops at `max_iterations` without raising.
6. **Terminate inside a loop:** a `function_terminate` node inside a loop body ends the *entire run* (not just the loop), matching the "never caught in `_run_loop_iteration`" design above.
7. **Nested loops:** an Apply to Each inside another Apply to Each's module resolves both levels correctly, and `{{loop.item}}`/`{{loop.index}}` inside the inner loop resolve to the *inner* loop's current item/index, not the outer one's.
8. **Backward compatibility:** an existing plain (non-loop) container graph fixture — same shape used by today's tests — still flattens and runs identically (Step B's narrowed filter doesn't change plain-container behavior).

## Explicitly out of scope

- **Any change to how a saved workflow is persisted** — `loop_type`/`items`/`condition`/`max_iterations` live in the container node's existing `data.params`, the same JSON blob every other node type already uses. No schema migration needed.
- **A visual indicator distinguishing a loop container from a plain one on the collapsed canvas box** — nice-to-have polish (e.g. a small badge/icon), not required for correctness. Can be added to `containerNodeHtml` (`workflow-builder.html:381`) later without any engine change.
- **Parallel/concurrent loop iteration** — iterations run strictly sequentially, matching Power Automate's default (non-concurrent) Apply to Each behavior and this engine's existing single-threaded execution model.
- **A `Do Until` "Limit: Count" vs "Limit: Timeout" split** the way Power Automate's real UI offers both — this slice only implements the iteration-count cap (`max_iterations`), consistent with `Delay`'s own existing wall-clock cap already covering the "don't run forever in one HTTP request" concern.
- **Migrating any existing saved workflow** — no existing workflow can have `params.loop_type` set (the field doesn't exist until this slice ships), so every existing container is guaranteed to hit Step B unchanged.
