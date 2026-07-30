# Workflow Builder: Config Panel Reorder & Conditions Node Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder the Workflow Builder's Node Configuration panel (Inputs → settings → Output Label) and add a new Conditions function node (up to 10 simple-rule/expression branches, first-match/all-matches toggle, mandatory default).

**Architecture:** The panel reorder is a template/JS-only change splitting one toggled block into two. Conditions reuses the existing `function_logic_gate` "jump_to node id" branching mechanism in `workflow_engine.py`'s `run()` loop, generalized from a single target to a list of targets; expression conditions are evaluated by a new stdlib-only restricted AST walker (no `eval()`, no new dependency).

**Tech Stack:** FastAPI + Jinja/vanilla JS template (`00_System/templates/workflow-builder.html`), Python engine (`00_System/workflow_engine.py`), Python stdlib `ast`/`re`/`json` only — no new dependencies.

## Global Constraints

- No new third-party dependency for expression evaluation — stdlib `ast` only (`requirements.txt` has no `simpleeval`/`asteval` today; spec explicitly rejects adding one).
- Expression evaluator must never execute arbitrary code: only `BoolOp`, `UnaryOp(Not)`, `Compare`, `Name` (namespace-only), and `Constant` AST nodes are permitted; anything else raises `WorkflowRunError`.
- Test convention for this repo: co-located `test_<module>.py`, plain `assert`, run directly via `python test_<module>.py` (no pytest fixtures, no `tests/` directory) — see `00_System/test_workflow_engine_tokens.py`.
- Conditions node stays visually single-input/single-output on the canvas (like `function_logic_gate`) — branching is via "Go To" dropdowns, not drawn wires or new Drawflow ports.
- Default branch target is mandatory — the UI must block saving a Conditions node with no default selected.

---

### Task 1: Node Configuration panel reorder

**Files:**
- Modify: `00_System/templates/workflow-builder.html:89-108` (panel markup), `:1179-1204` (`selectNode`), `:1206-1209` (`clearPanel`)

**Interfaces:**
- Produces: two panel section element ids, `#wfb-panel-inputs-section` (top) and `#wfb-panel-label-section` (bottom), replacing the single `#wfb-panel-header`. `#wfb-panel-inputs` (chips container) and `#wfb-panel-label-input` (text input) keep their existing ids and existing behavior (`renderInputsChips()`, `wfbSaveLabel()`) unchanged.

- [ ] **Step 1: Split `#wfb-panel-header` into two sections around `#wfb-panel-body`**

In `00_System/templates/workflow-builder.html`, replace lines 89-108:

```html
    <!-- Right panel: selected node's config, identical fields to its popup where one exists -->
    <div class="w-80 shrink-0 bg-surface border border-border rounded-xl flex flex-col overflow-hidden relative">
        <div class="px-4 py-3 border-b border-border shrink-0">
            <h4 class="text-xs font-semibold text-heading uppercase tracking-wider">Node Configuration</h4>
        </div>
        <div id="wfb-panel-header" class="hidden px-4 py-3 border-b border-border shrink-0 space-y-2">
            <div class="space-y-1.5">
                <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Output Label (reference as {{label}})</label>
                <div class="flex gap-1.5">
                    <input type="text" id="wfb-panel-label-input" onkeydown="if (event.key === 'Enter') window.wfbSaveLabel()" class="flex-1 bg-canvas border border-border rounded px-3 py-2 text-heading font-mono text-xs focus:outline-none focus:border-primary">
                    <button onclick="window.wfbSaveLabel()" class="px-3 py-1.5 bg-primary/15 hover:bg-primary/25 text-primary-400 border border-primary/30 text-xs font-semibold rounded transition-colors">Save</button>
                </div>
            </div>
            <div class="space-y-1">
                <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Input(s)</label>
                <div id="wfb-panel-inputs" class="flex flex-wrap gap-1"></div>
            </div>
        </div>
        <div id="wfb-panel-body" class="flex-1 overflow-y-auto custom-scrollbar p-4 text-xs space-y-3">
            <div class="text-muted">Select a node on the canvas to configure it.</div>
        </div>
```

with:

```html
    <!-- Right panel: selected node's config, identical fields to its popup where one exists -->
    <div class="w-80 shrink-0 bg-surface border border-border rounded-xl flex flex-col overflow-hidden relative">
        <div class="px-4 py-3 border-b border-border shrink-0">
            <h4 class="text-xs font-semibold text-heading uppercase tracking-wider">Node Configuration</h4>
        </div>
        <div id="wfb-panel-inputs-section" class="hidden px-4 py-3 border-b border-border shrink-0 space-y-1">
            <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Input(s)</label>
            <div id="wfb-panel-inputs" class="flex flex-wrap gap-1"></div>
        </div>
        <div id="wfb-panel-body" class="flex-1 overflow-y-auto custom-scrollbar p-4 text-xs space-y-3">
            <div class="text-muted">Select a node on the canvas to configure it.</div>
        </div>
        <div id="wfb-panel-label-section" class="hidden px-4 py-3 border-t border-border shrink-0 space-y-1.5">
            <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Output Label (reference as {{label}})</label>
            <div class="flex gap-1.5">
                <input type="text" id="wfb-panel-label-input" onkeydown="if (event.key === 'Enter') window.wfbSaveLabel()" class="flex-1 bg-canvas border border-border rounded px-3 py-2 text-heading font-mono text-xs focus:outline-none focus:border-primary">
                <button onclick="window.wfbSaveLabel()" class="px-3 py-1.5 bg-primary/15 hover:bg-primary/25 text-primary-400 border border-primary/30 text-xs font-semibold rounded transition-colors">Save</button>
            </div>
        </div>
```

(Note the border moved from `border-b` to `border-t` on the label section since it now sits at the bottom, visually separating it from `#wfb-panel-body` above it instead of below.)

- [ ] **Step 2: Update `selectNode()` to show both new sections**

In `00_System/templates/workflow-builder.html`, replace (around line 1183-1184):

```javascript
            const header = document.getElementById("wfb-panel-header");
            header.classList.remove("hidden");
```

with:

```javascript
            document.getElementById("wfb-panel-inputs-section").classList.remove("hidden");
            document.getElementById("wfb-panel-label-section").classList.remove("hidden");
```

- [ ] **Step 3: Update `clearPanel()` to hide both new sections**

In `00_System/templates/workflow-builder.html`, replace (around line 1208):

```javascript
            document.getElementById("wfb-panel-header").classList.add("hidden");
```

with:

```javascript
            document.getElementById("wfb-panel-inputs-section").classList.add("hidden");
            document.getElementById("wfb-panel-label-section").classList.add("hidden");
```

- [ ] **Step 4: Manually verify in the browser**

Run: `python 00_System/server.py` (serves on `http://127.0.0.1:8090`), then open `http://127.0.0.1:8090/page/workflow-builder`.

Expected: drag any node onto the canvas and select it. Top-to-bottom in the right panel: "Node Configuration" title, then **Input(s)** chips, then the node-specific settings (e.g. Logic Gate's Condition Type/Value/Go To fields), then **Output Label** at the very bottom. Type a label, click Save — still works. Click a canvas background to deselect — both sections hide again (panel shows only the placeholder text).

- [ ] **Step 5: Commit**

```bash
git add 00_System/templates/workflow-builder.html
git commit -m "Move Output Label to bottom of Node Configuration panel, Inputs to top"
```

---

### Task 2: Safe expression evaluator (`_eval_condition_expression`)

**Files:**
- Modify: `00_System/workflow_engine.py` (add `ast` import, add module-level evaluator functions after the `MissingInputError` class, i.e. after line 118)
- Test: `00_System/test_workflow_engine_conditions.py` (new file)

**Interfaces:**
- Produces: `_eval_condition_expression(expr: str, namespace: Dict[str, Any]) -> bool`, module-level in `workflow_engine.py`. Raises `WorkflowRunError` (already defined at `workflow_engine.py:103`) for invalid syntax, disallowed AST constructs, or a `Name` not present in `namespace`.

- [ ] **Step 1: Write the failing tests**

Create `00_System/test_workflow_engine_conditions.py`:

```python
# 00_System/test_workflow_engine_conditions.py
"""Assert-based smoke tests for the Conditions node: the safe expression
evaluator and the WorkflowEngine._run_conditions branching logic.
Run directly: python test_workflow_engine_conditions.py
"""
import sys
sys.dont_write_bytecode = True

from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from workflow_engine import WorkflowEngine, WorkflowRunError, _eval_condition_expression


def _graph(node_specs):
    """Builds a minimal valid Drawflow-shaped graph_json. node_specs is a list of
    (node_id, label, tool_id, params, outgoing_targets) tuples, all "function" kind
    nodes in the "Home" module, wired in the given order."""
    data = {}
    for node_id, label, tool_id, params, targets in node_specs:
        data[node_id] = {
            "name": tool_id,
            "data": {
                "kind": "function",
                "tool_id": tool_id,
                "category": None,
                "title": label,
                "label": label,
                "params": params,
            },
            "outputs": {
                "output_1": {"connections": [{"node": t, "output": "input_1"} for t in targets]}
            },
        }
    return {"drawflow": {"Home": {"data": data}}}


def test_expression_true_and_false():
    assert _eval_condition_expression("total > 1000", {"total": 1500}) is True
    assert _eval_condition_expression("total > 1000", {"total": 500}) is False


def test_expression_and_or_not():
    ns_west = {"total": 1500, "region": "west"}
    ns_east = {"total": 1500, "region": "east"}
    assert _eval_condition_expression("total > 1000 and region == 'west'", ns_west) is True
    assert _eval_condition_expression("total > 1000 and region == 'west'", ns_east) is False
    assert _eval_condition_expression("not approved", {"approved": False}) is True


def test_expression_unknown_name_raises():
    try:
        _eval_condition_expression("missing_field == 1", {})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_expression_rejects_function_call():
    # Security boundary: a Call node must never execute -- this is the whole
    # reason this isn't Python's eval().
    try:
        _eval_condition_expression("__import__('os').system('echo hi')", {})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


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

Run: `python 00_System/test_workflow_engine_conditions.py`
Expected: `ImportError: cannot import name '_eval_condition_expression'`

- [ ] **Step 3: Add the `ast` import**

In `00_System/workflow_engine.py`, replace line 84:

```python
import re
```

with:

```python
import re
import ast
```

- [ ] **Step 4: Add the evaluator, after `MissingInputError` (after line 118, before `class WorkflowEngine:`)**

```python
# --- Conditions node: safe expression evaluation (no eval(), stdlib only) -------

_CONDITION_COMPARE_OPS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _eval_condition_ast(node: ast.AST, namespace: Dict[str, Any]) -> Any:
    # Whitelist walker: only boolean logic, comparisons, name lookups (against
    # namespace only), and literal constants are ever evaluated. Anything else
    # (Call, Attribute, Subscript, imports, comprehensions, ...) is rejected --
    # this is what makes a user-typed expression safe to run server-side.
    if isinstance(node, ast.Expression):
        return _eval_condition_ast(node.body, namespace)
    if isinstance(node, ast.BoolOp):
        values = [_eval_condition_ast(v, namespace) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_condition_ast(node.operand, namespace)
    if isinstance(node, ast.Compare):
        left = _eval_condition_ast(node.left, namespace)
        for op, comparator in zip(node.ops, node.comparators):
            handler = _CONDITION_COMPARE_OPS.get(type(op))
            if handler is None:
                raise WorkflowRunError(f"Unsupported comparison operator in condition expression: {type(op).__name__}")
            right = _eval_condition_ast(comparator, namespace)
            if not handler(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        if node.id not in namespace:
            raise WorkflowRunError(f"Condition expression references unknown field: {node.id}")
        return namespace[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    raise WorkflowRunError(f"Unsupported syntax in condition expression: {type(node).__name__}")


def _eval_condition_expression(expr: str, namespace: Dict[str, Any]) -> bool:
    # expr is text a workflow author typed into a form field -- it must never
    # be able to call functions, access attributes, or do anything beyond
    # compare values already present in namespace. Deliberately not eval().
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise WorkflowRunError(f"Invalid condition expression: {e}")
    return bool(_eval_condition_ast(tree, namespace))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_conditions.py`
Expected: `4/4 passed`

- [ ] **Step 6: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine_conditions.py
git commit -m "Add stdlib-only safe expression evaluator for Conditions node"
```

---

### Task 3: `_run_conditions` engine handler + dispatch wiring

**Files:**
- Modify: `00_System/workflow_engine.py` (add `Union` to the `typing` import; add `_eval_simple_condition` and `_run_conditions` methods after `_run_logic_gate`, i.e. after line 502; add dispatch branch in `_execute_function_node` after line 591)
- Test: `00_System/test_workflow_engine_conditions.py` (append)

**Interfaces:**
- Consumes: `_eval_condition_expression(expr, namespace) -> bool` from Task 2. `WorkflowEngine._gather_upstream_text(node_id) -> str` (existing, `workflow_engine.py:340`).
- Produces: `WorkflowEngine._run_conditions(self, node_id: str, params: Dict[str, Any]) -> Tuple[str, Optional[Union[str, List[str]]]]`. Param shape consumed: `{"match_mode": "first_match"|"all_matches", "default_target_node_id": str|None, "conditions": [{"mode": "simple"|"expression", "field": str, "operator": str, "value": str, "expression": str, "target_node_id": str}]}` (per spec `docs/superpowers/specs/2026-07-30-workflow-builder-config-reorder-and-conditions-design.md`).

- [ ] **Step 1: Write the failing tests**

Append to `00_System/test_workflow_engine_conditions.py` (before the `if __name__ == "__main__":` block):

```python
def _conditions_engine(upstream_text):
    # Manually wires just enough WorkflowEngine state for _run_conditions to read
    # one upstream node's captured text via _gather_upstream_text, without going
    # through a full engine.run() (whose dry-run AI stubs wrap/prefix their output,
    # which would get in the way of testing exact JSON field extraction here).
    engine = WorkflowEngine(dry_run=True)
    engine.backward_edges = {"cond": ["src"]}
    engine.node_labels = {"src": "Src", "cond": "Cond"}
    engine.context = {"Src": upstream_text}
    return engine


def test_conditions_first_match_stops_at_first_true():
    engine = _conditions_engine('{"status": "approved", "region": "west"}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "status", "operator": "equals", "value": "approved", "target_node_id": "3"},
            {"mode": "simple", "field": "region", "operator": "equals", "value": "west", "target_node_id": "4"},
        ],
    })
    # Both conditions are true; first_match must return only the first one's target.
    assert target == "3", (verdict, target)


def test_conditions_all_matches_returns_every_true_target():
    engine = _conditions_engine('{"status": "approved", "region": "west"}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "all_matches",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "status", "operator": "equals", "value": "approved", "target_node_id": "3"},
            {"mode": "simple", "field": "region", "operator": "equals", "value": "west", "target_node_id": "4"},
            {"mode": "simple", "field": "status", "operator": "equals", "value": "denied", "target_node_id": "5"},
        ],
    })
    assert target == ["3", "4"], (verdict, target)


def test_conditions_default_used_when_none_match():
    engine = _conditions_engine('{"status": "pending"}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "status", "operator": "equals", "value": "approved", "target_node_id": "3"},
        ],
    })
    assert target == "9", (verdict, target)


def test_conditions_numeric_operators():
    engine = _conditions_engine('{"total": 1500}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "total", "operator": "gt", "value": "1000", "target_node_id": "3"},
        ],
    })
    assert target == "3", (verdict, target)

    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "total", "operator": "lt", "value": "1000", "target_node_id": "3"},
        ],
    })
    assert target == "9", (verdict, target)  # 1500 is not < 1000 -- falls through to default


def test_conditions_expression_mode_uses_parsed_fields_and_raw_input():
    engine = _conditions_engine('{"total": 1500, "region": "west"}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "expression", "expression": "total > 1000 and region == 'west'", "target_node_id": "3"},
        ],
    })
    assert target == "3", (verdict, target)

    # "input" is always bound to the raw upstream text, even when it's not JSON.
    engine2 = _conditions_engine("plain text here")
    verdict, target = engine2._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "expression", "expression": "'plain' in input", "target_node_id": "3"},
        ],
    })
    assert target == "3", (verdict, target)


def test_conditions_blank_field_tests_whole_upstream_text():
    engine = _conditions_engine("the quick brown fox")
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "", "operator": "contains", "value": "brown", "target_node_id": "3"},
        ],
    })
    assert target == "3", (verdict, target)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_conditions.py`
Expected: `AttributeError: 'WorkflowEngine' object has no attribute '_run_conditions'`

- [ ] **Step 3: Widen the `typing` import**

In `00_System/workflow_engine.py`, replace line 87:

```python
from typing import Dict, Any, List, Tuple, Optional
```

with:

```python
from typing import Dict, Any, List, Tuple, Optional, Union
```

- [ ] **Step 4: Add `_eval_simple_condition` and `_run_conditions`, after `_run_logic_gate` (after line 502, before the `# --- Built-in node handlers` comment on line 504)**

```python
    _CONDITION_NUMERIC_OPERATORS = {"gt", "gte", "lt", "lte"}

    def _eval_simple_condition(self, cond: Dict[str, Any], fields: Dict[str, Any], upstream_text: str) -> bool:
        # A "simple rule" condition row: field/operator/value, same operator
        # vocabulary as Logic Gate (contains/equals/regex) plus four numeric
        # comparisons. An empty field tests the whole upstream text, exactly
        # like Logic Gate's condition_value does today.
        field_name = cond.get("field") or ""
        operator = cond.get("operator", "contains")
        raw_value = cond.get("value", "")

        if field_name:
            if field_name not in fields:
                return False  # named field not present in parsed upstream JSON
            subject = str(fields[field_name])
        else:
            subject = upstream_text

        if operator in self._CONDITION_NUMERIC_OPERATORS:
            try:
                left, right = float(subject), float(raw_value)
            except ValueError:
                return False
            return {
                "gt": left > right, "gte": left >= right,
                "lt": left < right, "lte": left <= right,
            }[operator]
        if operator == "regex":
            return bool(re.search(raw_value, subject))
        if operator == "equals":
            return subject.strip() == raw_value.strip()
        return raw_value in subject  # "contains" -- also the fallback for an unrecognized operator

    def _run_conditions(self, node_id: str, params: Dict[str, Any]) -> Tuple[str, Optional[Union[str, List[str]]]]:
        # A "Conditions" node: up to 10 rows, each either a simple field/operator/value
        # rule or a free-form expression (_eval_condition_expression), each with its
        # own "Go To" target. match_mode picks whether only the first true row's
        # target fires (switch-style) or every true row's target fires. A row with no
        # target_node_id set is skipped -- it can never "match" anywhere useful.
        upstream_text = self._gather_upstream_text(node_id)
        try:
            parsed = json.loads(upstream_text)
            fields: Dict[str, Any] = parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            fields = {}
        namespace = dict(fields)
        namespace["input"] = upstream_text

        match_mode = params.get("match_mode", "first_match")
        default_target = params.get("default_target_node_id") or None
        conditions = (params.get("conditions") or [])[:10]

        matched_targets: List[str] = []
        for i, cond in enumerate(conditions, start=1):
            target = cond.get("target_node_id") or None
            if not target:
                continue
            if cond.get("mode") == "expression":
                is_match = _eval_condition_expression(cond.get("expression", ""), namespace)
            else:
                is_match = self._eval_simple_condition(cond, fields, upstream_text)
            if is_match:
                matched_targets.append(target)
                if match_mode == "first_match":
                    break

        if not matched_targets:
            return f"No condition matched -> default (node {default_target})", default_target
        if match_mode == "first_match":
            return f"Condition matched (first_match) -> node {matched_targets[0]}", matched_targets[0]
        return (
            f"{len(matched_targets)} condition(s) matched (all_matches) -> nodes {', '.join(matched_targets)}",
            matched_targets,
        )
```

- [ ] **Step 5: Wire dispatch in `_execute_function_node`**

In `00_System/workflow_engine.py`, replace (around line 590-591):

```python
        if tool_id == "function_logic_gate":
            return self._run_logic_gate(node_id, params)
```

with:

```python
        if tool_id == "function_logic_gate":
            return self._run_logic_gate(node_id, params)

        if tool_id == "function_conditions":
            return self._run_conditions(node_id, params)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_conditions.py`
Expected: `10/10 passed`

- [ ] **Step 7: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine_conditions.py
git commit -m "Add WorkflowEngine._run_conditions: Conditions node branching logic"
```

---

### Task 4: `run()` support for multiple queued targets (all_matches)

**Files:**
- Modify: `00_System/workflow_engine.py:539` (`_execute_node` return type), `:575` (`_execute_function_node` return type), `:756-759` (`run()`'s `jump_to` handling)
- Test: `00_System/test_workflow_engine_conditions.py` (append)

**Interfaces:**
- Consumes: `_run_conditions` from Task 3 (dispatched via `_execute_function_node`).
- Produces: `run()` now queues every id in a list `jump_to` at the front of the queue (in order), in addition to its existing single-id behavior.

- [ ] **Step 1: Write the failing tests**

Append to `00_System/test_workflow_engine_conditions.py` (before the `if __name__ == "__main__":` block):

```python
def test_conditions_all_matches_runs_every_target_node_end_to_end():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Src", "function_gemini_ask", {"instructions": "the quick brown fox"}, ["2"]),
        ("2", "Cond", "function_conditions", {
            "match_mode": "all_matches",
            "default_target_node_id": "5",
            "conditions": [
                {"mode": "simple", "field": "", "operator": "contains", "value": "quick", "target_node_id": "3"},
                {"mode": "simple", "field": "", "operator": "contains", "value": "fox", "target_node_id": "4"},
            ],
        }, []),
        ("3", "First", "function_gemini_ask", {"instructions": "AAA"}, []),
        ("4", "Second", "function_gemini_ask", {"instructions": "BBB"}, []),
        ("5", "Default", "function_gemini_ask", {"instructions": "CCC"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    ran_ids = [s["node_id"] for s in result["steps"]]
    # Both matching branches run, in order; the default branch does NOT run.
    assert ran_ids == ["1", "2", "3", "4"], ran_ids


def test_conditions_first_match_runs_only_one_target_node_end_to_end():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Src", "function_gemini_ask", {"instructions": "the quick brown fox"}, ["2"]),
        ("2", "Cond", "function_conditions", {
            "match_mode": "first_match",
            "default_target_node_id": "5",
            "conditions": [
                {"mode": "simple", "field": "", "operator": "contains", "value": "quick", "target_node_id": "3"},
                {"mode": "simple", "field": "", "operator": "contains", "value": "fox", "target_node_id": "4"},
            ],
        }, []),
        ("3", "First", "function_gemini_ask", {"instructions": "AAA"}, []),
        ("4", "Second", "function_gemini_ask", {"instructions": "BBB"}, []),
        ("5", "Default", "function_gemini_ask", {"instructions": "CCC"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    ran_ids = [s["node_id"] for s in result["steps"]]
    assert ran_ids == ["1", "2", "3"], ran_ids
```

- [ ] **Step 2: Run tests to verify the `all_matches` one fails**

Run: `python 00_System/test_workflow_engine_conditions.py`
Expected: `test_conditions_all_matches_runs_every_target_node_end_to_end` FAILs (today `queue.insert(0, jump_to)` inserts the whole list as one malformed queue entry, so node "4" never runs and the run may error trying to look up a list as a node id). `test_conditions_first_match_runs_only_one_target_node_end_to_end` already PASSes (single-string `jump_to` already works).

- [ ] **Step 3: Update return-type annotations**

In `00_System/workflow_engine.py`, replace line 539:

```python
    def _execute_node(self, node_id: str, node: Dict[str, Any]) -> Tuple[str, Optional[str]]:
```

with:

```python
    def _execute_node(self, node_id: str, node: Dict[str, Any]) -> Tuple[str, Optional[Union[str, List[str]]]]:
```

Replace line 575:

```python
    def _execute_function_node(self, node_id: str, node: Dict[str, Any], params: Dict[str, Any]) -> Tuple[str, Optional[str]]:
```

with:

```python
    def _execute_function_node(self, node_id: str, node: Dict[str, Any], params: Dict[str, Any]) -> Tuple[str, Optional[Union[str, List[str]]]]:
```

- [ ] **Step 4: Handle a list `jump_to` in `run()`**

In `00_System/workflow_engine.py`, replace (around lines 756-759):

```python
            if jump_to:
                # A Review Gate (or similar) decided to loop back to an
                # earlier node instead of continuing forward normally.
                queue.insert(0, jump_to)
```

with:

```python
            if jump_to:
                # A Review Gate (or similar) decided to loop back to an
                # earlier node instead of continuing forward normally. A
                # Conditions node in all_matches mode returns a LIST of
                # target ids instead of one -- queue every one of them at
                # the front, in order, same as a single jump_to would be.
                if isinstance(jump_to, list):
                    queue[0:0] = jump_to
                else:
                    queue.insert(0, jump_to)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_conditions.py`
Expected: `12/12 passed`

Also re-run the token tests to confirm nothing broke:

Run: `python 00_System/test_workflow_engine_tokens.py`
Expected: all still passing (same count as before this task).

- [ ] **Step 6: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine_conditions.py
git commit -m "Support queuing multiple jump_to targets for Conditions all_matches mode"
```

---

### Task 5: Register the Conditions node (server.py)

**Files:**
- Modify: `00_System/server.py:216-221` (`FUNCTIONS_REGISTRY`), `:435` area (`TOOL_FA_ICON_MAP`)

**Interfaces:**
- Produces: `function_conditions` appears in `GET /api/workflow-builder/node-registry`'s output (consumed by `workflow-builder.html`'s node palette) with a Font Awesome icon.

- [ ] **Step 1: Add the registry entry**

In `00_System/server.py`, replace (around lines 216-221):

```python
    {
        "tool_id": "function_logic_gate",
        "title": "Logic Gate (If/Else)",
        "description": "Evaluates upstream text against a condition (contains/equals/regex) and branches to a true or false node.",
        "model": None,
    },
```

with:

```python
    {
        "tool_id": "function_logic_gate",
        "title": "Logic Gate (If/Else)",
        "description": "Evaluates upstream text against a condition (contains/equals/regex) and branches to a true or false node.",
        "model": None,
    },
    {
        "tool_id": "function_conditions",
        "title": "Conditions",
        "description": "Evaluates up to 10 conditions (simple rules or expressions) against upstream data and branches to each one's target node; supports first-match or all-matches, with a required default.",
        "model": None,
    },
```

- [ ] **Step 2: Add the icon**

In `00_System/server.py`, replace (around line 435):

```python
    "function_logic_gate": "fa-signs-post",       # if/else branch -- literal signpost
```

with:

```python
    "function_logic_gate": "fa-signs-post",       # if/else branch -- literal signpost
    "function_conditions": "fa-code-branch",      # N-way branch
```

- [ ] **Step 3: Verify the registry serves correctly**

Run: `python 00_System/server.py` (in `00_System/`, background it or run in a separate terminal), then in another shell: `curl http://127.0.0.1:8090/api/workflow-builder/node-registry`
Expected: the JSON response's Functions section includes an entry with `"tool_id": "function_conditions"` and `"title": "Conditions"`. Stop the server after checking.

- [ ] **Step 4: Commit**

```bash
git add 00_System/server.py
git commit -m "Register Conditions function node in FUNCTIONS_REGISTRY"
```

---

### Task 6: Conditions node builder UI

**Files:**
- Modify: `00_System/templates/workflow-builder.html`:
  - `:176-177` (module-level state) — add three new `let`s
  - `:1153-1156` (`renderFunctionPanel`) — add dispatch branch
  - After `renderLogicGatePanel` (after line 1151) — add `renderConditionsPanel`, `renderConditionsBody`, `captureConditionsDraftFromDom`, `wfbAddCondition`, `wfbRemoveCondition`, `wfbSetConditionMode`
  - `:1245-1251` (`wfbSaveNodePanel`) — add `"conditions"` branch

**Interfaces:**
- Consumes: `otherCanvasNodes(nodeId)` (existing, line 971), `escapeHtml` (existing, used throughout), `saveNodeParams(nodeId, params)` (existing, called at the end of `wfbSaveNodePanel`), the `function_conditions` registry entry from Task 5.
- Produces: a working "Conditions" node type selectable from the builder's node palette, configurable in the right panel, whose saved `params` match the shape `_run_conditions` (Task 3) consumes.

- [ ] **Step 1: Add module-level draft state**

In `00_System/templates/workflow-builder.html`, replace lines 176-177:

```javascript
        let selectedNodeId = null;
        let currentModuleName = "Home";
```

with:

```javascript
        let selectedNodeId = null;
        let currentModuleName = "Home";
        // In-progress edits for whichever Conditions node's panel is currently
        // open -- mutated by add/remove/mode-toggle before each re-render, read
        // by wfbSaveNodePanel's "conditions" branch. Reset each time the panel
        // opens for a Conditions node (renderConditionsPanel).
        let wfbConditionsDraft = [];
        let wfbConditionsMatchMode = "first_match";
        let wfbConditionsDefault = "";
```

- [ ] **Step 2: Add the panel render functions, after `renderLogicGatePanel` (after line 1151, before `function renderFunctionPanel`)**

```javascript
        function conditionsNodeOptions(nodeId, selectedId) {
            const otherNodes = otherCanvasNodes(nodeId);
            return `<option value="">-- None --</option>` +
                otherNodes.map(n => `<option value="${n.id}" ${selectedId === n.id ? "selected" : ""}>${escapeHtml(n.title)}</option>`).join("");
        }

        function captureConditionsDraftFromDom() {
            document.querySelectorAll("#wfb-cond-rows [data-condition-row]").forEach(rowEl => {
                const i = parseInt(rowEl.dataset.conditionRow, 10);
                const c = wfbConditionsDraft[i];
                if (!c) return;
                const targetEl = rowEl.querySelector("[data-cond-target]");
                if (targetEl) c.target_node_id = targetEl.value;
                if (c.mode === "expression") {
                    const exprEl = rowEl.querySelector("[data-cond-expression]");
                    if (exprEl) c.expression = exprEl.value;
                } else {
                    const fieldEl = rowEl.querySelector("[data-cond-field]");
                    const operatorEl = rowEl.querySelector("[data-cond-operator]");
                    const valueEl = rowEl.querySelector("[data-cond-value]");
                    if (fieldEl) c.field = fieldEl.value;
                    if (operatorEl) c.operator = operatorEl.value;
                    if (valueEl) c.value = valueEl.value;
                }
            });
            const matchModeEl = document.getElementById("wfb-cond-match-mode");
            if (matchModeEl) wfbConditionsMatchMode = matchModeEl.value;
            const defaultEl = document.getElementById("wfb-cond-default");
            if (defaultEl) wfbConditionsDefault = defaultEl.value;
        }

        function renderConditionsBody(nodeId) {
            const body = document.getElementById("wfb-panel-body");
            const CONDITION_OPERATORS = ["contains", "equals", "regex", "gt", "gte", "lt", "lte"];

            const rowsHtml = wfbConditionsDraft.map((c, i) => `
                <div class="border border-border rounded p-2 mb-2 space-y-1.5" data-condition-row="${i}">
                    <div class="flex items-center justify-between">
                        <span class="text-[10px] text-muted font-mono uppercase">Condition ${i + 1}</span>
                        <button onclick="window.wfbRemoveCondition('${nodeId}', ${i})" class="text-danger-400 hover:text-danger-300 text-[10px]"><i class="fa-solid fa-trash"></i></button>
                    </div>
                    <select onchange="window.wfbSetConditionMode('${nodeId}', ${i}, this.value)" class="w-full bg-canvas border border-border rounded px-2 py-1 text-body text-[11px] focus:outline-none focus:border-primary">
                        <option value="simple" ${c.mode === "simple" ? "selected" : ""}>Simple Rule</option>
                        <option value="expression" ${c.mode === "expression" ? "selected" : ""}>Expression</option>
                    </select>
                    ${c.mode === "expression" ? `
                        <input type="text" data-cond-expression value="${escapeHtml(c.expression || "")}" placeholder="e.g. total > 1000 and region == 'west'" class="w-full bg-canvas border border-border rounded px-2 py-1 text-heading font-mono text-[11px] focus:outline-none focus:border-primary">
                    ` : `
                        <input type="text" data-cond-field value="${escapeHtml(c.field || "")}" placeholder="Field (blank = whole input)" class="w-full bg-canvas border border-border rounded px-2 py-1 text-heading font-mono text-[11px] focus:outline-none focus:border-primary">
                        <select data-cond-operator class="w-full bg-canvas border border-border rounded px-2 py-1 text-body text-[11px] focus:outline-none focus:border-primary">
                            ${CONDITION_OPERATORS.map(op => `<option value="${op}" ${c.operator === op ? "selected" : ""}>${op}</option>`).join("")}
                        </select>
                        <input type="text" data-cond-value value="${escapeHtml(c.value || "")}" placeholder="Value" class="w-full bg-canvas border border-border rounded px-2 py-1 text-heading font-mono text-[11px] focus:outline-none focus:border-primary">
                    `}
                    <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Go To</label>
                    <select data-cond-target class="w-full bg-canvas border border-border rounded px-2 py-1 text-body text-[11px] focus:outline-none focus:border-primary">${conditionsNodeOptions(nodeId, c.target_node_id)}</select>
                </div>
            `).join("");

            body.innerHTML = `
                <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Match Mode</label>
                <select id="wfb-cond-match-mode" class="w-full bg-canvas border border-border rounded px-3 py-2 text-body text-xs focus:outline-none focus:border-primary mb-3">
                    <option value="first_match" ${wfbConditionsMatchMode === "first_match" ? "selected" : ""}>First Match Wins</option>
                    <option value="all_matches" ${wfbConditionsMatchMode === "all_matches" ? "selected" : ""}>All Matches Fire</option>
                </select>
                <div id="wfb-cond-rows">${rowsHtml}</div>
                <button onclick="window.wfbAddCondition('${nodeId}')" ${wfbConditionsDraft.length >= 10 ? "disabled" : ""} class="w-full mt-1 px-3 py-1.5 bg-surface-2 hover:bg-border border border-border-strong text-xs font-mono rounded text-heading transition-colors disabled:opacity-40">+ Add Condition (${wfbConditionsDraft.length}/10)</button>
                <label class="block text-muted font-mono uppercase tracking-wider text-[10px] mt-3">Default -- Go To (required)</label>
                <select id="wfb-cond-default" class="w-full bg-canvas border border-border rounded px-3 py-2 text-body text-xs focus:outline-none focus:border-primary">${conditionsNodeOptions(nodeId, wfbConditionsDefault)}</select>
                <button onclick="window.wfbSaveNodePanel('${nodeId}')" class="w-full mt-3 px-3 py-1.5 bg-primary/15 hover:bg-primary/25 text-primary-400 border border-primary/30 text-xs font-semibold rounded transition-colors">Save Node Config</button>
            `;
            body.dataset.readFn = "conditions";
        }

        function renderConditionsPanel(nodeId, data) {
            const p = data.params || {};
            wfbConditionsDraft = (p.conditions && p.conditions.length)
                ? JSON.parse(JSON.stringify(p.conditions))
                : [{ mode: "simple", field: "", operator: "contains", value: "", expression: "", target_node_id: "" }];
            wfbConditionsMatchMode = p.match_mode || "first_match";
            wfbConditionsDefault = p.default_target_node_id || "";
            renderConditionsBody(nodeId);
        }

        window.wfbAddCondition = function(nodeId) {
            if (wfbConditionsDraft.length >= 10) return;
            captureConditionsDraftFromDom();
            wfbConditionsDraft.push({ mode: "simple", field: "", operator: "contains", value: "", expression: "", target_node_id: "" });
            renderConditionsBody(nodeId);
        };

        window.wfbRemoveCondition = function(nodeId, index) {
            captureConditionsDraftFromDom();
            wfbConditionsDraft.splice(index, 1);
            renderConditionsBody(nodeId);
        };

        window.wfbSetConditionMode = function(nodeId, index, mode) {
            captureConditionsDraftFromDom();
            wfbConditionsDraft[index].mode = mode;
            renderConditionsBody(nodeId);
        };
```

- [ ] **Step 3: Dispatch to it from `renderFunctionPanel`**

In `00_System/templates/workflow-builder.html`, replace (around line 1155):

```javascript
            if (data.tool_id === "function_logic_gate") { renderLogicGatePanel(nodeId, data); return; }
```

with:

```javascript
            if (data.tool_id === "function_logic_gate") { renderLogicGatePanel(nodeId, data); return; }
            if (data.tool_id === "function_conditions") { renderConditionsPanel(nodeId, data); return; }
```

- [ ] **Step 4: Read the draft into `params` in `wfbSaveNodePanel`**

In `00_System/templates/workflow-builder.html`, replace (around lines 1245-1251):

```javascript
            } else if (readFn === "logic-gate") {
                params = {
                    condition_type: body.querySelector("[data-panel-condition-type]").value,
                    condition_value: body.querySelector("[data-panel-condition-value]").value,
                    true_node_id: body.querySelector("[data-panel-true-node]").value || null,
                    false_node_id: body.querySelector("[data-panel-false-node]").value || null,
                };
            }
```

with:

```javascript
            } else if (readFn === "logic-gate") {
                params = {
                    condition_type: body.querySelector("[data-panel-condition-type]").value,
                    condition_value: body.querySelector("[data-panel-condition-value]").value,
                    true_node_id: body.querySelector("[data-panel-true-node]").value || null,
                    false_node_id: body.querySelector("[data-panel-false-node]").value || null,
                };
            } else if (readFn === "conditions") {
                captureConditionsDraftFromDom();
                if (!wfbConditionsDefault) {
                    alert("Conditions node requires a Default -- Go To target.");
                    return;
                }
                params = {
                    match_mode: wfbConditionsMatchMode,
                    default_target_node_id: wfbConditionsDefault,
                    conditions: wfbConditionsDraft.map(c => c.mode === "expression"
                        ? { mode: "expression", expression: c.expression || "", target_node_id: c.target_node_id || null }
                        : { mode: "simple", field: c.field || "", operator: c.operator || "contains", value: c.value || "", target_node_id: c.target_node_id || null }),
                };
            }
```

- [ ] **Step 5: Manually verify in the browser**

Run: `python 00_System/server.py`, open `http://127.0.0.1:8090/page/workflow-builder`.

1. Confirm a "Conditions" entry appears in the Functions section of the node palette (icon: branch/fork glyph), and drag one onto the canvas.
2. Select it — panel shows Match Mode, one Simple Rule condition row, "+ Add Condition (1/10)", and a required Default select.
3. Click "+ Add Condition" repeatedly — new rows appear, counter increments, button disables at 10/10.
4. On one row, switch to "Expression" — Field/Operator/Value inputs are replaced by a single expression text input; typed text in other rows is preserved (not wiped) across this re-render.
5. Remove a row via the trash icon — row disappears, remaining rows keep their entered values.
6. Click "Save Node Config" with no Default selected — an alert blocks the save.
7. Set a Default, set each row's "Go To" to a real node on the canvas (add a couple of plain nodes first, e.g. two Gemini Processor nodes, so the dropdowns have real targets), click Save — no error, `wfbLog` shows the "Saved config" message.
8. Wire something into the Conditions node's input, click the canvas Run button (dry run) — the run log shows the Conditions node executing and jumping to the expected target node(s) based on the dry-run text.

- [ ] **Step 6: Commit**

```bash
git add 00_System/templates/workflow-builder.html
git commit -m "Add Conditions node builder UI: repeatable condition rows, match mode, mandatory default"
```

---

## Self-Review Notes

- **Spec coverage:** Part 1 (reorder) → Task 1. Param shape, operators, mandatory default, match_mode → Tasks 3-4 (engine) and Task 6 (UI). Safe expression evaluator (stdlib-only, whitelist AST) → Task 2. Registry/icon → Task 5. Testing section's six scenarios are covered across Tasks 2-4's test functions (first_match, all_matches, default in both modes, expression basics, expression security boundary, numeric operators). Out-of-scope items (real multi-port canvas, nested boolean UI, persistence changes, migration) are untouched by every task above, consistent with the spec.
- **Placeholder scan:** no TBD/TODO; every step has literal code or literal manual-verification instructions.
- **Type consistency:** `_run_conditions` return type (`Tuple[str, Optional[Union[str, List[str]]]]`) matches the widened `_execute_node`/`_execute_function_node` annotations from Task 4, and matches how `run()` consumes `jump_to` in Task 4 Step 4. The params dict keys used in Task 6's UI (`match_mode`, `default_target_node_id`, `conditions[].mode/field/operator/value/expression/target_node_id`) match exactly what `_run_conditions` (Task 3) and `_eval_simple_condition` (Task 3) read.
