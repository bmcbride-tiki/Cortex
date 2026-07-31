# Variables & Loop Containers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a named mutable variable store (Initialize/Set/Increment/Append Variable) and loop execution (Apply to Each / Do Until, reusing the existing Container UI) to the Workflow Builder.

**Architecture:** Variables are a new `self.variables: Dict[str, Any]` store on `WorkflowEngine`, addressed by a new `{{var.name}}` token form, deliberately global (not connection-scoped) unlike the existing `{{label}}` system. Loop containers extend the existing `Container` node with a `params.loop_type` field; `_flatten_containers` gains a new extraction pass that pulls a loop container's inner module into a private `self.loop_subgraphs[node_id]` entry (instead of splicing it into the main flow once), and a new `_execute_loop_container`/`_run_loop_iteration` pair re-runs that private subgraph once per array item or until a condition holds, reusing the existing `_pick_next` scheduler.

**Tech Stack:** Pure Python stdlib additions to the existing engine (`00_System/workflow_engine.py`), declarative + one bespoke panel addition to `00_System/templates/workflow-builder.html`, registry entries in `00_System/server.py`. No new dependencies.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-31-variables-and-loops-design.md` — consult it for full rationale behind each design choice.
- `TOKEN_PATTERN` (`workflow_engine.py:107`) widens from `[a-zA-Z0-9_\-]+` to `[a-zA-Z0-9_.\-]+`. This is a strict superset — no existing label can contain a dot (enforced by `wfbSaveLabel` in the frontend), so this can never collide with an existing `{{label}}` reference.
- `{{var.name}}` and `{{loop.item}}`/`{{loop.index}}` are the only two reserved dot-namespaces. Both raise `WorkflowRunError` (not `MissingInputError`) when the name/context is invalid — they aren't "wiring" problems, they're real name-resolution failures.
- Loop containers reuse the existing `Container` node (`kind: "container"`) with a new `params.loop_type` field (`"apply_to_each"` | `"do_until"` | absent). Absent is fully backward compatible with every existing saved workflow.
- A loop iteration failure is fail-fast (aborts the whole loop container); a top-level graph node failure is not (existing `run()` behavior, unchanged). These are different, intentionally not unified into one shared method — see spec's "Why this isn't unified with `run()`'s own loop."
- Test convention: co-located `test_<module>.py` in `00_System/`, plain `assert`, run directly, no fixtures.

---

### Task 1: Engine state + token namespace dispatch

**Files:**
- Modify: `00_System/workflow_engine.py` (`TOKEN_PATTERN` at line 107; `WorkflowEngine.__init__` at line 222 — add `self.variables`, `self.loop_stack`; `_substitute_tokens` at line 395)
- Test: `00_System/test_workflow_engine_variables_and_loops.py` (new file)

**Interfaces:**
- Produces: `self.variables: Dict[str, Any]`, `self.loop_stack: List[List[Any]]` on `WorkflowEngine`. `_substitute_tokens` resolves `var.<name>` from `self.variables` and `loop.item`/`loop.index` from `self.loop_stack[-1]`, before falling through to the existing `_current_scope` lookup.

- [ ] **Step 1: Write the failing tests**

Create `00_System/test_workflow_engine_variables_and_loops.py`:

```python
# 00_System/test_workflow_engine_variables_and_loops.py
"""Assert-based smoke tests for Variables (Initialize/Set/Increment/Append)
and loop containers (Apply to Each / Do Until). Run directly:
python test_workflow_engine_variables_and_loops.py
"""
import sys
sys.dont_write_bytecode = True
import json

from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from workflow_engine import WorkflowEngine, WorkflowRunError, WorkflowTerminate


def _graph(node_specs):
    """Same helper as test_workflow_engine_flow_and_data_ops.py: builds a minimal
    valid Drawflow-shaped graph_json from (node_id, label, tool_id, params, targets)
    tuples, all in the "Home" module."""
    data = {}
    for node_id, label, tool_id, params, targets in node_specs:
        data[node_id] = {
            "name": tool_id,
            "data": {"kind": "function", "tool_id": tool_id, "category": None, "title": label, "label": label, "params": params},
            "outputs": {"output_1": {"connections": [{"node": t, "output": "input_1"} for t in targets]}},
        }
    return {"drawflow": {"Home": {"data": data}}}


def _single_input_engine(node_id, upstream_text):
    engine = WorkflowEngine(dry_run=True)
    engine.backward_edges = {node_id: ["src"]}
    engine.node_labels = {"src": "Src", node_id: "Node"}
    engine.context = {"Src": upstream_text}
    return engine


def test_var_token_resolves_and_unknown_raises():
    engine = _single_input_engine("n", "")
    engine.variables["counter"] = 5
    engine._current_scope = {}
    engine._current_pred_labels = set()
    assert engine._substitute_tokens("value is {{var.counter}}") == "value is 5"
    try:
        engine._substitute_tokens("{{var.missing}}")
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_loop_tokens_resolve_from_stack_and_raise_outside_loop():
    engine = WorkflowEngine(dry_run=True)
    engine._current_scope = {}
    engine._current_pred_labels = set()
    try:
        engine._substitute_tokens("{{loop.item}}")
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass

    engine.loop_stack.append(["Alice", 0])
    assert engine._substitute_tokens("{{loop.item}} at {{loop.index}}") == "Alice at 0"
    engine.loop_stack.append([{"name": "Bob"}, 1])
    assert json.loads(engine._substitute_tokens("{{loop.item}}")) == {"name": "Bob"}
    assert engine._substitute_tokens("{{loop.index}}") == "1"
    engine.loop_stack.pop()
    # Innermost-loop resolution: after popping the nested frame, the outer
    # loop's item/index are visible again.
    assert engine._substitute_tokens("{{loop.item}}") == "Alice"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_variables_and_loops.py`
Expected: `AttributeError: 'WorkflowEngine' object has no attribute 'variables'`

- [ ] **Step 3: Widen `TOKEN_PATTERN`**

In `00_System/workflow_engine.py`, replace line 107:

```python
TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-]+)\s*\}\}")
```

with:

```python
TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.\-]+)\s*\}\}")
```

- [ ] **Step 4: Add `self.variables`/`self.loop_stack` to `__init__`**

In `00_System/workflow_engine.py`, after `self.terminated: Optional[Dict[str, str]] = None` (~line 255):

```python
        # Named mutable variable store (Initialize/Set/Increment/Append Variable) --
        # deliberately global for the whole run, NOT connection-scoped like
        # self.context/{{label}}, matching Power Automate's own variable semantics.
        self.variables: Dict[str, Any] = {}
        # Stack of [current_item, current_index] frames, one per currently-executing
        # loop container -- supports nesting, {{loop.item}}/{{loop.index}} always
        # resolve to the innermost (top of stack) frame.
        self.loop_stack: List[List[Any]] = []
        # Populated by _flatten_containers' loop-extraction pass (Task 3): node_id
        # of a loop container -> its private {"nodes", "forward_edges",
        # "backward_edges", "entry_ids", "exit_ids"}.
        self.loop_subgraphs: Dict[str, Dict[str, Any]] = {}
```

- [ ] **Step 5: Extend `_substitute_tokens`'s `replace` closure**

In `00_System/workflow_engine.py`, replace the `replace` function inside `_substitute_tokens` (~lines 402-413):

```python
        def replace(m: "re.Match[str]") -> str:
            label = m.group(1)
            if label not in self._current_scope:
                token_display = "{{" + label + "}}"
                # A connected-but-empty predecessor shouldn't happen now that
                # run() waits for every predecessor to finish, but if it does
                # (e.g. that predecessor failed) say so precisely rather than
                # blaming the wiring.
                why = (
                    "hasn't produced output yet"
                    if label in self._current_pred_labels
                    else "isn't directly connected to this node"
                )
                raise MissingInputError(f'Missing input value: {token_display} -- "{label}" {why}.')
            return self._current_scope[label]
```

with:

```python
        def replace(m: "re.Match[str]") -> str:
            name = m.group(1)

            if name.startswith("var."):
                var_name = name[4:]
                if var_name not in self.variables:
                    raise WorkflowRunError(f"Unknown variable: {name} -- initialize it with an Initialize Variable node first.")
                return self._array_item_to_text(self.variables[var_name])

            if name in ("loop.item", "loop.index"):
                if not self.loop_stack:
                    raise WorkflowRunError("{{loop.item}}/{{loop.index}} can only be used inside an Apply to Each or Do Until container.")
                item, index = self.loop_stack[-1]
                return self._array_item_to_text(item) if name == "loop.item" else str(index)

            if name not in self._current_scope:
                token_display = "{{" + name + "}}"
                # A connected-but-empty predecessor shouldn't happen now that
                # run() waits for every predecessor to finish, but if it does
                # (e.g. that predecessor failed) say so precisely rather than
                # blaming the wiring.
                why = (
                    "hasn't produced output yet"
                    if name in self._current_pred_labels
                    else "isn't directly connected to this node"
                )
                raise MissingInputError(f'Missing input value: {token_display} -- "{name}" {why}.')
            return self._current_scope[name]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_variables_and_loops.py`
Expected: `2/2 passed`

- [ ] **Step 7: Regression check**

Run every existing test file to confirm the widened `TOKEN_PATTERN` and reordered `replace` logic don't break anything:

```bash
python 00_System/test_workflow_engine_tokens.py
python 00_System/test_workflow_engine_conditions.py
python 00_System/test_workflow_engine_flow_and_data_ops.py
```

Expected: all still passing at their prior counts (13, 16, 47).

- [ ] **Step 8: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine_variables_and_loops.py
git commit -m "Add variable store, loop stack, and var./loop. token namespaces"
```

---

### Task 2: The four Variable nodes

**Files:**
- Modify: `00_System/workflow_engine.py` (`_execute_function_node`, add four branches after the `function_create_html_table` branch, i.e. before the `# --- Prompt-driven AI functions` comment ~line 1035)
- Modify: `00_System/server.py` (`FUNCTIONS_REGISTRY`, `TOOL_FA_ICON_MAP`)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS`)
- Test: `00_System/test_workflow_engine_variables_and_loops.py` (append)

**Interfaces:**
- Produces: `tool_id`s `function_initialize_variable`, `function_set_variable`, `function_increment_variable`, `function_append_variable`. All read/write `self.variables` (from Task 1) and return their own new value as node output via `self._array_item_to_text` (existing helper).

- [ ] **Step 1: Write the failing tests**

Append to `00_System/test_workflow_engine_variables_and_loops.py` (before `if __name__ == "__main__":`):

```python
def test_initialize_variable_all_types():
    engine = WorkflowEngine(dry_run=True)
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "s", "type": "String", "value": "hello"})
    assert engine.variables["s"] == "hello"
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "num", "type": "Number", "value": "42"})
    assert engine.variables["num"] == 42.0
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "b", "type": "Boolean", "value": "true"})
    assert engine.variables["b"] is True
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "arr", "type": "Array", "value": "[1, 2, 3]"})
    assert engine.variables["arr"] == [1, 2, 3]
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "obj", "type": "Object", "value": '{"a": 1}'})
    assert engine.variables["obj"] == {"a": 1}


def test_initialize_variable_duplicate_name_raises():
    engine = WorkflowEngine(dry_run=True)
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "x", "type": "String", "value": "a"})
    try:
        engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "x", "type": "String", "value": "b"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_initialize_variable_invalid_array_json_raises():
    engine = WorkflowEngine(dry_run=True)
    try:
        engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "bad", "type": "Array", "value": "not json"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_set_variable_requires_initialized():
    engine = WorkflowEngine(dry_run=True)
    try:
        engine._execute_function_node("n", {"tool_id": "function_set_variable"}, {"name": "missing", "value": "x"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_set_variable_overwrites_and_preserves_json_type():
    engine = WorkflowEngine(dry_run=True)
    engine.variables["x"] = "initial"
    engine._execute_function_node("n", {"tool_id": "function_set_variable"}, {"name": "x", "value": '["a", "b"]'})
    assert engine.variables["x"] == ["a", "b"]
    engine._execute_function_node("n", {"tool_id": "function_set_variable"}, {"name": "x", "value": "plain text"})
    assert engine.variables["x"] == "plain text"


def test_increment_variable_requires_initialized_numeric():
    engine = WorkflowEngine(dry_run=True)
    try:
        engine._execute_function_node("n", {"tool_id": "function_increment_variable"}, {"name": "missing", "increment_by": "1"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass
    engine.variables["s"] = "not a number"
    try:
        engine._execute_function_node("n", {"tool_id": "function_increment_variable"}, {"name": "s", "increment_by": "1"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_increment_variable_produces_whole_number_ints():
    engine = WorkflowEngine(dry_run=True)
    engine.variables["count"] = 0
    output, jump = engine._execute_function_node("n", {"tool_id": "function_increment_variable"}, {"name": "count", "increment_by": "1"})
    assert engine.variables["count"] == 1
    assert output == "1"  # not "1.0"
    engine._execute_function_node("n", {"tool_id": "function_increment_variable"}, {"name": "count", "increment_by": "0.5"})
    assert engine.variables["count"] == 1.5


def test_append_variable_requires_initialized_list():
    engine = WorkflowEngine(dry_run=True)
    try:
        engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "missing", "value": "x"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass
    engine.variables["notalist"] = "x"
    try:
        engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "notalist", "value": "y"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_append_variable_preserves_json_types():
    engine = WorkflowEngine(dry_run=True)
    engine.variables["arr"] = []
    engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "arr", "value": "plain"})
    engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "arr", "value": "42"})
    engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "arr", "value": '{"a": 1}'})
    assert engine.variables["arr"] == ["plain", 42, {"a": 1}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_variables_and_loops.py`
Expected: `WorkflowRunError: Unknown function tool_id: function_initialize_variable` (and similar) on all new tests.

- [ ] **Step 3: Add the four dispatch branches**

In `00_System/workflow_engine.py`, add after the `function_create_html_table` branch (before `# --- Prompt-driven AI functions`):

```python
        if tool_id == "function_initialize_variable":
            name = params.get("name", "")
            if not name:
                raise WorkflowRunError("Initialize Variable requires a name.")
            if name in self.variables:
                raise WorkflowRunError(f"Variable '{name}' is already initialized.")
            var_type = params.get("type", "String")
            raw = self._substitute_tokens(params.get("value", ""))
            if var_type == "Number":
                try:
                    value = float(raw)
                except ValueError as e:
                    raise WorkflowRunError(f"Initialize Variable: '{raw}' is not a valid Number: {e}")
            elif var_type == "Boolean":
                value = raw.strip().lower() in ("true", "1", "yes")
            elif var_type in ("Array", "Object"):
                try:
                    value = json.loads(raw)
                except (TypeError, ValueError) as e:
                    raise WorkflowRunError(f"Initialize Variable: '{raw}' is not valid JSON for type {var_type}: {e}")
            else:
                value = raw
            self.variables[name] = value
            return self._array_item_to_text(value), None

        if tool_id == "function_set_variable":
            name = params.get("name", "")
            if name not in self.variables:
                raise WorkflowRunError(f"Set Variable: '{name}' has not been initialized.")
            raw = self._substitute_tokens(params.get("value", ""))
            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                value = raw
            self.variables[name] = value
            return self._array_item_to_text(value), None

        if tool_id == "function_increment_variable":
            name = params.get("name", "")
            if name not in self.variables:
                raise WorkflowRunError(f"Increment Variable: '{name}' has not been initialized.")
            try:
                current = float(self.variables[name])
            except (TypeError, ValueError):
                raise WorkflowRunError(f"Increment Variable: '{name}' is not numeric (current value: {self.variables[name]!r}).")
            increment_by = float(self._substitute_tokens(params.get("increment_by", "1")) or 1)
            new_value = current + increment_by
            new_value = int(new_value) if new_value.is_integer() else new_value
            self.variables[name] = new_value
            return self._array_item_to_text(new_value), None

        if tool_id == "function_append_variable":
            name = params.get("name", "")
            if name not in self.variables:
                raise WorkflowRunError(f"Append Variable: '{name}' has not been initialized.")
            if not isinstance(self.variables[name], list):
                raise WorkflowRunError(f"Append Variable: '{name}' is not an Array (current type: {type(self.variables[name]).__name__}).")
            raw = self._substitute_tokens(params.get("value", ""))
            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                value = raw
            self.variables[name].append(value)
            return self._array_item_to_text(self.variables[name]), None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_variables_and_loops.py`
Expected: `12/12 passed`

- [ ] **Step 5: Register all four nodes**

In `00_System/server.py` `FUNCTIONS_REGISTRY` (after the `function_create_html_table` entry):

```python
    {
        "tool_id": "function_initialize_variable",
        "title": "Initialize Variable",
        "description": "Declares a named variable (String/Number/Boolean/Array/Object) with an initial value, referenced elsewhere via {{var.name}}.",
        "model": None,
    },
    {
        "tool_id": "function_set_variable",
        "title": "Set Variable",
        "description": "Overwrites an already-initialized variable's value.",
        "model": None,
    },
    {
        "tool_id": "function_increment_variable",
        "title": "Increment Variable",
        "description": "Adds a number (default 1) to an already-initialized numeric variable.",
        "model": None,
    },
    {
        "tool_id": "function_append_variable",
        "title": "Append Variable",
        "description": "Appends a value to an already-initialized Array variable.",
        "model": None,
    },
```

`TOOL_FA_ICON_MAP`:

```python
    "function_initialize_variable": "fa-box",
    "function_set_variable": "fa-pen",
    "function_increment_variable": "fa-plus",
    "function_append_variable": "fa-list",
```

- [ ] **Step 6: Add builder UI schemas**

In `00_System/templates/workflow-builder.html` `FUNCTION_FIELD_SCHEMAS`:

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

- [ ] **Step 7: Verify icon names exist in the vendored Font Awesome CSS**

```bash
cd 00_System/templates/static/vendor/fontawesome/css
for icon in fa-box fa-pen fa-plus fa-list; do
    grep -qo "\.$icon[,:{ ]" all.min.css && echo "OK $icon" || echo "MISSING $icon"
done
```

Substitute any `MISSING` icon for a real one found the same way Task 12 of the previous slice did.

- [ ] **Step 8: Manually verify in the live registry**

Start the server, confirm `function_initialize_variable`/`function_set_variable`/`function_increment_variable`/`function_append_variable` all appear in `GET /api/workflow-builder/node-registry` with resolved icons, same verification pattern as every node in the previous slice.

- [ ] **Step 9: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_variables_and_loops.py
git commit -m "Add Initialize/Set/Increment/Append Variable function nodes"
```

---

### Task 3: Loop container extraction

**Files:**
- Modify: `00_System/workflow_engine.py` (`_flatten_containers` at line 310)
- Test: `00_System/test_workflow_engine_variables_and_loops.py` (append)

**Interfaces:**
- Consumes: `self.loop_subgraphs` (from Task 1).
- Produces: `_flatten_containers` extracts every container whose `params.loop_type` is set into `self.loop_subgraphs[node_id] = {"nodes", "forward_edges", "backward_edges", "entry_ids", "exit_ids"}`, removing its inner nodes from the passed-in `nodes`/`forward_edges`/`backward_edges` dicts but leaving the container node itself in place. Non-loop containers are unaffected (existing Step B behavior, filter narrowed to exclude loop containers).

- [ ] **Step 1: Write the failing tests**

Append to `00_System/test_workflow_engine_variables_and_loops.py`:

```python
def _container_graph(outer_specs, container_id, container_label, loop_params, inner_module_name, inner_specs, outer_targets_from_container):
    """Builds a Drawflow-shaped graph_json with one container node wired into the
    Home module, whose own sub-diagram lives in a separate module. outer_specs and
    inner_specs are lists of (node_id, label, tool_id, params, targets) same as
    _graph(); inner node targets are wired within the inner module only."""
    home_data = {}
    for node_id, label, tool_id, params, targets in outer_specs:
        home_data[node_id] = {
            "name": tool_id,
            "data": {"kind": "function", "tool_id": tool_id, "category": None, "title": label, "label": label, "params": params},
            "outputs": {"output_1": {"connections": [{"node": t, "output": "input_1"} for t in targets]}},
        }
    home_data[container_id] = {
        "name": "container",
        "data": {
            "kind": "container", "tool_id": "container", "category": None,
            "title": container_label, "label": container_label, "params": loop_params,
            "module_name": inner_module_name,
        },
        "outputs": {"output_1": {"connections": [{"node": t, "output": "input_1"} for t in outer_targets_from_container]}},
    }
    inner_data = {}
    for node_id, label, tool_id, params, targets in inner_specs:
        inner_data[node_id] = {
            "name": tool_id,
            "data": {"kind": "function", "tool_id": tool_id, "category": None, "title": label, "label": label, "params": params},
            "outputs": {"output_1": {"connections": [{"node": t, "output": "input_1"} for t in targets]}},
        }
    return {"drawflow": {"Home": {"data": home_data}, inner_module_name: {"data": inner_data}}}


def test_apply_to_each_container_extracted_not_flattened():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1,2,3]"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Inner", "function_compose", {"value": "x"}, [])],
        outer_targets_from_container=[],
    )
    nodes, forward_edges, backward_edges = engine._parse_graph(graph)
    assert "10" in nodes and nodes["10"]["kind"] == "container"
    assert "11" not in nodes  # pulled out of the shared graph
    assert "10" in engine.loop_subgraphs
    sub = engine.loop_subgraphs["10"]
    assert list(sub["nodes"].keys()) == ["11"]
    assert sub["entry_ids"] == ["11"] and sub["exit_ids"] == ["11"]


def test_plain_container_nested_inside_loop_container_still_resolves():
    # The specific correctness risk the recursive extraction design targets:
    # a PLAIN container's inner nodes, nested inside a LOOP container's own
    # module, must end up inside the loop's private subgraph, not lost.
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1]"},
        inner_module_name="loop_mod_1",
        inner_specs=[
            ("11", "BeforeNested", "function_compose", {"value": "a"}, ["20"]),
        ],
        outer_targets_from_container=[],
    )
    # Manually splice a plain container ("20") into the loop's module, whose
    # own sub-diagram lives in yet another module ("nested_mod").
    graph["drawflow"]["loop_mod_1"]["data"]["20"] = {
        "name": "container",
        "data": {"kind": "container", "tool_id": "container", "category": None, "title": "Nested", "label": "Nested", "params": {}, "module_name": "nested_mod"},
        "outputs": {"output_1": {"connections": []}},
    }
    graph["drawflow"]["nested_mod"] = {"data": {
        "21": {
            "name": "function_compose",
            "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "Nested Inner", "label": "NestedInner", "params": {"value": "b"}},
            "outputs": {"output_1": {"connections": []}},
        }
    }}

    nodes, forward_edges, backward_edges = engine._parse_graph(graph)
    assert "10" in nodes  # loop container itself survives
    assert "11" not in nodes and "20" not in nodes and "21" not in nodes  # all pulled into the loop's private subgraph
    sub = engine.loop_subgraphs["10"]
    assert set(sub["nodes"].keys()) == {"11", "21"}  # "20" (the nested container) is spliced away WITHIN the private copy, same as top-level
    assert sub["forward_edges"]["11"] == ["21"]  # rewired through the nested container's own entry/exit


def test_backward_compatible_plain_container_unaffected():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[("1", "Before", "function_compose", {"value": "x"}, ["10"])],
        container_id="10", container_label="Group", loop_params={},  # no loop_type -- today's plain container
        inner_module_name="mod_1",
        inner_specs=[("11", "Inner", "function_compose", {"value": "y"}, [])],
        outer_targets_from_container=["2"],
    )
    graph["drawflow"]["Home"]["data"]["2"] = {
        "name": "function_compose",
        "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "After", "label": "After", "params": {"value": "z"}},
        "outputs": {"output_1": {"connections": []}},
    }
    nodes, forward_edges, backward_edges = engine._parse_graph(graph)
    assert "10" not in nodes  # plain container IS spliced away, unchanged from today
    assert "11" in nodes
    assert forward_edges["1"] == ["11"]  # rewired to the inner entry, same as before this slice
    assert engine.loop_subgraphs == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_variables_and_loops.py`
Expected: `test_apply_to_each_container_extracted_not_flattened` and `test_plain_container_nested_inside_loop_container_still_resolves` fail (today's `_flatten_containers` treats every container identically, splicing the loop container away too — `"10" in nodes` will be `False`). `test_backward_compatible_plain_container_unaffected` already passes (nothing about plain-container behavior has changed yet).

- [ ] **Step 3: Add the extraction pass to `_flatten_containers`**

In `00_System/workflow_engine.py`, replace the method body (line 310 area) — the existing `while True:` splice loop stays exactly as-is, just gains a new pass before it and a narrowed filter:

```python
    def _flatten_containers(
        self,
        nodes: Dict[str, Any],
        forward_edges: Dict[str, List[str]],
        backward_edges: Dict[str, List[str]],
        module_nodes: Dict[str, List[str]],
    ) -> None:
        """Splices every PLAIN container node out of the flat graph in place (see
        docstring below), after first EXTRACTING every LOOP container (Apply to Each /
        Do Until -- params.loop_type set) into its own private subgraph in
        self.loop_subgraphs, since a loop's body must run more than once at runtime
        and can't be expressed by splicing it into the main flow a single time."""
        # --- Step A: extract loop containers into private subgraphs -------------
        # Recursing into each one's own private copy first means anything nested
        # inside a loop's body (a plain container, or another loop) resolves
        # correctly before the loop itself is treated as one opaque node by
        # whatever contains it. Module names are unique per container instance
        # (workflow-builder.html's container_${Date.now()}_${counter}), so no two
        # containers' modules ever share a node id -- extraction order never matters.
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
            self._flatten_containers(sub_nodes, sub_forward, sub_backward, module_nodes)
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
            # executable unit (dispatched via _execute_loop_container, Task 4);
            # only its inner module's nodes are pulled out of the shared graph.

        # --- Step B: existing plain-container splice-and-delete, filter narrowed --
        # A "container" node on the main canvas is really just a visual
        # stand-in for a whole separate mini-diagram of its own steps. This
        # removes that stand-in box entirely and rewires the connections so
        # whatever used to point INTO the container now points to the first
        # real step inside it, and whatever used to come OUT of the container
        # now comes from the last real step inside it -- as if the container
        # had never existed. Loop containers (handled above) are excluded.
        while True:
            container_ids = [
                nid for nid, n in nodes.items()
                if n.get("kind") == "container" and not (n.get("params") or {}).get("loop_type")
            ]
            if not container_ids:
                break

            for cid in container_ids:
                module_name = nodes[cid].get("module_name")
                inner_ids = module_nodes.get(module_name, [])
                preds = list(backward_edges.get(cid, []))
                succs = list(forward_edges.get(cid, []))

                if inner_ids:
                    entry_ids = [nid for nid in inner_ids if not backward_edges.get(nid)] or [inner_ids[0]]
                    exit_ids = [nid for nid in inner_ids if not forward_edges.get(nid)] or [inner_ids[-1]]
                else:
                    entry_ids, exit_ids = [], []

                if not entry_ids or not exit_ids:
                    for p in preds:
                        forward_edges[p] = [n for n in forward_edges[p] if n != cid] + succs
                    for s in succs:
                        backward_edges[s] = [n for n in backward_edges[s] if n != cid] + preds
                else:
                    for p in preds:
                        forward_edges[p] = [n for n in forward_edges[p] if n != cid] + entry_ids
                    for e in entry_ids:
                        backward_edges[e] = [n for n in backward_edges[e] if n != cid] + preds
                    for s in succs:
                        backward_edges[s] = [n for n in backward_edges[s] if n != cid] + exit_ids
                    for x in exit_ids:
                        forward_edges[x] = [n for n in forward_edges[x] if n != cid] + succs

                del nodes[cid]
                forward_edges.pop(cid, None)
                backward_edges.pop(cid, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_variables_and_loops.py`
Expected: `15/15 passed`

- [ ] **Step 5: Regression check**

```bash
python 00_System/test_workflow_engine_tokens.py
python 00_System/test_workflow_engine_conditions.py
python 00_System/test_workflow_engine_flow_and_data_ops.py
```

Expected: all still passing at their prior counts. These exercise plain containers indirectly through `run()`; none use `loop_type`, so Step B's narrowed filter should leave their behavior byte-for-byte identical.

- [ ] **Step 6: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine_variables_and_loops.py
git commit -m "Extract loop containers into private subgraphs instead of flattening them"
```

---

### Task 4: Loop execution — Apply to Each / Do Until

**Files:**
- Modify: `00_System/workflow_engine.py` (`_execute_node` at line 742 — add `kind == "container"` branch; new `_execute_loop_container` and `_run_loop_iteration` methods)
- Modify: `00_System/server.py` (no new registry entry needed — loop containers aren't a new `tool_id`, they're the existing `container` tool_id with a params field)
- Test: `00_System/test_workflow_engine_variables_and_loops.py` (append)

**Interfaces:**
- Consumes: `self.loop_subgraphs` (Task 3), `self.loop_stack` (Task 1), `self.variables` (Task 1/2), `_eval_condition_expression` (existing, module-level), `_pick_next` (existing, unchanged).
- Produces: `WorkflowEngine._execute_loop_container(self, node_id: str, node: Dict[str, Any]) -> str` and `WorkflowEngine._run_loop_iteration(self, subgraph: Dict[str, Any]) -> str`, dispatched from `_execute_node` for any node with `kind == "container"`.

- [ ] **Step 1: Write the failing tests**

Append to `00_System/test_workflow_engine_variables_and_loops.py`:

```python
def test_apply_to_each_end_to_end():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[("1", "Src", "function_compose", {"value": '[10, 20, 30]'}, [])],
        container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "{{Src}}"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Doubled", "function_compose", {"value": "got {{loop.item}} at {{loop.index}}"}, [])],
        outer_targets_from_container=[],
    )
    graph["drawflow"]["Home"]["data"]["1"]["outputs"]["output_1"]["connections"] = [{"node": "10", "output": "input_1"}]
    result = engine.run(graph)
    assert result["success"], result
    container_step = next(s for s in result["steps"] if s["node_id"] == "10")
    iterations = json.loads(container_step["output"])
    assert iterations == ["got 10 at 0", "got 20 at 1", "got 30 at 2"]


def test_apply_to_each_inner_failure_aborts_whole_loop():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1, 2]"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Bad", "function_parse_json", {"required_keys": ""}, [])],  # gathers upstream text -- none connected -> invalid JSON
        outer_targets_from_container=[],
    )
    result = engine.run(graph)
    assert result["success"] is False
    container_step = next(s for s in result["steps"] if s["node_id"] == "10")
    assert container_step["status"] == "failed"
    # Only ONE inner-node failure log entry -- the loop aborted after the first
    # iteration's failure rather than attempting a second.
    inner_failures = [s for s in result["steps"] if s["node_id"] == "11"]
    assert len(inner_failures) == 1


def test_apply_to_each_context_and_container_output():
    # Connection-scoping is unchanged by loops: "After" is only directly wired to
    # the container ("Loop"), never to the loop-body node ("Inner") -- it can only
    # read the container's own aggregate JSON array via {{Loop}}, exactly like any
    # other node's output is referenced. {{Inner}} from outside the loop's module
    # would raise MissingInputError, same as referencing any non-adjacent label
    # would today -- this test doesn't attempt that unreachable reference.
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1, 2, 3]"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Inner", "function_compose", {"value": "n={{loop.item}}"}, [])],
        outer_targets_from_container=["2"],
    )
    graph["drawflow"]["Home"]["data"]["2"] = {
        "name": "function_compose",
        "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "After", "label": "After", "params": {"value": "loop result: {{Loop}}"}},
        "outputs": {"output_1": {"connections": []}},
    }
    result = engine.run(graph)
    assert result["success"], result
    after_step = next(s for s in result["steps"] if s["node_id"] == "2")
    prefix = "loop result: "
    assert after_step["output"].startswith(prefix)
    assert json.loads(after_step["output"][len(prefix):]) == ["n=1", "n=2", "n=3"]
    # Internally, self.context["Inner"] (the inner node's OWN label) still holds
    # the last iteration's value, same as any node re-run in place would -- not
    # reachable from outside the loop's module, but real and correct internally.
    assert engine.context["Inner"] == "n=3"


def test_do_until_stops_when_condition_true():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[("1", "Init", "function_initialize_variable", {"name": "counter", "type": "Number", "value": "0"}, ["10"])],
        container_id="10", container_label="Loop",
        loop_params={"loop_type": "do_until", "condition": "counter >= 3", "max_iterations": 10},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Inc", "function_increment_variable", {"name": "counter", "increment_by": "1"}, [])],
        outer_targets_from_container=[],
    )
    result = engine.run(graph)
    assert result["success"], result
    container_step = next(s for s in result["steps"] if s["node_id"] == "10")
    iterations = json.loads(container_step["output"])
    assert len(iterations) == 3  # 0->1, 1->2, 2->3, condition true after 3rd
    assert engine.variables["counter"] == 3


def test_do_until_stops_at_max_iterations_without_raising():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[("1", "Init", "function_initialize_variable", {"name": "counter", "type": "Number", "value": "0"}, ["10"])],
        container_id="10", container_label="Loop",
        loop_params={"loop_type": "do_until", "condition": "counter >= 1000", "max_iterations": 5},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Inc", "function_increment_variable", {"name": "counter", "increment_by": "1"}, [])],
        outer_targets_from_container=[],
    )
    result = engine.run(graph)
    assert result["success"], result
    container_step = next(s for s in result["steps"] if s["node_id"] == "10")
    assert len(json.loads(container_step["output"])) == 5
    assert engine.variables["counter"] == 5


def test_terminate_inside_loop_ends_entire_run():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1, 2, 3]"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Stop", "function_terminate", {"status": "Failed", "message": "stop from inside loop"}, [])],
        outer_targets_from_container=["2"],
    )
    graph["drawflow"]["Home"]["data"]["2"] = {
        "name": "function_compose",
        "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "Never", "label": "Never", "params": {"value": "should not run"}},
        "outputs": {"output_1": {"connections": []}},
    }
    result = engine.run(graph)
    assert result["success"] is False
    assert result["terminated"] == {"status": "Failed", "message": "stop from inside loop"}
    ran_ids = [s["node_id"] for s in result["steps"]]
    assert "2" not in ran_ids  # the whole run stopped, not just the loop


def test_nested_apply_to_each_resolves_innermost_loop_stack():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Outer",
        loop_params={"loop_type": "apply_to_each", "items": '["a", "b"]'},
        inner_module_name="outer_mod",
        inner_specs=[],
        outer_targets_from_container=[],
    )
    # Nest an inner Apply to Each container inside the outer loop's own module.
    graph["drawflow"]["outer_mod"]["data"]["20"] = {
        "name": "container",
        "data": {
            "kind": "container", "tool_id": "container", "category": None,
            "title": "Inner", "label": "Inner",
            "params": {"loop_type": "apply_to_each", "items": "[1, 2]"},
            "module_name": "inner_mod",
        },
        "outputs": {"output_1": {"connections": []}},
    }
    graph["drawflow"]["inner_mod"] = {"data": {
        "21": {
            "name": "function_compose",
            "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "Combine", "label": "Combine", "params": {"value": "outer={{loop.item}}"}},
            "outputs": {"output_1": {"connections": []}},
        }
    }}
    result = engine.run(graph)
    assert result["success"], result
    outer_step = next(s for s in result["steps"] if s["node_id"] == "10")
    outer_iterations = json.loads(outer_step["output"])
    # Each outer iteration's result is itself the inner loop's [item, item] array;
    # the inner "Combine" node's {{loop.item}} must resolve to the INNER loop's
    # current item (1, then 2) both times, NOT the outer loop's "a"/"b" -- proving
    # innermost-frame resolution, not just "some" loop context leaking through.
    assert outer_iterations == [
        ["outer=1", "outer=2"],
        ["outer=1", "outer=2"],
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_variables_and_loops.py`
Expected: `WorkflowRunError: Unknown node kind: container` on every new end-to-end test (no `kind == "container"` dispatch branch exists yet).

- [ ] **Step 3: Add the `_execute_node` dispatch branch**

In `00_System/workflow_engine.py`, in `_execute_node` (line 742 area), add before the final `raise WorkflowRunError(f"Unknown node kind: {kind}")`:

```python
        if kind == "container":
            return self._execute_loop_container(node_id, node), None
```

- [ ] **Step 4: Add `_execute_loop_container` and `_run_loop_iteration`**

Add as new `WorkflowEngine` methods, placed after `_run_review_gate` (alongside the other "Built-in node handlers"):

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
            max_iterations = int(params.get("max_iterations") or 60)
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

    def _run_loop_iteration(self, subgraph: Dict[str, Any]) -> str:
        nodes, forward_edges, backward_edges = subgraph["nodes"], subgraph["forward_edges"], subgraph["backward_edges"]
        # A full swap, not a merge, is correct here: Drawflow connections are drawn
        # within one module's own canvas view, so an inner node's edges can only
        # ever point at other inner nodes in the same private subgraph.
        saved_backward_edges, self.backward_edges = self.backward_edges, backward_edges
        try:
            queue = list(subgraph["entry_ids"])
            finished: set = set()
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
                    raise  # Terminate ends the whole run, even from inside a loop
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

Note: `node_labels` for inner nodes must already be populated before a loop container ever executes. `run()` builds `self.node_labels` from the *final* flattened `nodes` dict (`workflow_engine.py` ~line 1120: `{nid: (n.get("label") or nid) for nid, n in nodes.items()}`) — since Task 3's extraction happens inside `_parse_graph`/`_flatten_containers` and inner nodes are removed from that final dict, `self.node_labels` would be missing entries for every inner node. Fix this in the same step: in `run()`, after building `self.node_labels` from `nodes`, also merge in labels from every extracted loop subgraph:

```python
        self.node_labels = {nid: (n.get("label") or nid) for nid, n in nodes.items()}
        for subgraph in self.loop_subgraphs.values():
            for nid, n in subgraph["nodes"].items():
                self.node_labels[nid] = n.get("label") or nid
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_variables_and_loops.py`
Expected: `22/22 passed`

- [ ] **Step 6: Regression check**

```bash
python 00_System/test_workflow_engine_tokens.py
python 00_System/test_workflow_engine_conditions.py
python 00_System/test_workflow_engine_flow_and_data_ops.py
```

Expected: all still passing at their prior counts.

- [ ] **Step 7: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine_variables_and_loops.py
git commit -m "Add Apply to Each / Do Until loop execution"
```

---

### Task 5: Container panel UI — Loop Type

**Files:**
- Modify: `00_System/templates/workflow-builder.html` (`renderContainerPanel` and its `wfbSaveNodePanel` read branch)

**Interfaces:**
- Produces: a **Loop Type** dropdown (None / Apply to Each / Do Until) in the Container config panel; selecting a type reveals its own inline fields; saved `params` match the shape `_execute_loop_container` (Task 4) consumes (`{"loop_type": "apply_to_each", "items": ...}` or `{"loop_type": "do_until", "condition": ..., "max_iterations": ...}` or `{}` for None).

- [ ] **Step 1: Locate and replace `renderContainerPanel`**

Find the current implementation:

```javascript
        function renderContainerPanel(nodeId, data) {
            const body = document.getElementById("wfb-panel-body");
            body.innerHTML = `
                <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Container Name</label>
                <input type="text" data-panel-container-name value="${escapeHtml(data.title)}" class="w-full bg-canvas border border-border rounded px-3 py-2 text-heading text-xs focus:outline-none focus:border-primary">
                ...
                <button onclick="window.wfbEnterContainerFromPanel('${nodeId}')" class="w-full mt-2 px-3 py-1.5 bg-surface-2 hover:bg-border border border-border-strong text-xs font-mono rounded text-heading transition-colors">Open Container <i class="fa-solid fa-up-right-and-down-left-from-center ml-1"></i></button>
                ...
            `;
            body.dataset.readFn = "container-name";
        }
```

Replace with (adding the Loop Type section without touching the existing name field or Open Container button):

```javascript
        function renderContainerPanel(nodeId, data) {
            const body = document.getElementById("wfb-panel-body");
            const p = data.params || {};
            const loopType = p.loop_type || "";
            body.innerHTML = `
                <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Container Name</label>
                <input type="text" data-panel-container-name value="${escapeHtml(data.title)}" class="w-full bg-canvas border border-border rounded px-3 py-2 text-heading text-xs focus:outline-none focus:border-primary">
                <label class="block text-muted font-mono uppercase tracking-wider text-[10px] mt-3">Loop Type</label>
                <select id="wfb-container-loop-type" onchange="window.wfbRenderLoopFields('${nodeId}')" class="w-full bg-canvas border border-border rounded px-3 py-2 text-body text-xs focus:outline-none focus:border-primary">
                    <option value="" ${loopType === "" ? "selected" : ""}>None (plain grouping)</option>
                    <option value="apply_to_each" ${loopType === "apply_to_each" ? "selected" : ""}>Apply to Each</option>
                    <option value="do_until" ${loopType === "do_until" ? "selected" : ""}>Do Until</option>
                </select>
                <div id="wfb-container-loop-fields" class="mt-2"></div>
                <button onclick="window.wfbEnterContainerFromPanel('${nodeId}')" class="w-full mt-3 px-3 py-1.5 bg-surface-2 hover:bg-border border border-border-strong text-xs font-mono rounded text-heading transition-colors">Open Container <i class="fa-solid fa-up-right-and-down-left-from-center ml-1"></i></button>
                <button onclick="window.wfbSaveNodePanel('${nodeId}')" class="w-full mt-2 px-3 py-1.5 bg-primary/15 hover:bg-primary/25 text-primary-400 border border-primary/30 text-xs font-semibold rounded transition-colors">Save Node Config</button>
            `;
            window.wfbRenderLoopFields(nodeId, p);
            body.dataset.readFn = "container-name";
        }

        window.wfbRenderLoopFields = function(nodeId, existingParams) {
            const loopType = document.getElementById("wfb-container-loop-type").value;
            const p = existingParams || {};
            const mount = document.getElementById("wfb-container-loop-fields");
            if (loopType === "apply_to_each") {
                mount.innerHTML = `
                    <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Items</label>
                    <textarea id="wfb-loop-items" rows="2" placeholder="e.g. {{label}} or a literal JSON array" class="w-full bg-canvas border border-border rounded px-3 py-2 text-heading font-mono text-[11px] focus:outline-none focus:border-primary custom-scrollbar resize-none">${escapeHtml(p.items || "")}</textarea>
                `;
            } else if (loopType === "do_until") {
                mount.innerHTML = `
                    <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Condition</label>
                    <input type="text" id="wfb-loop-condition" value="${escapeHtml(p.condition || "")}" placeholder="e.g. total &gt;= 100" class="w-full bg-canvas border border-border rounded px-3 py-2 text-heading font-mono text-[11px] focus:outline-none focus:border-primary">
                    <label class="block text-muted font-mono uppercase tracking-wider text-[10px] mt-2">Max Iterations</label>
                    <input type="number" id="wfb-loop-max-iterations" value="${escapeHtml(p.max_iterations || 60)}" class="w-full bg-canvas border border-border rounded px-3 py-2 text-heading text-xs focus:outline-none focus:border-primary">
                `;
            } else {
                mount.innerHTML = "";
            }
        };
```

- [ ] **Step 2: Extend `wfbSaveNodePanel`'s `"container-name"` branch**

Find:

```javascript
            if (readFn === "container-name") {
                const newTitle = body.querySelector("[data-panel-container-name]").value.trim() || "Container";
                ...
                wfbLog(`Renamed container to "${newTitle}".`, "text-success-400");
```

Replace with (keep the existing title-save behavior, add params read/save):

```javascript
            if (readFn === "container-name") {
                const newTitle = body.querySelector("[data-panel-container-name]").value.trim() || "Container";
                const loopType = document.getElementById("wfb-container-loop-type").value;
                let params = {};
                if (loopType === "apply_to_each") {
                    params = { loop_type: "apply_to_each", items: document.getElementById("wfb-loop-items").value };
                } else if (loopType === "do_until") {
                    params = {
                        loop_type: "do_until",
                        condition: document.getElementById("wfb-loop-condition").value,
                        max_iterations: parseInt(document.getElementById("wfb-loop-max-iterations").value, 10) || 60,
                    };
                }
                saveNodeParams(nodeId, params);
                ...
                wfbLog(`Renamed container to "${newTitle}".`, "text-success-400");
```

(The `...` marks the existing title-rename/node-update lines already there — keep them; only the new `loopType`/`params`/`saveNodeParams` lines are additions.)

- [ ] **Step 3: Manually verify in the browser**

Run: `python 00_System/server.py`, open the builder.

1. Drag a Container onto the canvas, select it — confirm Loop Type defaults to "None" and no extra fields show.
2. Switch to "Apply to Each" — an Items textarea appears. Type `[1,2,3]`, open the container, drag a Compose node inside referencing `{{loop.item}}`, save, close, click Save Node Config on the container.
3. Run (dry run) — confirm the run log shows the container executing with a 3-element JSON array output.
4. Switch a different container to "Do Until", set Condition and Max Iterations, verify the fields save/reload correctly when reselecting the node.
5. Confirm an existing plain container (Loop Type "None") still opens/renames/runs exactly as before.

- [ ] **Step 4: Commit**

```bash
git add 00_System/templates/workflow-builder.html
git commit -m "Add Loop Type (Apply to Each / Do Until) to the Container config panel"
```

---

### Task 6: Full regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run every test file**

```bash
python 00_System/test_workflow_engine_variables_and_loops.py
python 00_System/test_workflow_engine_flow_and_data_ops.py
python 00_System/test_workflow_engine_conditions.py
python 00_System/test_workflow_engine_tokens.py
python 00_System/test_model_classifications.py
```

Expected: all pass, zero regressions.

- [ ] **Step 2: Live end-to-end verification via the real server**

Start the server, POST a real `graph_json` (Initialize Variable → Do Until incrementing it → downstream node reading `{{var.name}}`) to `/api/workflow-builder/run` with `dry_run: true`, same verification style as the previous slice's Task 12. Confirm the response's step log, final variable value, and container output array all match expectations.

- [ ] **Step 3: Commit** (only if Step 2 surfaces a fix — otherwise nothing to commit)

## Self-Review Notes

- **Spec coverage:** Part 1 (Variables + `{{var.name}}`) → Tasks 1-2. Part 2 (loop containers: extraction, execution, `{{loop.item}}`/`{{loop.index}}`, panel UI) → Tasks 3-5. Testing section's 8 scenarios are covered across Tasks 1-5's test additions (variables: Task 2; extraction/nesting: Task 3; Apply to Each/Do Until/failure/Terminate/nested loops: Task 4; backward compatibility: Task 3's third test). Out-of-scope items (persistence changes, visual loop badge, concurrent iteration, timeout-based Do Until, migration) are untouched by every task above.
- **Placeholder scan:** no TBD/TODO; every step has literal code or literal manual-verification instructions.
- **Type consistency:** `_execute_loop_container` returns `str` (not a tuple); `_execute_node`'s new branch wraps it as `(result, None)`, matching the existing `Tuple[str, Optional[Union[str, List[str]]]]` contract every other branch already returns. `self.loop_subgraphs[cid]`'s shape (`nodes`/`forward_edges`/`backward_edges`/`entry_ids`/`exit_ids`) is produced once in Task 3 and consumed with those exact keys in Task 4's `_execute_loop_container`/`_run_loop_iteration` — no mismatch.
- **`node_labels` gap caught during planning:** `run()` builds `self.node_labels` from the post-flatten `nodes` dict, which no longer contains extracted loop-body node ids after Task 3 — without the Task 4 Step 4 fix (merging in labels from every `self.loop_subgraphs` entry), `{{label}}` references to a loop-body node from outside the loop, and the loop body's own internal `self.context[label]` bookkeeping, would silently use the raw node id as a fallback label instead of the author-chosen one. Folded into Task 4 rather than left as a follow-up bug.
