# Flow Control & Data Operations Function Nodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 20 new Power Automate-style `Function` nodes to the Workflow Builder — Compose, Parse JSON, HTTP, Response, Terminate, Delay, Delay Until, and the array data-op family (Filter Array, Select, Join, Sort, Union, Chunk, Length, First, Last, Take, Skip, Create CSV Table, Create HTML Table).

**Architecture:** Every node is additive to the existing `_execute_function_node` if/elif ladder in `workflow_engine.py` and the declarative `FUNCTION_FIELD_SCHEMAS` table in `workflow-builder.html` — no changes to graph parsing, token substitution, or `_pick_next` scheduling. Two small engine-level additions support the whole batch: a `WorkflowTerminate` exception that short-circuits `run()`'s loop (for the Terminate node), and a `responses` list plus `terminated` field added to `run()`'s return dict (both additive keys — `server.py`'s `run_workflow` endpoint returns the dict verbatim, no contract change needed there).

**Tech Stack:** Python stdlib (`ast` reuse, `time`, `datetime`, `csv`, `io`, `html`) plus `requests` (already a dependency) for the HTTP node. No new third-party dependency. Frontend is the existing vanilla-JS Drawflow-based builder (`00_System/templates/workflow-builder.html`) — one new declarative field type (`select`), no new framework.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-30-flow-control-and-data-operations-design.md` — every task below implements a named part of that spec; consult it for the full rationale behind a design choice if a task's summary isn't enough.
- No new third-party dependency — `requests` is already in `requirements.txt`; everything else uses stdlib.
- Test convention for this repo: co-located `test_<module>.py` in `00_System/`, plain `assert`, run directly via `python test_<module>.py` (no pytest fixtures, no `tests/` directory) — see `00_System/test_workflow_engine_conditions.py`.
- Data-shape nodes (Parse JSON, all array ops) read their input from `self._gather_upstream_text(node_id)` — no bound "Input" field. `Union` is the one exception and uses `_direct_predecessor_texts(node_id)` instead, since it needs each predecessor's array kept separate.
- Scalar-returning ops (`Length`, `Join`, `First`/`Last` on a plain value) return plain text, not a JSON-quoted string, so `{{label}}` substitution reads naturally in later prompts. Array/object results are always `json.dumps(..., indent=2)`.
- HTTP: 30s request timeout, 5000-char response body cap, both fixed constants — no per-node configuration in this slice.
- Delay / Delay Until: real `time.sleep`, capped at `MAX_DELAY_SECONDS = 300` (5 minutes) — over-cap raises `WorkflowRunError` instead of sleeping.
- Every new node type needs three things to be visible/usable: (1) an `_execute_function_node` dispatch branch in `workflow_engine.py`, (2) a `FUNCTIONS_REGISTRY` + `TOOL_FA_ICON_MAP` entry in `server.py`, (3) a `FUNCTION_FIELD_SCHEMAS` entry in `workflow-builder.html`. Every task below does all three for its node(s).

---

### Task 1: Shared engine helpers

**Files:**
- Modify: `00_System/workflow_engine.py` (add `_parse_json_array`, `_dotted_get`, `_array_item_to_text` methods to `WorkflowEngine`, after `_direct_predecessor_texts`, i.e. after line 406)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (new file)

**Interfaces:**
- Produces:
  - `WorkflowEngine._parse_json_array(self, node_id: str, friendly_name: str) -> list` — reads `self._gather_upstream_text(node_id)`, raises `WorkflowRunError` (existing, `workflow_engine.py:104`) if it isn't valid JSON or isn't a list.
  - `WorkflowEngine._dotted_get(self, obj: Any, path: str) -> Any` — dict-only dotted-path lookup; `path == ""` returns `obj` unchanged; a missing key at any level returns `None`.
  - `WorkflowEngine._array_item_to_text(self, value: Any) -> str` — `dict`/`list` → `json.dumps(value, indent=2)`; `None` → `""`; anything else → `str(value)`.

- [ ] **Step 1: Write the failing tests**

Create `00_System/test_workflow_engine_flow_and_data_ops.py`:

```python
# 00_System/test_workflow_engine_flow_and_data_ops.py
"""Assert-based smoke tests for the flow-control and data-operation Function
nodes (Compose, Parse JSON, HTTP, Response, Terminate, Delay, Delay Until,
and the array data-op family). Run directly: python test_workflow_engine_flow_and_data_ops.py
"""
import sys
sys.dont_write_bytecode = True

from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from workflow_engine import WorkflowEngine, WorkflowRunError, WorkflowTerminate


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


def _single_input_engine(node_id, upstream_text):
    # Manually wires just enough WorkflowEngine state for a function handler to
    # read one upstream node's captured text via _gather_upstream_text, without
    # a full engine.run() -- mirrors test_workflow_engine_conditions.py's
    # _conditions_engine helper.
    engine = WorkflowEngine(dry_run=True)
    engine.backward_edges = {node_id: ["src"]}
    engine.node_labels = {"src": "Src", node_id: "Node"}
    engine.context = {"Src": upstream_text}
    return engine


def test_parse_json_array_valid():
    engine = _single_input_engine("n", '[{"a": 1}, {"a": 2}]')
    arr = engine._parse_json_array("n", "TestOp")
    assert arr == [{"a": 1}, {"a": 2}], arr


def test_parse_json_array_invalid_json_raises():
    engine = _single_input_engine("n", "not json")
    try:
        engine._parse_json_array("n", "TestOp")
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_parse_json_array_non_list_raises():
    engine = _single_input_engine("n", '{"a": 1}')
    try:
        engine._parse_json_array("n", "TestOp")
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_dotted_get():
    engine = WorkflowEngine(dry_run=True)
    assert engine._dotted_get({"user": {"name": "Alice"}}, "user.name") == "Alice"
    assert engine._dotted_get({"user": {"name": "Alice"}}, "user.missing") is None
    assert engine._dotted_get({"a": 1}, "") == {"a": 1}
    assert engine._dotted_get("not a dict", "a.b") is None


def test_array_item_to_text():
    engine = WorkflowEngine(dry_run=True)
    assert engine._array_item_to_text({"a": 1}) == '{\n  "a": 1\n}'
    assert engine._array_item_to_text([1, 2]) == "[\n  1,\n  2\n]"
    assert engine._array_item_to_text("Alice") == "Alice"
    assert engine._array_item_to_text(42) == "42"
    assert engine._array_item_to_text(None) == ""


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

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `ImportError: cannot import name 'WorkflowTerminate'` (added in Task 6, imported here up front since every test file in this task family imports it) — comment out the `WorkflowTerminate` import and the three `_parse_json_array`/`_dotted_get`/`_array_item_to_text` tests will instead fail with `AttributeError: 'WorkflowEngine' object has no attribute '_parse_json_array'`. Leave the import in place; it will resolve once Task 6 lands (this file accumulates tests across Tasks 1-11, matching the `test_workflow_engine_conditions.py` convention of one shared file appended to task-by-task). For this task, temporarily verify with: `python -c "from workflow_engine import WorkflowEngine; WorkflowEngine(dry_run=True)._parse_json_array('n','x')"` instead, expecting `AttributeError`.

- [ ] **Step 3: Add the helpers**

In `00_System/workflow_engine.py`, add after `_direct_predecessor_texts` (after line 406, before `_gather_upstream_text`):

```python
    def _parse_json_array(self, node_id: str, friendly_name: str) -> list:
        """Shared by every array-op node. Raises WorkflowRunError naming the
        node type on invalid JSON or a non-list top-level value."""
        text = self._gather_upstream_text(node_id)
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError) as e:
            raise WorkflowRunError(f"{friendly_name} requires a JSON array as input; got invalid JSON: {e}")
        if not isinstance(parsed, list):
            raise WorkflowRunError(f"{friendly_name} requires a JSON array as input; got {type(parsed).__name__}.")
        return parsed

    def _dotted_get(self, obj: Any, path: str) -> Any:
        """Dict-only dotted-path lookup (no list indices, no expressions) -- used by
        Select/Join/Sort/Union for 'pull this nested field out of each item.' Missing
        key at any level returns None rather than raising: a per-item lookup miss
        just produces a null field on that item, consistent with Select's
        row-independent design (one bad item shouldn't kill the whole array)."""
        if not path:
            return obj
        current = obj
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    def _array_item_to_text(self, value: Any) -> str:
        # Object/array items round-trip through JSON (so a later Parse JSON node
        # still works on them); bare scalars get unquoted plain text so
        # {{label}} substitution into a later prompt reads as Alice, not "Alice".
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2)
        return "" if value is None else str(value)
```

- [ ] **Step 4: Run tests to verify they pass**

Temporarily remove the `WorkflowTerminate` import (it doesn't exist until Task 6) and run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `5/5 passed`. Restore the `WorkflowTerminate` import afterward — Task 6 will make it valid again; until then leave a `# noqa: added in Task 6` style comment if your editor's linter complains, or simply proceed to Task 2 without restoring it yet (it will be re-added naturally as Task 6's Step 1 rewrites this file's test-import line).

- [ ] **Step 5: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add shared _parse_json_array/_dotted_get/_array_item_to_text helpers"
```

---

### Task 2: Frontend `select` field type

**Files:**
- Modify: `00_System/templates/workflow-builder.html` (`renderGenericFunctionFields`, lines 570-592)

**Interfaces:**
- Produces: `FUNCTION_FIELD_SCHEMAS` entries can now include `{ key, label, type: "select", options: [...] }`, rendered as a `<select>` populated from `options` (plain strings, used as both value and label). `readGenericFunctionFields` (lines 594-604) needs **no change** — `el.value` already reads a `<select>` the same as an `<input>`.

- [ ] **Step 1: Add the `select` branch**

In `00_System/templates/workflow-builder.html`, replace (lines 573-587):

```javascript
            const fieldsHtml = schema.map(f => {
                const raw = (p[f.key] !== undefined && p[f.key] !== null) ? p[f.key] : "";
                const val = escapeHtml(raw);
                const monoClass = f.mono ? "font-mono" : "";
                if (f.type === "textarea") {
                    return `
                        <label class="block text-muted font-mono uppercase tracking-wider text-[10px] mt-3 first:mt-0">${f.label}</label>
                        <textarea data-panel-field="${f.key}" rows="4" placeholder="${escapeHtml(f.placeholder || "")}" class="w-full bg-canvas border border-border rounded px-3 py-2 text-heading text-[11px] ${monoClass} focus:outline-none focus:border-primary custom-scrollbar resize-none">${val}</textarea>
                    `;
                }
                return `
                    <label class="block text-muted font-mono uppercase tracking-wider text-[10px] mt-3 first:mt-0">${f.label}</label>
                    <input type="${f.type === "number" ? "number" : "text"}" data-panel-field="${f.key}" value="${val}" placeholder="${escapeHtml(f.placeholder || "")}" class="w-full bg-canvas border border-border rounded px-3 py-2 text-heading text-xs ${monoClass} focus:outline-none focus:border-primary">
                `;
            }).join("");
```

with:

```javascript
            const fieldsHtml = schema.map(f => {
                const raw = (p[f.key] !== undefined && p[f.key] !== null) ? p[f.key] : "";
                const val = escapeHtml(raw);
                const monoClass = f.mono ? "font-mono" : "";
                if (f.type === "textarea") {
                    return `
                        <label class="block text-muted font-mono uppercase tracking-wider text-[10px] mt-3 first:mt-0">${f.label}</label>
                        <textarea data-panel-field="${f.key}" rows="4" placeholder="${escapeHtml(f.placeholder || "")}" class="w-full bg-canvas border border-border rounded px-3 py-2 text-heading text-[11px] ${monoClass} focus:outline-none focus:border-primary custom-scrollbar resize-none">${val}</textarea>
                    `;
                }
                if (f.type === "select") {
                    const options = (f.options || []).map(o => `<option value="${escapeHtml(o)}" ${o === raw ? "selected" : ""}>${escapeHtml(o)}</option>`).join("");
                    return `
                        <label class="block text-muted font-mono uppercase tracking-wider text-[10px] mt-3 first:mt-0">${f.label}</label>
                        <select data-panel-field="${f.key}" class="w-full bg-canvas border border-border rounded px-3 py-2 text-body text-xs focus:outline-none focus:border-primary">${options}</select>
                    `;
                }
                return `
                    <label class="block text-muted font-mono uppercase tracking-wider text-[10px] mt-3 first:mt-0">${f.label}</label>
                    <input type="${f.type === "number" ? "number" : "text"}" data-panel-field="${f.key}" value="${val}" placeholder="${escapeHtml(f.placeholder || "")}" class="w-full bg-canvas border border-border rounded px-3 py-2 text-heading text-xs ${monoClass} focus:outline-none focus:border-primary">
                `;
            }).join("");
```

- [ ] **Step 2: Manually verify**

This has no consuming schema entry yet (Task 4 adds the first one, HTTP's `method` field). Verify syntactically by running: `python 00_System/server.py`, open `http://127.0.0.1:8090/page/workflow-builder`, confirm the page loads with no JS console errors (no existing schema uses `type: "select"` yet, so this is a no-op-safe change — full visual verification happens in Task 4).

- [ ] **Step 3: Commit**

```bash
git add 00_System/templates/workflow-builder.html
git commit -m "Add select field type support to Function node config panel"
```

---

### Task 3: Compose & Parse JSON

**Files:**
- Modify: `00_System/workflow_engine.py` (`_execute_function_node`, add branches after the `function_conditions` branch, i.e. after line 737)
- Modify: `00_System/server.py` (`FUNCTIONS_REGISTRY` after line 276's `function_notebooklm_prompt_loop` entry closes... actually insert after `function_conditions` entry, ~line 227; `TOOL_FA_ICON_MAP` ~line 444)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS`, add after `function_concatenate` entry, ~line 540)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (append)

**Interfaces:**
- Produces: `tool_id` `"function_compose"` (params: `{"value": str}`) and `"function_parse_json"` (params: `{"required_keys": str}`, newline-separated) dispatched in `_execute_function_node`.

- [ ] **Step 1: Write the failing tests**

Append to `00_System/test_workflow_engine_flow_and_data_ops.py` (before `if __name__ == "__main__":`):

```python
def test_compose_substitutes_tokens():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Name", "function_gemini_ask", {"instructions": "Alice"}, ["2"]),
        ("2", "Greeting", "function_compose", {"value": "Hello, {{Name}}!"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    assert result["steps"][1]["output"] == "Hello, [DRY RUN] Simulated Gemini response for prompt:\nAlice!"


def test_parse_json_valid_passthrough():
    engine = _single_input_engine("n", '{"a": 1}')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_parse_json"}, {"required_keys": ""})
    assert json.loads(output) == {"a": 1}
    assert jump is None


def test_parse_json_invalid_raises():
    engine = _single_input_engine("n", "not json")
    try:
        engine._execute_function_node("n", {"tool_id": "function_parse_json"}, {"required_keys": ""})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_parse_json_missing_required_key_raises():
    engine = _single_input_engine("n", '{"a": 1}')
    try:
        engine._execute_function_node("n", {"tool_id": "function_parse_json"}, {"required_keys": "a\nb"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError as e:
        assert "b" in str(e)


def test_parse_json_present_required_keys_pass():
    engine = _single_input_engine("n", '{"a": 1, "b": 2}')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_parse_json"}, {"required_keys": "a\nb"})
    assert json.loads(output) == {"a": 1, "b": 2}
```

Add `import json` to the test file's top-level imports (needed by these tests): in `00_System/test_workflow_engine_flow_and_data_ops.py`, replace `sys.dont_write_bytecode = True` with:

```python
sys.dont_write_bytecode = True
import json
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `AttributeError`/dispatch failure — `_execute_function_node` raises `WorkflowRunError(f"Unknown function tool_id: {tool_id}")` for both new tool_ids, so `test_compose_substitutes_tokens` fails on the run's step showing a `WorkflowRunError` output instead of `"Hello, ...!"`, and the two "valid"/"present" Parse JSON tests raise `WorkflowRunError` where they expect success.

- [ ] **Step 3: Add the dispatch branches**

In `00_System/workflow_engine.py`, add after the `function_conditions` branch (after line 737, before the `AI_PROMPT_NODES` block):

```python
        if tool_id == "function_compose":
            return self._substitute_tokens(params.get("value", "")), None

        if tool_id == "function_parse_json":
            text = self._gather_upstream_text(node_id)
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError) as e:
                raise WorkflowRunError(f"Parse JSON: invalid JSON input: {e}")
            required = [k.strip() for k in self._substitute_tokens(params.get("required_keys", "")).splitlines() if k.strip()]
            if required:
                if not isinstance(parsed, dict):
                    raise WorkflowRunError(f"Parse JSON: required keys given but input is a {type(parsed).__name__}, not an object.")
                missing = [k for k in required if k not in parsed]
                if missing:
                    raise WorkflowRunError(f"Parse JSON: missing required key(s): {', '.join(missing)}")
            return json.dumps(parsed, indent=2), None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: all tests in the file so far pass (10/10).

- [ ] **Step 5: Register both nodes**

In `00_System/server.py`, add to `FUNCTIONS_REGISTRY` after the `function_conditions` entry:

```python
    {
        "tool_id": "function_compose",
        "title": "Compose",
        "description": "Passes a value (with {{label}} substitution) through unchanged -- a named checkpoint value for later steps to reference.",
        "model": None,
    },
    {
        "tool_id": "function_parse_json",
        "title": "Parse JSON",
        "description": "Validates upstream data is valid JSON and (optionally) that required top-level keys are present; re-emits it pretty-printed.",
        "model": None,
    },
```

Add to `TOOL_FA_ICON_MAP`:

```python
    "function_compose": "fa-cube",
    "function_parse_json": "fa-file-code",
```

- [ ] **Step 6: Add builder UI schemas**

In `00_System/templates/workflow-builder.html`, add to `FUNCTION_FIELD_SCHEMAS` after `function_concatenate`:

```javascript
            function_compose: [
                { key: "value", label: "Value", type: "textarea", placeholder: "e.g. {{label}} or a literal value" },
            ],
            function_parse_json: [
                { key: "required_keys", label: "Required Keys (optional, one per line)", type: "textarea", mono: true },
            ],
```

- [ ] **Step 7: Manually verify in the browser**

Run: `python 00_System/server.py`, open `http://127.0.0.1:8090/page/workflow-builder`. Confirm "Compose" and "Parse JSON" appear in the Functions palette. Drag a Compose node, configure a Value, wire something into it, dry-run — confirm the log shows the substituted output. Drag a Parse JSON node, feed it valid JSON, dry-run, confirm it re-emits the JSON pretty-printed.

- [ ] **Step 8: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add Compose and Parse JSON function nodes"
```

---

### Task 4: HTTP node

**Files:**
- Modify: `00_System/workflow_engine.py` (`_execute_function_node`, add branch after Task 3's additions)
- Modify: `00_System/server.py` (registry + icon)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS`, using the `select` type from Task 2)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (append)

**Interfaces:**
- Produces: `tool_id` `"function_http"`, params `{"method": str, "uri": str, "headers": str, "body": str}`. Live-mode success output: `json.dumps({"status_code": int, "headers": dict, "body": str})`. Non-2xx or network error raises `WorkflowRunError`.

- [ ] **Step 1: Write the failing tests**

Append to `00_System/test_workflow_engine_flow_and_data_ops.py`:

```python
from unittest.mock import patch, MagicMock


def test_http_dry_run_no_network_call():
    engine = _single_input_engine("n", "")
    with patch("requests.request") as mock_request:
        output, jump = engine._execute_function_node("n", {"tool_id": "function_http"}, {
            "method": "GET", "uri": "https://example.com/api", "headers": "", "body": "",
        })
    mock_request.assert_not_called()
    assert "https://example.com/api" in output


def test_http_live_success():
    engine = WorkflowEngine(dry_run=False)
    engine.backward_edges, engine.node_labels, engine.context = {}, {}, {}
    mock_resp = MagicMock(status_code=200, headers={"Content-Type": "application/json"}, text='{"ok": true}')
    with patch("requests.request", return_value=mock_resp) as mock_request:
        output, jump = engine._execute_function_node("n", {"tool_id": "function_http"}, {
            "method": "POST", "uri": "https://example.com/api", "headers": '{"X-Test": "1"}', "body": '{"x": 1}',
        })
    mock_request.assert_called_once_with("POST", "https://example.com/api", headers={"X-Test": "1"}, data='{"x": 1}', timeout=30)
    parsed = json.loads(output)
    assert parsed["status_code"] == 200
    assert parsed["body"] == '{"ok": true}'


def test_http_non_2xx_raises():
    engine = WorkflowEngine(dry_run=False)
    engine.backward_edges, engine.node_labels, engine.context = {}, {}, {}
    mock_resp = MagicMock(status_code=404, reason="Not Found", text="no such resource")
    with patch("requests.request", return_value=mock_resp):
        try:
            engine._execute_function_node("n", {"tool_id": "function_http"}, {
                "method": "GET", "uri": "https://example.com/missing", "headers": "", "body": "",
            })
            assert False, "expected WorkflowRunError"
        except WorkflowRunError as e:
            assert "404" in str(e)


def test_http_blank_uri_raises():
    engine = _single_input_engine("n", "")
    try:
        engine._execute_function_node("n", {"tool_id": "function_http"}, {"method": "GET", "uri": "", "headers": "", "body": ""})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `WorkflowRunError: Unknown function tool_id: function_http` on all four new tests.

- [ ] **Step 3: Add the dispatch branch**

In `00_System/workflow_engine.py`, add `import requests` near the top (alongside the other stdlib imports — `requests` is a third-party import, group it in its own small block after the stdlib `import` lines, before `from core_router import CoreRouter`):

```python
import requests
```

Add after Task 3's `function_parse_json` branch:

```python
        if tool_id == "function_http":
            method = (params.get("method") or "GET").upper()
            uri = self._substitute_tokens(params.get("uri", ""))
            if not uri.strip():
                raise WorkflowRunError("HTTP requires a URI.")
            headers_text = self._substitute_tokens(params.get("headers", "")).strip()
            headers = {}
            if headers_text:
                try:
                    headers = json.loads(headers_text)
                except (TypeError, ValueError) as e:
                    raise WorkflowRunError(f"HTTP: Headers must be a JSON object: {e}")
            body = self._substitute_tokens(params.get("body", ""))

            if self.dry_run:
                return f"[DRY RUN] Would {method} {uri}", None

            try:
                resp = requests.request(method, uri, headers=headers, data=body or None, timeout=30)
            except requests.exceptions.RequestException as e:
                raise WorkflowRunError(f"HTTP {method} {uri} failed: {e}")

            if resp.status_code >= 400:
                raise WorkflowRunError(f"HTTP {method} {uri} failed: {resp.status_code} {resp.reason}\n{resp.text[:1000]}")

            return json.dumps({
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text[:5000],
            }, indent=2), None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: all tests pass (14/14).

- [ ] **Step 5: Register the node**

In `00_System/server.py` `FUNCTIONS_REGISTRY`:

```python
    {
        "tool_id": "function_http",
        "title": "HTTP",
        "description": "Generic REST API request (GET/POST/PUT/PATCH/DELETE). A non-2xx response fails the step with the status code and body, for troubleshooting.",
        "model": None,
    },
```

`TOOL_FA_ICON_MAP`:

```python
    "function_http": "fa-globe",
```

- [ ] **Step 6: Add the builder UI schema (uses Task 2's `select` type)**

In `00_System/templates/workflow-builder.html` `FUNCTION_FIELD_SCHEMAS`:

```javascript
            function_http: [
                { key: "method", label: "Method", type: "select", options: ["GET", "POST", "PUT", "PATCH", "DELETE"] },
                { key: "uri", label: "URI", type: "text", mono: true, placeholder: "https://api.example.com/..." },
                { key: "headers", label: "Headers (JSON object, optional)", type: "textarea", mono: true, placeholder: '{"Authorization": "Bearer {{token}}"}' },
                { key: "body", label: "Body (optional)", type: "textarea", mono: true },
            ],
```

- [ ] **Step 7: Manually verify in the browser**

Run: `python 00_System/server.py`, open the builder. Drag an HTTP node — confirm the Method dropdown renders and defaults sensibly, fill in a real public GET URL (e.g. `https://httpbin.org/get`), run live (not dry-run) — confirm success shows status 200 in the log. Point it at a URL that 404s — confirm the step shows as failed (red) with the status code visible.

- [ ] **Step 8: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add HTTP function node"
```

---

### Task 5: Response node

**Files:**
- Modify: `00_System/workflow_engine.py` (`__init__` — add `self.responses`; `_execute_function_node` — add branch; `run()` — record responses)
- Modify: `00_System/server.py` (registry + icon)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS` — empty array entry)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (append)

**Interfaces:**
- Produces: `tool_id` `"function_response"`, no params. `WorkflowEngine.responses: List[Dict[str, str]]`, populated during `run()`. `run()`'s return dict gains `"responses": self.responses`.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_response_passes_through_and_is_recorded():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Src", "function_compose", {"value": "final answer"}, ["2"]),
        ("2", "Out", "function_response", {}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    assert result["responses"] == [{"node_id": "2", "label": "Out", "output": "final answer"}], result["responses"]


def test_response_absent_when_no_response_node():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([("1", "Src", "function_compose", {"value": "x"}, [])])
    result = engine.run(graph)
    assert result["responses"] == [], result["responses"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `KeyError: 'responses'` (not yet in `run()`'s return dict) or a `WorkflowRunError` from the unknown `function_response` tool_id.

- [ ] **Step 3: Add `self.responses` to `__init__`**

In `00_System/workflow_engine.py`, in `WorkflowEngine.__init__` (after `self.log: List[Dict[str, Any]] = []`, ~line 230):

```python
        # Every "function_response" node's captured output, in execution order --
        # a workflow's explicitly declared output(s), since Cortex has no external
        # caller yet for a Response node to literally respond to.
        self.responses: List[Dict[str, str]] = []
```

- [ ] **Step 4: Add the dispatch branch**

After Task 4's `function_http` branch:

```python
        if tool_id == "function_response":
            return self._gather_upstream_text(node_id), None
```

- [ ] **Step 5: Record responses in `run()`**

In `00_System/workflow_engine.py`'s `run()`, right after `self.context[label] = output_text` and its `self.log.append(...)` (the success path, ~line 886-890), add:

```python
                if node.get("tool_id") == "function_response":
                    self.responses.append({"node_id": node_id, "label": label, "output": output_text})
```

Update `run()`'s final return statement to include `responses`:

```python
        return {"success": overall_success, "steps": self.log, "responses": self.responses}
```

(`terminated` is added to this same return statement in Task 6 — don't worry about it yet here.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: all pass (16/16).

- [ ] **Step 7: Register the node**

`FUNCTIONS_REGISTRY`:

```python
    {
        "tool_id": "function_response",
        "title": "Response",
        "description": "Marks its connected input as one of the workflow's declared final outputs (Cortex workflows have no external caller yet -- this records intent, not an HTTP reply).",
        "model": None,
    },
```

`TOOL_FA_ICON_MAP`:

```python
    "function_response": "fa-reply",
```

- [ ] **Step 8: Add builder UI schema**

`FUNCTION_FIELD_SCHEMAS`:

```javascript
            function_response: [],
```

- [ ] **Step 9: Manually verify in the browser**

Drag a Response node, wire something into it, dry-run — confirm the panel shows "This function needs no configuration" and the run completes normally.

- [ ] **Step 10: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add Response function node"
```

---

### Task 6: Terminate node

**Files:**
- Modify: `00_System/workflow_engine.py` (new `WorkflowTerminate` exception; `__init__` — add `self.terminated`; `_execute_function_node` — add branch; `run()` — catch it and stop, update return dict)
- Modify: `00_System/server.py` (registry + icon)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS`)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (append)

**Interfaces:**
- Produces: `WorkflowTerminate(Exception)` with `.status: str`, `.message: str`. `tool_id` `"function_terminate"`, params `{"status": "Succeeded"|"Failed"|"Cancelled", "message": str}`. `WorkflowEngine.terminated: Optional[Dict[str, str]]`. `run()`'s return dict gains `"terminated": self.terminated`; `overall_success` is `self.terminated["status"] == "Succeeded"` when terminated, else the existing all-steps-succeeded check.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_terminate_failed_stops_run_before_later_node():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Stop", "function_terminate", {"status": "Failed", "message": "stopping here"}, ["2"]),
        ("2", "Never", "function_compose", {"value": "should not run"}, []),
    ])
    result = engine.run(graph)
    assert result["success"] is False, result
    assert result["terminated"] == {"status": "Failed", "message": "stopping here"}, result["terminated"]
    ran_ids = [s["node_id"] for s in result["steps"]]
    assert ran_ids == ["1"], ran_ids


def test_terminate_succeeded_marks_run_successful():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([("1", "Stop", "function_terminate", {"status": "Succeeded", "message": "done"}, [])])
    result = engine.run(graph)
    assert result["success"] is True, result
    assert result["terminated"]["status"] == "Succeeded"


def test_no_terminate_leaves_terminated_none():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([("1", "Src", "function_compose", {"value": "x"}, [])])
    result = engine.run(graph)
    assert result["terminated"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `KeyError: 'terminated'` and/or `WorkflowRunError: Unknown function tool_id: function_terminate` (which today would be caught by `run()`'s generic `except Exception`, marking node "1" as a **failed** step rather than stopping the run before node "2" — so `ran_ids` would incorrectly be `["1", "2"]`).

- [ ] **Step 3: Add the `WorkflowTerminate` exception**

In `00_System/workflow_engine.py`, after `MissingInputError` (after line 119):

```python
class WorkflowTerminate(Exception):
    # Deliberately NOT a WorkflowRunError subclass -- it must not fall into
    # run()'s generic per-step failure handling. It needs its own except
    # clause that stops the whole run rather than continuing to the next
    # queued node.
    def __init__(self, status: str, message: str):
        self.status = status
        self.message = message
        super().__init__(message)
```

- [ ] **Step 4: Add `self.terminated` to `__init__`**

Alongside `self.responses` from Task 5:

```python
        self.terminated: Optional[Dict[str, str]] = None
```

- [ ] **Step 5: Add the dispatch branch**

After Task 5's `function_response` branch:

```python
        if tool_id == "function_terminate":
            status = params.get("status", "Failed")
            message = self._substitute_tokens(params.get("message", ""))
            raise WorkflowTerminate(status, message)
```

- [ ] **Step 6: Catch it in `run()`'s loop**

In `00_System/workflow_engine.py`'s `run()`, the existing per-node block is:

```python
            try:
                output_text, jump_to = self._execute_node(node_id, node)
                label = self.node_labels.get(node_id, node_id)
                self.context[label] = output_text
                if node.get("tool_id") == "function_response":
                    self.responses.append({"node_id": node_id, "label": label, "output": output_text})
                self.log.append({
                    "node_id": node_id, "title": node["title"], "kind": node["kind"],
                    "status": "success", "output": (output_text or "")[:600],
                })
            except Exception as e:
```

Insert a new `except WorkflowTerminate` clause **before** `except Exception`:

```python
            try:
                output_text, jump_to = self._execute_node(node_id, node)
                label = self.node_labels.get(node_id, node_id)
                self.context[label] = output_text
                if node.get("tool_id") == "function_response":
                    self.responses.append({"node_id": node_id, "label": label, "output": output_text})
                self.log.append({
                    "node_id": node_id, "title": node["title"], "kind": node["kind"],
                    "status": "success", "output": (output_text or "")[:600],
                })
            except WorkflowTerminate as e:
                self.log.append({
                    "node_id": node_id, "title": node.get("title", node_id), "kind": node.get("kind"),
                    "status": "terminated", "output": e.message,
                })
                self.terminated = {"status": e.status, "message": e.message}
                break
            except Exception as e:
```

- [ ] **Step 7: Update `run()`'s final return**

Replace:

```python
        overall_success = bool(self.log) and all(s["status"] == "success" for s in self.log)
        return {"success": overall_success, "steps": self.log, "responses": self.responses}
```

with:

```python
        if self.terminated:
            overall_success = self.terminated["status"] == "Succeeded"
        else:
            overall_success = bool(self.log) and all(s["status"] == "success" for s in self.log)
        return {"success": overall_success, "steps": self.log, "responses": self.responses, "terminated": self.terminated}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: all pass (19/19). Also re-run `python 00_System/test_workflow_engine_conditions.py` and `python 00_System/test_workflow_engine_tokens.py` to confirm the `run()` changes didn't break existing behavior — expect all still passing at their prior counts.

- [ ] **Step 9: Register the node**

`FUNCTIONS_REGISTRY`:

```python
    {
        "tool_id": "function_terminate",
        "title": "Terminate",
        "description": "Ends the workflow run immediately with a declared status (Succeeded/Failed/Cancelled) and message.",
        "model": None,
    },
```

`TOOL_FA_ICON_MAP`:

```python
    "function_terminate": "fa-flag-checkered",
```

- [ ] **Step 10: Add builder UI schema (uses the `select` type from Task 2)**

```javascript
            function_terminate: [
                { key: "status", label: "Status", type: "select", options: ["Succeeded", "Failed", "Cancelled"] },
                { key: "message", label: "Message", type: "textarea" },
            ],
```

- [ ] **Step 11: Manually verify in the browser**

Build a small graph: Node A → Terminate (Failed) → Node B. Dry-run — confirm the log shows node A, then Terminate, then stops (Node B never appears in the log), and the overall run status shows Failed.

- [ ] **Step 12: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add Terminate function node"
```

---

### Task 7: Delay & Delay Until

**Files:**
- Modify: `00_System/workflow_engine.py` (add `import time`, `from datetime import datetime`; add `MAX_DELAY_SECONDS` constant; `_execute_function_node` — add two branches)
- Modify: `00_System/server.py` (registry + icons)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS`, using the `select` type)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (append)

**Interfaces:**
- Produces: `tool_id` `"function_delay"` (params `{"duration": number, "unit": "Seconds"|"Minutes"|"Hours"}`) and `"function_delay_until"` (params `{"timestamp": str}`, ISO8601). `MAX_DELAY_SECONDS = 300` module constant.

- [ ] **Step 1: Write the failing tests**

Append:

```python
import time as _time


def test_delay_dry_run_does_not_sleep():
    engine = WorkflowEngine(dry_run=True)
    start = _time.monotonic()
    output, jump = engine._execute_function_node("n", {"tool_id": "function_delay"}, {"duration": 3600, "unit": "Seconds"})
    assert _time.monotonic() - start < 1
    assert "[DRY RUN]" in output


def test_delay_over_cap_raises_without_sleeping():
    engine = WorkflowEngine(dry_run=False)
    start = _time.monotonic()
    try:
        engine._execute_function_node("n", {"tool_id": "function_delay"}, {"duration": 10, "unit": "Minutes"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass
    assert _time.monotonic() - start < 1


def test_delay_live_short_actually_sleeps():
    engine = WorkflowEngine(dry_run=False)
    start = _time.monotonic()
    output, jump = engine._execute_function_node("n", {"tool_id": "function_delay"}, {"duration": 0.2, "unit": "Seconds"})
    elapsed = _time.monotonic() - start
    assert elapsed >= 0.2, elapsed


def test_delay_until_past_timestamp_continues_immediately():
    engine = WorkflowEngine(dry_run=False)
    output, jump = engine._execute_function_node("n", {"tool_id": "function_delay_until"}, {"timestamp": "2000-01-01T00:00:00"})
    assert "already passed" in output


def test_delay_until_far_future_raises():
    engine = WorkflowEngine(dry_run=False)
    try:
        engine._execute_function_node("n", {"tool_id": "function_delay_until"}, {"timestamp": "2099-01-01T00:00:00"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `WorkflowRunError: Unknown function tool_id: function_delay` / `function_delay_until` on all five.

- [ ] **Step 3: Add imports and the cap constant**

In `00_System/workflow_engine.py`, add to the stdlib import block near the top:

```python
import time
from datetime import datetime
```

Add near `MAX_TOTAL_STEPS`:

```python
MAX_DELAY_SECONDS = 300  # 5 minutes -- workflows run synchronously inside one HTTP request
```

- [ ] **Step 4: Add the dispatch branches**

After Task 6's `function_terminate` branch:

```python
        if tool_id == "function_delay":
            unit_seconds = {"Seconds": 1, "Minutes": 60, "Hours": 3600}
            duration = float(params.get("duration") or 0)
            unit = params.get("unit", "Seconds")
            seconds = duration * unit_seconds.get(unit, 1)
            if seconds > MAX_DELAY_SECONDS:
                raise WorkflowRunError(f"Delay of {seconds:.0f}s exceeds the {MAX_DELAY_SECONDS}s cap (workflows run synchronously inside one request).")
            if self.dry_run:
                return f"[DRY RUN] Would delay {duration} {unit}", None
            time.sleep(max(seconds, 0))
            return f"Delayed {duration} {unit}", None

        if tool_id == "function_delay_until":
            raw = self._substitute_tokens(params.get("timestamp", "")).strip()
            if not raw:
                raise WorkflowRunError("Delay Until requires a timestamp.")
            try:
                target = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError as e:
                raise WorkflowRunError(f"Delay Until: invalid ISO8601 timestamp: {e}")
            now = datetime.now(target.tzinfo) if target.tzinfo else datetime.now()
            seconds = (target - now).total_seconds()
            if seconds <= 0:
                return f"Target timestamp {raw} already passed; continuing immediately.", None
            if seconds > MAX_DELAY_SECONDS:
                raise WorkflowRunError(f"Delay Until is {seconds:.0f}s away, exceeding the {MAX_DELAY_SECONDS}s cap.")
            if self.dry_run:
                return f"[DRY RUN] Would delay until {raw}", None
            time.sleep(seconds)
            return f"Delayed until {raw}", None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: all pass (24/24).

- [ ] **Step 6: Register both nodes**

`FUNCTIONS_REGISTRY`:

```python
    {
        "tool_id": "function_delay",
        "title": "Delay",
        "description": "Pauses execution for a duration (capped at 5 minutes -- workflows run synchronously inside one request).",
        "model": None,
    },
    {
        "tool_id": "function_delay_until",
        "title": "Delay Until",
        "description": "Pauses execution until an ISO8601 timestamp (capped at 5 minutes out). A past timestamp continues immediately.",
        "model": None,
    },
```

`TOOL_FA_ICON_MAP`:

```python
    "function_delay": "fa-clock",
    "function_delay_until": "fa-hourglass-half",
```

- [ ] **Step 7: Add builder UI schemas**

```javascript
            function_delay: [
                { key: "duration", label: "Duration", type: "number", placeholder: "5" },
                { key: "unit", label: "Unit", type: "select", options: ["Seconds", "Minutes", "Hours"] },
            ],
            function_delay_until: [
                { key: "timestamp", label: "Timestamp (ISO8601)", type: "text", mono: true, placeholder: "2026-08-01T14:00:00" },
            ],
```

- [ ] **Step 8: Manually verify in the browser**

Drag a Delay node, set Duration=2, Unit=Seconds, live-run (not dry) — confirm the run visibly pauses ~2s before completing. Drag a Delay Until node with a near-future timestamp, confirm similar behavior.

- [ ] **Step 9: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add Delay and Delay Until function nodes"
```

---

### Task 8: Filter Array & Select

**Files:**
- Modify: `00_System/workflow_engine.py` (`_execute_function_node` — add two branches, reusing `_eval_condition_expression` from `test_workflow_engine_conditions.py`'s sibling implementation already in this file, and `_parse_json_array`/`_dotted_get` from Task 1)
- Modify: `00_System/server.py` (registry + icons)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS`)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (append)

**Interfaces:**
- Produces: `tool_id` `"function_filter_array"` (params `{"condition": str}`) and `"function_select"` (params `{"columns": str}`, JSON text `{"outputKey": "dotted.path"}`).

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_filter_array_keeps_matching_items():
    engine = _single_input_engine("n", '[{"status": "active", "total": 50}, {"status": "closed", "total": 200}, {"status": "active", "total": 300}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_filter_array"}, {"condition": "status == 'active'"})
    assert json.loads(output) == [{"status": "active", "total": 50}, {"status": "active", "total": 300}]


def test_filter_array_numeric_condition():
    engine = _single_input_engine("n", '[{"total": 50}, {"total": 300}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_filter_array"}, {"condition": "total > 100"})
    assert json.loads(output) == [{"total": 300}]


def test_filter_array_invalid_input_raises():
    engine = _single_input_engine("n", "not json")
    try:
        engine._execute_function_node("n", {"tool_id": "function_filter_array"}, {"condition": "1 == 1"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_select_projects_and_renames_fields():
    engine = _single_input_engine("n", '[{"user": {"name": "Alice", "email": "a@x.com"}}, {"user": {"name": "Bob", "email": "b@x.com"}}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_select"}, {"columns": '{"name": "user.name", "email": "user.email"}'})
    assert json.loads(output) == [{"name": "Alice", "email": "a@x.com"}, {"name": "Bob", "email": "b@x.com"}]


def test_select_missing_path_yields_null():
    engine = _single_input_engine("n", '[{"user": {"name": "Alice"}}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_select"}, {"columns": '{"email": "user.email"}'})
    assert json.loads(output) == [{"email": None}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `WorkflowRunError: Unknown function tool_id: function_filter_array` / `function_select`.

- [ ] **Step 3: Add the dispatch branches**

After Task 7's `function_delay_until` branch:

```python
        if tool_id == "function_filter_array":
            arr = self._parse_json_array(node_id, "Filter Array")
            condition = self._substitute_tokens(params.get("condition", ""))
            kept = []
            for item in arr:
                namespace = dict(item) if isinstance(item, dict) else {}
                namespace["item"] = item
                if _eval_condition_expression(condition, namespace):
                    kept.append(item)
            return json.dumps(kept, indent=2), None

        if tool_id == "function_select":
            arr = self._parse_json_array(node_id, "Select")
            columns_text = self._substitute_tokens(params.get("columns", "")).strip()
            try:
                columns = json.loads(columns_text) if columns_text else {}
            except (TypeError, ValueError) as e:
                raise WorkflowRunError(f"Select: Columns must be a JSON object: {e}")
            projected = [
                {out_key: self._dotted_get(item, path) for out_key, path in columns.items()}
                for item in arr
            ]
            return json.dumps(projected, indent=2), None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: all pass (29/29).

- [ ] **Step 5: Register both nodes**

`FUNCTIONS_REGISTRY`:

```python
    {
        "tool_id": "function_filter_array",
        "title": "Filter Array",
        "description": "Keeps array items matching a condition (e.g. status == 'active' and total > 100), using the same safe expression evaluator as Conditions.",
        "model": None,
    },
    {
        "tool_id": "function_select",
        "title": "Select",
        "description": "Projects/renames fields per array item via a JSON map of {outputKey: \"dotted.path\"}.",
        "model": None,
    },
```

`TOOL_FA_ICON_MAP`:

```python
    "function_filter_array": "fa-filter",
    "function_select": "fa-table-columns",
```

- [ ] **Step 6: Add builder UI schemas**

```javascript
            function_filter_array: [
                { key: "condition", label: "Condition (e.g. status == 'active' and total > 100)", type: "text", mono: true },
            ],
            function_select: [
                { key: "columns", label: 'Columns (JSON: {"outputKey": "dotted.path"})', type: "textarea", mono: true, placeholder: '{"name": "user.name"}' },
            ],
```

- [ ] **Step 7: Manually verify in the browser**

Feed a Compose node a small JSON array literal, wire it into a Filter Array node with a condition, dry-run, confirm filtered output. Repeat for Select with a columns map.

- [ ] **Step 8: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add Filter Array and Select function nodes"
```

---

### Task 9: Join, Sort, Union

**Files:**
- Modify: `00_System/workflow_engine.py` (`_execute_function_node` — add three branches)
- Modify: `00_System/server.py` (registry + icons)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS`, using `select` type for Sort's direction)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (append)

**Interfaces:**
- Produces: `"function_join"` (params `{"field": str, "separator": str}`, output is a plain joined string), `"function_sort"` (params `{"field": str, "direction": "asc"|"desc"}`), `"function_union"` (params `{"key": str}`, uses `_direct_predecessor_texts`, requires ≥2 predecessors).

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_join_whole_items_with_separator():
    engine = _single_input_engine("n", '["a", "b", "c"]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_join"}, {"field": "", "separator": ", "})
    assert output == "a, b, c"


def test_join_field_path():
    engine = _single_input_engine("n", '[{"name": "Alice"}, {"name": "Bob"}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_join"}, {"field": "name", "separator": "; "})
    assert output == "Alice; Bob"


def test_sort_ascending_and_descending():
    engine = _single_input_engine("n", '[{"total": 30}, {"total": 10}, {"total": 20}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_sort"}, {"field": "total", "direction": "asc"})
    assert [i["total"] for i in json.loads(output)] == [10, 20, 30]

    output, jump = engine._execute_function_node("n", {"tool_id": "function_sort"}, {"field": "total", "direction": "desc"})
    assert [i["total"] for i in json.loads(output)] == [30, 20, 10]


def test_sort_mixed_types_raises():
    engine = _single_input_engine("n", '[1, "a"]')
    try:
        engine._execute_function_node("n", {"tool_id": "function_sort"}, {"field": "", "direction": "asc"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_union_merges_and_dedupes_two_predecessors():
    engine = WorkflowEngine(dry_run=True)
    engine.backward_edges = {"n": ["a", "b"]}
    engine.node_labels = {"a": "A", "b": "B", "n": "N"}
    engine.context = {"A": '[{"id": 1}, {"id": 2}]', "B": '[{"id": 2}, {"id": 3}]'}
    output, jump = engine._execute_function_node("n", {"tool_id": "function_union"}, {"key": "id"})
    assert json.loads(output) == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_union_requires_two_predecessors():
    engine = WorkflowEngine(dry_run=True)
    engine.backward_edges = {"n": ["a"]}
    engine.node_labels = {"a": "A", "n": "N"}
    engine.context = {"A": "[1, 2]"}
    try:
        engine._execute_function_node("n", {"tool_id": "function_union"}, {"key": ""})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `WorkflowRunError: Unknown function tool_id: function_join` / `function_sort` / `function_union`.

- [ ] **Step 3: Add the dispatch branches**

After Task 8's `function_select` branch:

```python
        if tool_id == "function_join":
            arr = self._parse_json_array(node_id, "Join")
            field = self._substitute_tokens(params.get("field", ""))
            separator = self._substitute_tokens(params.get("separator", ", "))
            values = [str(self._dotted_get(item, field) if field else item) for item in arr]
            return separator.join(values), None

        if tool_id == "function_sort":
            arr = self._parse_json_array(node_id, "Sort")
            field = self._substitute_tokens(params.get("field", ""))
            direction = params.get("direction", "asc")
            key_fn = (lambda item: self._dotted_get(item, field)) if field else (lambda item: item)
            try:
                sorted_arr = sorted(arr, key=key_fn, reverse=(direction == "desc"))
            except TypeError as e:
                raise WorkflowRunError(f"Sort: items aren't consistently comparable: {e}")
            return json.dumps(sorted_arr, indent=2), None

        if tool_id == "function_union":
            pred_texts = self._direct_predecessor_texts(node_id)
            if len(pred_texts) < 2:
                raise WorkflowRunError("Union requires at least two connected inputs.")
            key = self._substitute_tokens(params.get("key", ""))
            merged, seen = [], set()
            for i, text in enumerate(pred_texts):
                try:
                    parsed = json.loads(text)
                except (TypeError, ValueError) as e:
                    raise WorkflowRunError(f"Union: predecessor {i + 1} is not valid JSON: {e}")
                if not isinstance(parsed, list):
                    raise WorkflowRunError(f"Union: predecessor {i + 1} is a {type(parsed).__name__}, not a JSON array.")
                for item in parsed:
                    dedup_key = json.dumps(self._dotted_get(item, key) if key else item, sort_keys=True)
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        merged.append(item)
            return json.dumps(merged, indent=2), None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: all pass (35/35).

- [ ] **Step 5: Register all three nodes**

`FUNCTIONS_REGISTRY`:

```python
    {
        "tool_id": "function_join",
        "title": "Join",
        "description": "Joins array items (or an optional dotted-path field of each item) into a single delimited string.",
        "model": None,
    },
    {
        "tool_id": "function_sort",
        "title": "Sort",
        "description": "Sorts an array by an optional dotted-path field, ascending or descending.",
        "model": None,
    },
    {
        "tool_id": "function_union",
        "title": "Union",
        "description": "Merges two or more connected arrays, deduplicated by whole-item equality or an optional dotted-path key.",
        "model": None,
    },
```

`TOOL_FA_ICON_MAP`:

```python
    "function_join": "fa-link",
    "function_sort": "fa-arrow-down-a-z",
    "function_union": "fa-object-ungroup",
```

- [ ] **Step 6: Add builder UI schemas**

```javascript
            function_join: [
                { key: "field", label: "Field (optional dotted path; blank = whole item)", type: "text", mono: true },
                { key: "separator", label: "Separator", type: "text", mono: true, placeholder: ", " },
            ],
            function_sort: [
                { key: "field", label: "Field (optional dotted path; blank = whole item)", type: "text", mono: true },
                { key: "direction", label: "Direction", type: "select", options: ["asc", "desc"] },
            ],
            function_union: [
                { key: "key", label: "Dedup Key (optional dotted path; blank = whole item)", type: "text", mono: true },
            ],
```

- [ ] **Step 7: Manually verify in the browser**

Wire two Compose nodes (each with a JSON array literal) into one Union node — confirm both inputs show as connected chips and the dry-run output is the merged/deduped array. Verify Join and Sort similarly with a single upstream array.

- [ ] **Step 8: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add Join, Sort, and Union function nodes"
```

---

### Task 10: Chunk, Length, First, Last, Take, Skip

**Files:**
- Modify: `00_System/workflow_engine.py` (`_execute_function_node` — add six branches)
- Modify: `00_System/server.py` (registry + icons)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS`)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (append)

**Interfaces:**
- Produces: `"function_chunk"` (params `{"size": number}`), `"function_length"` (no params, plain-text integer output), `"function_first"`/`"function_last"` (no params, `_array_item_to_text` output, raise on empty array), `"function_take"`/`"function_skip"` (params `{"count": number}`).

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_chunk_splits_into_groups():
    engine = _single_input_engine("n", "[1, 2, 3, 4, 5]")
    output, jump = engine._execute_function_node("n", {"tool_id": "function_chunk"}, {"size": 2})
    assert json.loads(output) == [[1, 2], [3, 4], [5]]


def test_chunk_invalid_size_raises():
    engine = _single_input_engine("n", "[1, 2, 3]")
    try:
        engine._execute_function_node("n", {"tool_id": "function_chunk"}, {"size": 0})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_length_returns_plain_count():
    engine = _single_input_engine("n", "[1, 2, 3]")
    output, jump = engine._execute_function_node("n", {"tool_id": "function_length"}, {})
    assert output == "3"


def test_first_and_last_scalar_unquoted():
    engine = _single_input_engine("n", '["Alice", "Bob"]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_first"}, {})
    assert output == "Alice"
    output, jump = engine._execute_function_node("n", {"tool_id": "function_last"}, {})
    assert output == "Bob"


def test_first_and_last_object_json():
    engine = _single_input_engine("n", '[{"a": 1}, {"a": 2}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_first"}, {})
    assert json.loads(output) == {"a": 1}


def test_first_empty_array_raises():
    engine = _single_input_engine("n", "[]")
    try:
        engine._execute_function_node("n", {"tool_id": "function_first"}, {})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_take_and_skip():
    engine = _single_input_engine("n", "[1, 2, 3, 4, 5]")
    output, jump = engine._execute_function_node("n", {"tool_id": "function_take"}, {"count": 2})
    assert json.loads(output) == [1, 2]
    output, jump = engine._execute_function_node("n", {"tool_id": "function_skip"}, {"count": 2})
    assert json.loads(output) == [3, 4, 5]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `WorkflowRunError: Unknown function tool_id: function_chunk` etc. on all seven.

- [ ] **Step 3: Add the dispatch branches**

After Task 9's `function_union` branch:

```python
        if tool_id == "function_chunk":
            arr = self._parse_json_array(node_id, "Chunk")
            size = int(params.get("size") or 0)
            if size <= 0:
                raise WorkflowRunError("Chunk size must be a positive integer.")
            return json.dumps([arr[i:i + size] for i in range(0, len(arr), size)], indent=2), None

        if tool_id == "function_length":
            arr = self._parse_json_array(node_id, "Length")
            return str(len(arr)), None

        if tool_id == "function_first":
            arr = self._parse_json_array(node_id, "First")
            if not arr:
                raise WorkflowRunError("First: array is empty.")
            return self._array_item_to_text(arr[0]), None

        if tool_id == "function_last":
            arr = self._parse_json_array(node_id, "Last")
            if not arr:
                raise WorkflowRunError("Last: array is empty.")
            return self._array_item_to_text(arr[-1]), None

        if tool_id == "function_take":
            arr = self._parse_json_array(node_id, "Take")
            count = max(int(params.get("count") or 0), 0)
            return json.dumps(arr[:count], indent=2), None

        if tool_id == "function_skip":
            arr = self._parse_json_array(node_id, "Skip")
            count = max(int(params.get("count") or 0), 0)
            return json.dumps(arr[count:], indent=2), None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: all pass (42/42).

- [ ] **Step 5: Register all six nodes**

`FUNCTIONS_REGISTRY`:

```python
    {"tool_id": "function_chunk", "title": "Chunk", "description": "Splits an array into fixed-size sub-arrays.", "model": None},
    {"tool_id": "function_length", "title": "Length", "description": "Returns the number of items in an array.", "model": None},
    {"tool_id": "function_first", "title": "First", "description": "Returns the first item of an array; fails if the array is empty.", "model": None},
    {"tool_id": "function_last", "title": "Last", "description": "Returns the last item of an array; fails if the array is empty.", "model": None},
    {"tool_id": "function_take", "title": "Take", "description": "Returns the first N items of an array.", "model": None},
    {"tool_id": "function_skip", "title": "Skip", "description": "Returns an array with the first N items removed.", "model": None},
```

`TOOL_FA_ICON_MAP`:

```python
    "function_chunk": "fa-layer-group",
    "function_length": "fa-ruler-horizontal",
    "function_first": "fa-angles-left",
    "function_last": "fa-angles-right",
    "function_take": "fa-forward",
    "function_skip": "fa-backward",
```

- [ ] **Step 6: Add builder UI schemas**

```javascript
            function_chunk: [{ key: "size", label: "Chunk Size", type: "number", placeholder: "10" }],
            function_length: [],
            function_first: [],
            function_last: [],
            function_take: [{ key: "count", label: "Count", type: "number", placeholder: "5" }],
            function_skip: [{ key: "count", label: "Count", type: "number", placeholder: "5" }],
```

- [ ] **Step 7: Manually verify in the browser**

Feed each of the six nodes a small JSON array from a Compose node and dry-run each, confirming the palette icons and output match expectations.

- [ ] **Step 8: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add Chunk, Length, First, Last, Take, Skip function nodes"
```

---

### Task 11: Create CSV Table & Create HTML Table

**Files:**
- Modify: `00_System/workflow_engine.py` (add `import csv, io, html`; `_execute_function_node` — add two branches)
- Modify: `00_System/server.py` (registry + icon)
- Modify: `00_System/templates/workflow-builder.html` (`FUNCTION_FIELD_SCHEMAS`)
- Test: `00_System/test_workflow_engine_flow_and_data_ops.py` (append)

**Interfaces:**
- Produces: `"function_create_csv_table"` and `"function_create_html_table"`, both params `{"columns": str}` (optional, newline-separated; blank = keys of the first item in first-seen order, or `[]` if the array is empty). Every item must be a `dict` or the node raises `WorkflowRunError` naming the first offending index.

- [ ] **Step 1: Write the failing tests**

Append:

```python
def test_create_csv_table_auto_columns():
    engine = _single_input_engine("n", '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_create_csv_table"}, {"columns": ""})
    assert "name,age" in output.replace("\r\n", "\n").splitlines()[0]
    assert "Alice,30" in output


def test_create_csv_table_explicit_columns():
    engine = _single_input_engine("n", '[{"name": "Alice", "age": 30, "extra": "x"}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_create_csv_table"}, {"columns": "name\nage"})
    lines = output.replace("\r\n", "\n").splitlines()
    assert lines[0] == "name,age"
    assert lines[1] == "Alice,30"


def test_create_csv_table_non_dict_item_raises():
    engine = _single_input_engine("n", "[1, 2]")
    try:
        engine._execute_function_node("n", {"tool_id": "function_create_csv_table"}, {"columns": ""})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_create_csv_table_empty_array_returns_empty_string():
    engine = _single_input_engine("n", "[]")
    output, jump = engine._execute_function_node("n", {"tool_id": "function_create_csv_table"}, {"columns": ""})
    assert output == ""


def test_create_html_table_basic_structure_and_escaping():
    engine = _single_input_engine("n", '[{"name": "<b>Alice</b>"}]')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_create_html_table"}, {"columns": ""})
    assert "<table>" in output and "</table>" in output
    assert "&lt;b&gt;Alice&lt;/b&gt;" in output
    assert "<b>Alice</b>" not in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: `WorkflowRunError: Unknown function tool_id: function_create_csv_table` / `function_create_html_table`.

- [ ] **Step 3: Add imports**

In `00_System/workflow_engine.py`'s stdlib import block:

```python
import csv
import io
import html
```

- [ ] **Step 4: Add a shared column-resolution helper and the two dispatch branches**

Add after Task 10's `function_skip` branch:

```python
        if tool_id in ("function_create_csv_table", "function_create_html_table"):
            friendly_name = "Create CSV Table" if tool_id == "function_create_csv_table" else "Create HTML Table"
            arr = self._parse_json_array(node_id, friendly_name)
            for i, item in enumerate(arr):
                if not isinstance(item, dict):
                    raise WorkflowRunError(f"{friendly_name}: item {i} is a {type(item).__name__}, not an object.")
            explicit_columns = [c.strip() for c in self._substitute_tokens(params.get("columns", "")).splitlines() if c.strip()]
            columns = explicit_columns or (list(arr[0].keys()) if arr else [])

            if not arr:
                return "", None

            if tool_id == "function_create_csv_table":
                buffer = io.StringIO()
                writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", restval="")
                writer.writeheader()
                writer.writerows(arr)
                return buffer.getvalue(), None

            header_html = "".join(f"<th>{html.escape(str(c))}</th>" for c in columns)
            rows_html = "".join(
                "<tr>" + "".join(f"<td>{html.escape(str(item.get(c, '')))}</td>" for c in columns) + "</tr>"
                for item in arr
            )
            return f"<table><tr>{header_html}</tr>{rows_html}</table>", None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_flow_and_data_ops.py`
Expected: all pass (47/47).

- [ ] **Step 6: Register both nodes**

`FUNCTIONS_REGISTRY`:

```python
    {
        "tool_id": "function_create_csv_table",
        "title": "Create CSV Table",
        "description": "Converts an array of objects into CSV text (optional explicit column order; blank = auto-detect from the first row).",
        "model": None,
    },
    {
        "tool_id": "function_create_html_table",
        "title": "Create HTML Table",
        "description": "Converts an array of objects into an HTML <table> (optional explicit column order; blank = auto-detect from the first row).",
        "model": None,
    },
```

`TOOL_FA_ICON_MAP`:

```python
    "function_create_csv_table": "fa-file-csv",
    "function_create_html_table": "fa-table",
```

- [ ] **Step 7: Add builder UI schemas**

```javascript
            function_create_csv_table: [
                { key: "columns", label: "Columns (optional, one per line; blank = auto-detect from first row)", type: "textarea", mono: true },
            ],
            function_create_html_table: [
                { key: "columns", label: "Columns (optional, one per line; blank = auto-detect from first row)", type: "textarea", mono: true },
            ],
```

- [ ] **Step 8: Manually verify in the browser**

Feed both nodes a small array of objects from a Compose node, dry-run, confirm CSV text and HTML table markup respectively.

- [ ] **Step 9: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/server.py 00_System/templates/workflow-builder.html 00_System/test_workflow_engine_flow_and_data_ops.py
git commit -m "Add Create CSV Table and Create HTML Table function nodes"
```

---

### Task 12: Frontend run-log display for Terminate/Response + icon verification pass

**Files:**
- Modify: `00_System/templates/workflow-builder.html` (`wfbRun`'s result-handling code, ~lines 1493-1516)
- Modify: `00_System/server.py` (`TOOL_FA_ICON_MAP` — verify glyphs exist)

**Interfaces:**
- Produces: the run log visibly distinguishes a "terminated" step from "success"/"failed", and shows a summary line for `data.terminated`/`data.responses` when present.

- [ ] **Step 1: Update the per-step color logic**

In `00_System/templates/workflow-builder.html`, replace (~line 1493-1495):

```javascript
                (data.steps || []).forEach(step => {
                    const color = step.status === "success" ? "text-body" : "text-danger-400";
                    wfbLog(`[${step.kind || "?"}] ${step.title || step.node_id}: ${step.status}${step.output ? " -- " + step.output : ""}`, color);
```

with:

```javascript
                (data.steps || []).forEach(step => {
                    const color = step.status === "success" ? "text-body" : step.status === "terminated" ? "text-info-400" : "text-danger-400";
                    wfbLog(`[${step.kind || "?"}] ${step.title || step.node_id}: ${step.status}${step.output ? " -- " + step.output : ""}`, color);
```

- [ ] **Step 2: Show responses and terminated status in the summary**

Replace (~line 1510-1516):

```javascript
                if (data.success) {
                    wfbLog("Workflow run complete.", "text-success-400");
                    wfbSetRunStatus("Complete", "text-success-400");
                } else {
                    wfbLog("Workflow run finished with failures.", "text-danger-400");
                    wfbSetRunStatus("Failed", "text-danger-400");
                }
```

with:

```javascript
                (data.responses || []).forEach(r => {
                    wfbLog(`Response [${r.label}]: ${r.output}`, "text-info-400");
                });

                if (data.terminated) {
                    const tColor = data.terminated.status === "Succeeded" ? "text-success-400" : "text-danger-400";
                    wfbLog(`Workflow terminated: ${data.terminated.status} -- ${data.terminated.message}`, tColor);
                    wfbSetRunStatus(`Terminated (${data.terminated.status})`, tColor);
                } else if (data.success) {
                    wfbLog("Workflow run complete.", "text-success-400");
                    wfbSetRunStatus("Complete", "text-success-400");
                } else {
                    wfbLog("Workflow run finished with failures.", "text-danger-400");
                    wfbSetRunStatus("Failed", "text-danger-400");
                }
```

- [ ] **Step 3: Verify every new icon name exists in the vendored Font Awesome CSS**

Run (from the repo root):

```bash
grep -o '"fa-[a-z0-9-]*"' 00_System/templates/static/vendor/fontawesome/*.min.css | sort -u > /tmp/fa_available.txt
```

Then check each icon added across Tasks 3-11 (`fa-cube`, `fa-file-code`, `fa-globe`, `fa-reply`, `fa-flag-checkered`, `fa-clock`, `fa-hourglass-half`, `fa-filter`, `fa-table-columns`, `fa-link`, `fa-arrow-down-a-z`, `fa-object-ungroup`, `fa-layer-group`, `fa-ruler-horizontal`, `fa-angles-left`, `fa-angles-right`, `fa-forward`, `fa-backward`, `fa-file-csv`, `fa-table`) is actually present. For any that aren't, pick a real substitute from the same file and update `TOOL_FA_ICON_MAP` in `00_System/server.py` accordingly (this is the same "checked against the actual installed CSS" discipline the file's own header comment requires — don't guess a second time).

- [ ] **Step 4: Full manual regression pass**

Run: `python 00_System/server.py`, open the builder. Build one end-to-end workflow exercising a representative sample: Compose → HTTP (against a public test endpoint) → Parse JSON → Filter Array → Select → Create HTML Table → Response, with a Terminate(Failed) branch reachable via a Logic Gate for a second manual test. Confirm: palette shows all 20 new nodes with resolved icons (no broken/default icon unless intentionally falling back), dry-run completes cleanly end to end, a live run against the HTTP node succeeds, and the Terminate branch stops the run and shows the terminated summary line in the log.

- [ ] **Step 5: Run the full test suite one more time**

```bash
python 00_System/test_workflow_engine_flow_and_data_ops.py
python 00_System/test_workflow_engine_conditions.py
python 00_System/test_workflow_engine_tokens.py
python 00_System/test_model_classifications.py
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add 00_System/templates/workflow-builder.html 00_System/server.py
git commit -m "Surface Terminate/Response in run log; verify Font Awesome icon names"
```

---

## Self-Review Notes

- **Spec coverage:** Part 1 (Compose, Parse JSON) → Task 3. Part 2 (HTTP, Response) → Tasks 4-5. Part 3 (Terminate, Delay, Delay Until) → Tasks 6-7. Part 4 (all 13 array-op nodes) → Tasks 8-10-11 (split by shared-mechanism grouping: expression/dotted-path nodes in 8, join/sort/multi-predecessor in 9, pure slice/measure ops in 10, table-serialization ops in 11). Part 5 (`select` field type) → Task 2, consumed by Tasks 4/6/7/9. Part 6 (registries/icons) → done per-task throughout, with a dedicated verification pass in Task 12. Shared mechanics (`_parse_json_array`/`_dotted_get`/`_array_item_to_text`) → Task 1. Testing section's per-node cases are covered by each task's own test additions to the single accumulating test file, matching the spec's "one new file" testing plan.
- **Placeholder scan:** no TBD/TODO; every step has literal code, literal commands, or literal manual-verification instructions with concrete expected outcomes.
- **Type consistency:** every dispatch branch's `params` keys match exactly what its corresponding `FUNCTION_FIELD_SCHEMAS` entry produces (verified key-by-key against each task's schema block). `run()`'s return dict shape (`success`, `steps`, `responses`, `terminated`) is introduced incrementally (Task 5 adds `responses`, Task 6 adds `terminated`) and each introducing task updates the *same* return statement rather than two independent ones, avoiding a shape conflict. `WorkflowTerminate` (Task 6) is deliberately not a `WorkflowRunError` subclass, consistent with the spec's explicit rationale for needing its own `except` clause.
- **Task 1's forward reference:** Task 1's test file imports `WorkflowTerminate` before Task 6 defines it, matching this repo's established convention of one accumulating test file per feature area (`test_workflow_engine_conditions.py` also grew across that plan's Tasks 2-4). Step 2 of Task 1 calls this out explicitly with a workaround so the task is independently verifiable without jumping ahead.
