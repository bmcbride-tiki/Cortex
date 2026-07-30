# Workflow Builder Named I/O Tokens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a Workflow Builder node's output be given a custom, human-readable label (e.g. `CG-JSON`) that downstream nodes reference explicitly as `{{label}}`, resolved only across direct connections, with a builder UI that shows and helps insert the labels actually available to whichever node is selected.

**Architecture:** `workflow_engine.py` gains a `label` field on parsed node data (stored alongside the existing `title`), keys its run-time `context` dict by label instead of node ID, and scopes `{{label}}` substitution to each node's direct predecessors (`backward_edges`, already computed but previously unused for this) — an out-of-scope or nonexistent label now raises `MissingInputError` instead of silently resolving to `""`. `workflow-builder.html` gains a persistent "Output Label" + "Input(s)" panel above each node's existing config UI, auto-generating and auto-suffixing labels client-side, cascading renames live across the current module, and painting a red outline + tooltip on any node whose run step failed.

**Tech Stack:** Python 3 (stdlib `re`, `json`), vanilla JS (no new dependencies), Drawflow (already in use).

## Global Constraints

- No back-compat shim for the old `{{node_id}}` style — no saved workflows exist yet to migrate (confirmed during design).
- Labels use the existing `TOKEN_PATTERN` regex `[a-zA-Z0-9_\-]+` (`workflow_engine.py:96`) — no new brace syntax.
- Token substitution is scoped to direct connections only (`backward_edges`) — never resolves a label belonging to a node without a direct edge into the one being evaluated.
- Unresolved or out-of-scope tokens raise an error (`MissingInputError`, a `WorkflowRunError` subclass) — never silently resolve to `""`.
- Duplicate labels auto-suffix (`_2`, `_3`, …) client-side — creation/rename never blocks on a naming collision.
- No new Python or JS dependencies.
- Match existing code conventions: comments explain *why* not what (see existing style throughout both files), existing Tailwind utility classes, existing `escapeHtml`/`wfbLog`/`editor.updateNodeDataFromId` helpers.
- Test file convention in this repo is a co-located `test_<module>.py` run directly with `python <file>.py` (see `00_System/test_model_classifications.py`) — there is no `tests/` directory.

---

### Task 1: Engine — label-keyed, connection-scoped token substitution

**Files:**
- Modify: `00_System/workflow_engine.py`
- Create: `00_System/test_workflow_engine_tokens.py`

**Interfaces:**
- Produces: `WorkflowEngine.node_labels: Dict[str, str]` (node ID → label, built fresh each `run()`), `WorkflowEngine._current_scope: Dict[str, str]` (rebuilt per node during `run()`), `MissingInputError` exception class, `WorkflowEngine._build_scope(node_id: str) -> Dict[str, str]`.
- Consumes: nothing from other tasks — this is the foundation Task 2 (engine node-type updates) and Tasks 3-5 (UI) build on.

- [ ] **Step 1: Write the failing tests**

Create `00_System/test_workflow_engine_tokens.py`:

```python
# 00_System/test_workflow_engine_tokens.py
"""Assert-based smoke tests for WorkflowEngine's named-label token substitution.
Run directly: python test_workflow_engine_tokens.py
"""
import sys
sys.dont_write_bytecode = True

from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from workflow_engine import WorkflowEngine


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


def test_label_resolves_when_directly_connected():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Source", "function_gemini_ask", {"instructions": "AAA"}, ["2"]),
        ("2", "Combine", "function_gemini_ask", {"instructions": "Use: {{Source}}"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    combine_step = next(s for s in result["steps"] if s["node_id"] == "2")
    assert "AAA" in combine_step["output"], combine_step


def test_label_on_non_predecessor_raises_missing_input():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Alpha", "function_gemini_ask", {"instructions": "AAA"}, []),
        ("2", "Beta", "function_gemini_ask", {"instructions": "{{Alpha}}"}, []),
    ])
    # "Alpha" exists in the graph but has no edge into "Beta" -- referencing it
    # must fail, not silently resolve, per the connection-scoped design.
    result = engine.run(graph)
    assert not result["success"], result
    beta_step = next(s for s in result["steps"] if s["node_id"] == "2")
    assert beta_step["status"] == "failed", beta_step
    assert "Alpha" in beta_step["output"], beta_step


def test_nonexistent_label_raises_missing_input():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Solo", "function_gemini_ask", {"instructions": "{{DoesNotExist}}"}, []),
    ])
    result = engine.run(graph)
    assert not result["success"], result
    step = next(s for s in result["steps"] if s["node_id"] == "1")
    assert step["status"] == "failed", step
    assert "DoesNotExist" in step["output"], step


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

Run: `python 00_System/test_workflow_engine_tokens.py`
Expected: `FAIL test_label_resolves_when_directly_connected: ...` and similar for the others — today's `_substitute_tokens` resolves any label in the whole-run `self.context` regardless of wiring (so test 2 wouldn't fail the way it should) and returns `""` for unknown labels instead of raising (so test 3's step would show `status: "success"` with an empty-string-substituted output, not `"failed"`).

- [ ] **Step 3: Add `MissingInputError` and thread `label` through graph parsing**

In `00_System/workflow_engine.py`, add the new exception class right after `WorkflowRunError` (after line 106):

```python
class MissingInputError(WorkflowRunError):
    # Raised when a {{label}} reference can't be resolved -- either the
    # label doesn't exist anywhere in the graph, or it exists but isn't on
    # a node directly wired into the one currently executing. Unlike a
    # generic WorkflowRunError, callers can catch this one specifically if
    # they ever need to distinguish "bad wiring" from other failure modes.
    pass
```

In `_parse_graph` (lines 168-175), add one line so `label` is read the same way `title` already is:

```python
                nodes[node_id] = {
                    "kind": data.get("kind"),
                    "tool_id": data.get("tool_id"),
                    "category": data.get("category"),
                    "title": data.get("title") or raw.get("name") or node_id,
                    "label": data.get("label") or node_id,
                    "params": data.get("params") or {},
                    "module_name": data.get("module_name"),
                }
```

- [ ] **Step 4: Add `node_labels` and `_current_scope` state**

In `WorkflowEngine.__init__` (lines 121-137), add two lines after `self.context: Dict[str, str] = {}` and update that line's comment:

```python
        # Every node's captured text output, keyed by that node's LABEL (not
        # its raw ID) -- this is the shared "memory" that lets later nodes
        # reference earlier nodes' results via {{label}} tokens.
        self.context: Dict[str, str] = {}
        # node_id -> label, rebuilt fresh at the start of every run() call.
        self.node_labels: Dict[str, str] = {}
        # The subset of self.context visible to whichever node is currently
        # executing -- only its direct predecessors' labels, rebuilt by
        # _build_scope() right before that node runs. This is what makes
        # token resolution connection-scoped instead of graph-wide.
        self._current_scope: Dict[str, str] = {}
```

- [ ] **Step 5: Add `_build_scope` and rewrite `_substitute_tokens`**

Add a new method right after `_find_entry_nodes` (after line 254, before the "Token substitution" section header at line 256):

```python
    def _build_scope(self, node_id: str) -> Dict[str, str]:
        # Only labels belonging to nodes with a DIRECT edge into node_id are
        # visible to it -- this is what makes {{label}} a connection, not a
        # graph-wide lookup. A predecessor whose label isn't in self.context
        # yet (shouldn't happen given run()'s topological-ish walk order,
        # but defensively) is just left out of scope rather than crashing.
        scope: Dict[str, str] = {}
        for pred_id in self.backward_edges.get(node_id, []):
            label = self.node_labels.get(pred_id)
            if label and label in self.context:
                scope[label] = self.context[label]
        return scope
```

Replace `_substitute_tokens` (lines 258-266):

```python
    def _substitute_tokens(self, text: str) -> str:
        # Finds every {{label}} placeholder in a piece of text and replaces
        # it with that label's captured output -- but only if the label is
        # in self._current_scope (set by _execute_node right before this
        # node's handler runs, see below). A label that doesn't exist, or
        # exists but isn't directly connected, is a hard failure rather
        # than a silent blank.
        if not text:
            return text

        def replace(m: "re.Match[str]") -> str:
            label = m.group(1)
            if label not in self._current_scope:
                token_display = "{{" + label + "}}"
                raise MissingInputError(
                    f'Missing input value: {token_display} -- "{label}" isn\'t directly connected to this node.'
                )
            return self._current_scope[label]

        return TOKEN_PATTERN.sub(replace, text)
```

- [ ] **Step 6: Build `node_labels` and set `_current_scope` per node in `run()`**

In `run()`, right after `self.backward_edges = backward_edges` (line 580), add:

```python
        self.node_labels = {nid: (n.get("label") or nid) for nid, n in nodes.items()}
```

In `_execute_node` (line 463), add the scope-build as the first line of the method body, right after the docstring/comment block and before `kind = node.get("kind")` (line 476):

```python
        self._current_scope = self._build_scope(node_id)
        kind = node.get("kind")
```

- [ ] **Step 7: Key `self.context` by label instead of node ID**

In `run()`, replace the context assignment (line 608):

```python
                output_text, jump_to = self._execute_node(node_id, node)
                label = self.node_labels.get(node_id, node_id)
                self.context[label] = output_text
```

- [ ] **Step 8: Keep `_gather_upstream_text` correct under the new label keying**

`_gather_upstream_text` (lines 268-274) isn't rewritten until Task 2, but Step 7 just changed what `self.context` is keyed by — leaving this method's node-ID-based lookup in place would make it silently return `""` for every node from this commit until Task 2 lands, even though nothing in Step 1's tests exercises it. Fix the keying now (Task 2 replaces this whole method later with `_direct_predecessor_texts` — this is a minimal correctness patch, not a preview of that refactor):

```python
    def _gather_upstream_text(self, node_id: str) -> str:
        # Collects the output of every node that feeds directly into this
        # one and joins them together (separated by a blank line) -- this
        # is the default "input" most node types receive automatically,
        # without the user needing to manually reference {{...}} tokens.
        parts = [
            self.context[self.node_labels[p]]
            for p in self.backward_edges.get(node_id, [])
            if self.node_labels.get(p) in self.context
        ]
        return "\n\n".join(parts)
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_tokens.py`
Expected: `3/3 passed`

- [ ] **Step 10: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine_tokens.py
git commit -m "$(cat <<'EOF'
Scope workflow token substitution to direct connections, key by label

{{label}} now resolves only across a node's direct predecessors (never
graph-wide) and raises MissingInputError instead of silently substituting
an empty string when a reference is unresolved or out of scope.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Engine — require explicit binding except where a node has no alternative field

**Note:** every line number cited below is from the file as it stood before Task 1's edits. Task 1 shifted everything after its first change by a small, consistent offset. Locate each target by method name and the surrounding code shown in this task's "before" snippets, not by trusting the line number literally.

**Files:**
- Modify: `00_System/workflow_engine.py`
- Modify: `00_System/test_workflow_engine_tokens.py`

**Interfaces:**
- Consumes: `MissingInputError`, `_substitute_tokens`, `node_labels`, `backward_edges` from Task 1.
- Produces: `WorkflowEngine._direct_predecessor_texts(node_id: str) -> List[str]`, `WorkflowEngine._extract_json_field_or_raw(value: str, key: str) -> str` (renamed/rewritten from `_extract_json_field`).

- [ ] **Step 1: Write the failing tests**

Append to `00_System/test_workflow_engine_tokens.py`, right before the `if __name__ == "__main__":` block:

```python
def test_ai_prompt_node_has_no_implicit_upstream_text():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Upstream", "function_gemini_ask", {"instructions": "IGNORED"}, ["2"]),
        ("2", "Prompted", "function_gemini_ask", {"instructions": "ONLY THIS"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    step = next(s for s in result["steps"] if s["node_id"] == "2")
    assert step["output"] == "[DRY RUN] Simulated Gemini response for prompt:\nONLY THIS", step


def test_concatenate_joins_direct_predecessors_with_separator():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "A", "function_gemini_ask", {"instructions": "AAA"}, ["3"]),
        ("2", "B", "function_gemini_ask", {"instructions": "BBB"}, ["3"]),
        ("3", "Combine", "function_concatenate", {"separator": "|"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    step = next(s for s in result["steps"] if s["node_id"] == "3")
    parts = step["output"].split("|")
    assert len(parts) == 2 and "AAA" in parts[0] and "BBB" in parts[1], step


def test_notebook_id_extracted_from_json_shaped_value():
    engine = WorkflowEngine(dry_run=True)
    result = engine._extract_json_field_or_raw('{"notebook_id": "nb-123", "title": "X"}', "notebook_id")
    assert result == "nb-123", result


def test_notebook_id_passthrough_when_not_json():
    engine = WorkflowEngine(dry_run=True)
    result = engine._extract_json_field_or_raw("nb-123", "notebook_id")
    assert result == "nb-123", result


def test_upload_sources_requires_notebook_id():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Upload", "function_notebooklm_upload_sources", {"notebook_id": "", "file_paths": "a.pdf"}, []),
    ])
    result = engine.run(graph)
    step = next(s for s in result["steps"] if s["node_id"] == "1")
    assert step["status"] == "failed", step
    assert "notebook_id" in step["output"], step
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python 00_System/test_workflow_engine_tokens.py`
Expected: `test_ai_prompt_node_has_no_implicit_upstream_text` FAILs (today's output also includes `"\n\nInput:\n"` boilerplate plus whatever's upstream); `test_notebook_id_extracted_from_json_shaped_value` and `test_notebook_id_passthrough_when_not_json` FAIL with `AttributeError: 'WorkflowEngine' object has no attribute '_extract_json_field_or_raw'`; the Concatenate and upload-sources tests should already PASS (regression checks — confirm they do, since Steps 3-5 below must not change their behavior).

- [ ] **Step 3: Add `_direct_predecessor_texts`, simplify `_gather_upstream_text`, update Concatenate**

Replace `_gather_upstream_text` (as it stands after Task 1's Step 8 keying fix — find it by name, not line number, since Task 1 shifted its line range) with two methods:

```python
    def _direct_predecessor_texts(self, node_id: str) -> List[str]:
        # Every direct predecessor's captured output, in edge order -- the
        # raw material both _gather_upstream_text (whole-text join) and the
        # Concatenate function (custom-separator join) build on.
        return [
            self.context[self.node_labels[p]]
            for p in self.backward_edges.get(node_id, [])
            if self.node_labels.get(p) in self.context
        ]

    def _gather_upstream_text(self, node_id: str) -> str:
        # Used only by node types whose entire defined behavior IS "operate
        # on whatever's directly connected" -- Skill nodes, Logic Gate, and
        # Review Gate -- which have no settings field to explicitly bind a
        # {{label}} into instead.
        return "\n\n".join(self._direct_predecessor_texts(node_id))
```

In `_execute_function_node`, replace the Concatenate branch (lines 509-512):

```python
        if tool_id == "function_concatenate":
            separator = self._substitute_tokens(params.get("separator", "\n\n"))
            return separator.join(self._direct_predecessor_texts(node_id)), None
```

- [ ] **Step 4: Remove universal `upstream_text`, compute it only where still needed**

In `_execute_node` (around line 478), delete the universal computation:

```python
        kind = node.get("kind")
        params = node.get("params") or {}
```

(i.e. delete the `upstream_text = self._gather_upstream_text(node_id)` line that used to follow `params = node.get("params") or {}`.)

In the same method, update the `skill` branch (lines 489-491) to compute it locally, since Skill nodes are one of the four exceptions:

```python
        if kind == "skill":
            upstream_text = self._gather_upstream_text(node_id)
            prompt = f"{node['title']}: {node.get('description', '')}\n\nInput:\n{upstream_text}"
            return self._ask_copilot(prompt), None
```

Update the function-dispatch line (494) to drop the now-removed argument:

```python
        if kind == "function":
            return self._execute_function_node(node_id, node, params)
```

- [ ] **Step 5: Update `_execute_function_node`'s signature and its two other exceptions**

Change the method signature (line 498):

```python
    def _execute_function_node(self, node_id: str, node: Dict[str, Any], params: Dict[str, Any]) -> Tuple[str, Optional[str]]:
```

Update the two call sites inside it that used to forward `upstream_text` (lines 505-506, 514-515):

```python
        if tool_id == "builtin_review_gate":
            return self._run_review_gate(node_id, params)
```

```python
        if tool_id == "function_logic_gate":
            return self._run_logic_gate(node_id, params)
```

Update `_run_review_gate`'s signature (line 431) and add its own local computation:

```python
    def _run_review_gate(self, node_id: str, params: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        upstream_text = self._gather_upstream_text(node_id)
        criteria = params.get("criteria", "")
```

(i.e. drop the `upstream_text: str` parameter from the signature, keep everything else in the method body unchanged, and add the `upstream_text = self._gather_upstream_text(node_id)` line as the new first line before `criteria = params.get("criteria", "")`.)

Update `_run_logic_gate`'s signature (line 407) the same way:

```python
    def _run_logic_gate(self, node_id: str, params: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        upstream_text = self._gather_upstream_text(node_id)
        condition_type = params.get("condition_type", "contains")
```

- [ ] **Step 6: Drop implicit upstream fallback from the AI-prompt and image-generate branches**

Replace lines 518-542 (the Gemini/Claude/ChatGPT/image-generate branches):

```python
        # --- Gemini-backed functions (adapters/gemini-bridge, uses a signed-in browser session, no API key) ---
        if tool_id == "function_google_search":
            instructions = self._substitute_tokens(params.get("instructions", ""))
            return self._ask_gemini(instructions, use_search=True), None
        if tool_id == "function_gemini_ask":
            instructions = self._substitute_tokens(params.get("instructions", ""))
            return self._ask_gemini(instructions), None

        # --- Claude-backed functions (adapters/claude-bridge, mock-mode until real API access exists) ---
        if tool_id == "function_claude_ask":
            instructions = self._substitute_tokens(params.get("instructions", ""))
            return self._ask_claude(instructions), None

        # --- ChatGPT-backed functions (adapters/chatgpt-bridge, mock-mode until real API access exists) ---
        if tool_id == "function_chatgpt_ask":
            instructions = self._substitute_tokens(params.get("instructions", ""))
            return self._ask_chatgpt(instructions), None

        if tool_id == "function_image_generate":
            prompt = self._substitute_tokens(params.get("prompt", ""))
            output_dir = params.get("output_dir") or str(self.router.base_dir / "02_vault" / "generated_images")
            return self._generate_image_gemini(prompt, output_dir), None
```

- [ ] **Step 7: Rename `_extract_json_field` to `_extract_json_field_or_raw` and drop its use as a blank-field fallback**

Replace `_extract_json_field` (lines 360-370):

```python
    def _extract_json_field_or_raw(self, value: str, key: str) -> str:
        # Lets a field accept either a bare string (typed directly, or the
        # plain output of a node whose captured output already IS that
        # value) or an upstream node's raw JSON output (e.g. a Create
        # Notebook node's {"notebook_id": ..., "title": ...}) -- if value
        # parses as a JSON object containing key, that field is pulled out;
        # otherwise value is used exactly as given.
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return value
        if isinstance(parsed, dict) and key in parsed:
            return str(parsed[key])
        return value
```

Replace the two NotebookLM branches that used it as a blank-field fallback (lines 549-567):

```python
        if tool_id == "function_notebooklm_upload_sources":
            notebook_id = self._extract_json_field_or_raw(self._substitute_tokens(params.get("notebook_id", "")), "notebook_id")
            if not notebook_id:
                raise WorkflowRunError("Upload Sources requires a notebook_id -- bind {{label}} to a Create Notebook node's output, or type one directly.")
            raw_paths = self._substitute_tokens(params.get("file_paths", ""))
            file_paths = [p.strip() for p in raw_paths.splitlines() if p.strip()]
            if not file_paths:
                raise WorkflowRunError("Upload Sources requires at least one file path.")
            return self._upload_notebooklm_sources(notebook_id, file_paths), None

        if tool_id == "function_notebooklm_prompt_loop":
            notebook_id = self._extract_json_field_or_raw(self._substitute_tokens(params.get("notebook_id", "")), "notebook_id")
            if not notebook_id:
                raise WorkflowRunError("Prompt Loop requires a notebook_id -- bind {{label}} to a Create Notebook node's output, or type one directly.")
            raw_prompts = self._substitute_tokens(params.get("prompts", ""))
            prompts = [p.strip() for p in raw_prompts.splitlines() if p.strip()]
            if not prompts:
                raise WorkflowRunError("Prompt Loop requires at least one prompt.")
            return self._run_notebooklm_prompt_loop(notebook_id, prompts), None
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine_tokens.py`
Expected: `8/8 passed`

- [ ] **Step 9: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine_tokens.py
git commit -m "$(cat <<'EOF'
Require explicit {{label}} binding except where a node has no alternative

Skill, Logic Gate, Review Gate, and Concatenate keep reading whatever's
directly connected (their whole defined purpose, no settings field exists
for it). Every other function node now requires an explicit {{label}}
reference instead of silently appending or guessing from upstream text.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: UI — Output Label field, default generation, duplicate auto-suffix, rename cascade

**Files:**
- Modify: `00_System/templates/workflow-builder.html`

**Interfaces:**
- Consumes: nothing from Task 1/2 (this only edits client-side `data.label`/`data.params` in the saved graph JSON; the engine reads whatever ends up saved).
- Produces: `allWorkflowLabels(excludeNodeId)`, `uniqueLabel(candidate, excludeNodeId)`, `nextDefaultLabel(toolId)`, `directPredecessorLabels(nodeId)`, `renderInputsChips(nodeId)`, `wfbRenameLabelReferences(oldLabel, newLabel)`, `window.wfbSaveLabel()` — Task 4 (autocomplete) and Task 5 (failure feedback) build on `directPredecessorLabels`.

- [ ] **Step 1: Add the persistent Label + Input(s) header to the panel markup**

Modify the right panel markup (lines 88-96):

```html
    <!-- Right panel: selected node's config, identical fields to its popup where one exists -->
    <div class="w-80 shrink-0 bg-surface border border-border rounded-xl flex flex-col overflow-hidden">
        <div class="px-4 py-3 border-b border-border shrink-0">
            <h4 class="text-xs font-semibold text-heading uppercase tracking-wider">Node Configuration</h4>
        </div>
        <div id="wfb-panel-header" class="hidden px-4 py-3 border-b border-border shrink-0 space-y-2">
            <div class="space-y-1.5">
                <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Output Label (reference as {{label}})</label>
                <div class="flex gap-1.5">
                    <input type="text" id="wfb-panel-label-input" class="flex-1 bg-canvas border border-border rounded px-3 py-2 text-heading font-mono text-xs focus:outline-none focus:border-primary">
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
    </div>
```

- [ ] **Step 2: Add label-management helpers**

Add these right after `otherCanvasNodes` (after line 956):

```javascript
        function allWorkflowLabels(excludeNodeId) {
            // Graph-wide (every module, not just the currently open one) --
            // labels must be unique across the whole flattened workflow,
            // the same way node IDs already are.
            const exported = editor.export().drawflow;
            const result = [];
            Object.values(exported).forEach(mod => {
                Object.entries(mod.data || {}).forEach(([id, node]) => {
                    if (id !== excludeNodeId) result.push({ id, label: node.data.label });
                });
            });
            return result;
        }

        function uniqueLabel(candidate, excludeNodeId) {
            const taken = new Set(allWorkflowLabels(excludeNodeId).map(n => n.label));
            if (!taken.has(candidate)) return candidate;
            let n = 2;
            while (taken.has(`${candidate}_${n}`)) n += 1;
            return `${candidate}_${n}`;
        }

        const labelCounters = {};
        function nextDefaultLabel(toolId) {
            labelCounters[toolId] = (labelCounters[toolId] || 0) + 1;
            return uniqueLabel(`${toolId}_${labelCounters[toolId]}`, null);
        }

        function directPredecessorLabels(nodeId) {
            const node = editor.getNodeFromId(nodeId);
            const connections = (node.inputs && node.inputs.input_1 && node.inputs.input_1.connections) || [];
            return connections.map(c => editor.getNodeFromId(c.node).data.label).filter(Boolean);
        }

        function renderInputsChips(nodeId) {
            const box = document.getElementById("wfb-panel-inputs");
            const labels = directPredecessorLabels(nodeId);
            if (!labels.length) {
                box.innerHTML = `<span class="text-muted text-[10px]">No connected inputs yet.</span>`;
                return;
            }
            box.innerHTML = labels.map(l => `<span class="px-2 py-1 rounded bg-canvas border border-border-strong font-mono text-[10px] text-primary-400 cursor-pointer hover:bg-primary/15" data-insert-label="${escapeHtml(l)}">{{${escapeHtml(l)}}}</span>`).join("");
        }

        function wfbRenameLabelReferences(oldLabel, newLabel) {
            // Connections never cross modules (Drawflow enforces this), and a
            // label is only ever referenceable via a direct connection -- so
            // only the current module can possibly contain a {{oldLabel}}
            // reference. No need to switch modules to check others.
            if (oldLabel === newLabel) return;
            const oldToken = "{{" + oldLabel + "}}";
            const newToken = "{{" + newLabel + "}}";
            const moduleData = editor.export().drawflow[currentModuleName].data;
            Object.entries(moduleData).forEach(([id, rawNode]) => {
                const params = rawNode.data.params || {};
                let changed = false;
                const newParams = {};
                Object.entries(params).forEach(([key, value]) => {
                    if (typeof value === "string" && value.includes(oldToken)) {
                        newParams[key] = value.split(oldToken).join(newToken);
                        changed = true;
                    } else {
                        newParams[key] = value;
                    }
                });
                if (changed) editor.updateNodeDataFromId(id, { ...rawNode.data, params: newParams });
            });
            if (selectedNodeId) selectNode(selectedNodeId);
        }

        window.wfbSaveLabel = function() {
            if (!selectedNodeId) return;
            const input = document.getElementById("wfb-panel-label-input");
            const requested = input.value.trim();
            if (!requested) { alert("Output label can't be empty."); return; }
            const finalLabel = uniqueLabel(requested, selectedNodeId);
            const node = editor.getNodeFromId(selectedNodeId);
            const oldLabel = node.data.label;
            editor.updateNodeDataFromId(selectedNodeId, { ...node.data, label: finalLabel });
            input.value = finalLabel;
            if (finalLabel !== oldLabel) wfbRenameLabelReferences(oldLabel, finalLabel);
            wfbLog(`Output label set to "${finalLabel}". Reference it elsewhere as {{${finalLabel}}}.`, "text-success-400");
        };
```

- [ ] **Step 3: Assign a default label when a node is created**

Modify `addNodeToCanvas` (lines 375-403):

```javascript
        function addNodeToCanvas(meta, posX, posY) {
            if (meta.tool_id === "container") {
                containerCounter += 1;
                const moduleName = `container_${Date.now()}_${containerCounter}`;
                const title = `Container ${containerCounter}`;
                editor.addModule(moduleName);
                const data = { kind: "container", tool_id: "container", category: null, title, label: nextDefaultLabel("container"), description: "", params: {}, module_name: moduleName };
                editor.addNode("container", 1, 1, posX, posY, "kind-container", data, containerNodeHtml(title), false);
                return;
            }

            const data = {
                kind: meta.kind,
                tool_id: meta.tool_id,
                category: meta.category || null,
                title: meta.title,
                label: nextDefaultLabel(meta.tool_id),
                description: meta.description || "",
                model: meta.model || null,
                licensed: meta.licensed,
                icon_source: meta.icon_source || "fa",
                svgl_icon_url: meta.svgl_icon_url || null,
                fa_icon: meta.fa_icon || null,
                params: {},
            };
            let cssClass = HUMAN_CHECKPOINT_TOOL_IDS.includes(meta.tool_id) ? "kind-human-checkpoint" : `kind-${meta.kind}`;
            if (meta.licensed === false) cssClass += " kind-greyed";
            editor.addNode(meta.tool_id, 1, 1, posX, posY, cssClass, data, nodeHtml(meta), false);
            recomputeClassificationBadge();
        }
```

- [ ] **Step 4: Populate/hide the header in `selectNode`/`clearPanel`**

Modify `selectNode` and `clearPanel` (lines 1040-1064):

```javascript
        function selectNode(nodeId) {
            selectedNodeId = nodeId;
            const data = currentNodeData(nodeId);

            const header = document.getElementById("wfb-panel-header");
            header.classList.remove("hidden");
            document.getElementById("wfb-panel-label-input").value = data.label || "";
            renderInputsChips(nodeId);

            if (data.kind === "task" || data.kind === "process" || data.kind === "adapter") {
                const argSchema = ARG_FIELD_SCHEMAS[data.tool_id];
                if (FIELD_PARTIAL_TOOL_IDS.includes(data.tool_id)) {
                    renderFieldPartialPanel(nodeId, data);
                } else if (argSchema) {
                    renderArgFieldsPanel(nodeId, data, argSchema);
                } else {
                    renderGenericArgsPanel(nodeId, data);
                }
            } else if (data.kind === "skill") {
                renderSkillPanel(data);
            } else if (data.kind === "function") {
                renderFunctionPanel(nodeId, data);
            } else if (data.kind === "container") {
                renderContainerPanel(nodeId, data);
            }
        }

        function clearPanel() {
            selectedNodeId = null;
            document.getElementById("wfb-panel-header").classList.add("hidden");
            document.getElementById("wfb-panel-body").innerHTML = `<div class="text-muted">Select a node on the canvas to configure it.</div>`;
        }
```

- [ ] **Step 5: Manual verification**

Start the dev server the way this project normally runs it (check `00_System/server.py`'s `if __name__ == "__main__"` block if unfamiliar), open the Workflow Builder page, and:
1. Drag a node onto the canvas, select it, confirm the Output Label field shows an auto-generated default like `function_gemini_ask_1`.
2. Change it to `CG-JSON`, click Save, confirm the log shows the "Output label set to..." message.
3. Add a second node of the same tool type, confirm its default label is `function_gemini_ask_2` (counter keeps incrementing, doesn't collide with the renamed first node).
4. Rename the second node's label to `CG-JSON` too (colliding with the first), click Save, confirm it silently becomes `CG-JSON_2` instead of blocking.
5. Add a third node, connect it downstream of the first, type `{{CG-JSON}}` manually into one of its text fields, save that node's config. Reselect the first node and rename its label from `CG-JSON` to `Curriculum`. Reselect the third node and confirm its field now reads `{{Curriculum}}`.

- [ ] **Step 6: Commit**

```bash
git add 00_System/templates/workflow-builder.html
git commit -m "$(cat <<'EOF'
Add Output Label field with auto-suffix and live rename cascade

Every node gets an auto-generated, always-editable label used as its
{{token}} name. Duplicate labels auto-suffix instead of blocking; renaming
rewrites every {{oldLabel}} reference elsewhere in the same module live,
in the browser, before Save.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: UI — Input(s) click-to-insert and `{{`-triggered autocomplete

**Files:**
- Modify: `00_System/templates/workflow-builder.html`

**Interfaces:**
- Consumes: `directPredecessorLabels(nodeId)`, `selectedNodeId`, `escapeHtml` from Task 3 / existing code.

- [ ] **Step 1: Make the panel a positioning context and add the suggestion dropdown element**

Modify the panel wrapper's class list (the same `<div class="w-80 ...">` from Task 3 Step 1) to add `relative`, and add the suggestion box right after `#wfb-panel-body`:

```html
    <div class="w-80 shrink-0 bg-surface border border-border rounded-xl flex flex-col overflow-hidden relative">
```

```html
        <div id="wfb-panel-body" class="flex-1 overflow-y-auto custom-scrollbar p-4 text-xs space-y-3">
            <div class="text-muted">Select a node on the canvas to configure it.</div>
        </div>
        <div id="wfb-token-suggest" class="hidden absolute z-50 bg-surface border border-border-strong rounded-lg shadow-lg max-h-40 overflow-y-auto custom-scrollbar text-xs"></div>
    </div>
```

- [ ] **Step 2: Track the last-focused field and wire click-to-insert from the Input(s) chips**

Add near the bottom of the file, before the closing `document.getElementById("wfb-palette-search").addEventListener(...)` block:

```javascript
        // One delegated focus listener covers every text/textarea field in
        // the node config panel, present and future, so click-to-insert
        // knows where to put the token without each renderXPanel wiring it.
        let wfbLastFocusedField = null;
        document.getElementById("wfb-panel-body").addEventListener("focusin", (e) => {
            if (e.target.matches("textarea, input[type='text']")) wfbLastFocusedField = e.target;
        });

        document.getElementById("wfb-panel-inputs").addEventListener("click", (e) => {
            const chip = e.target.closest("[data-insert-label]");
            if (!chip || !wfbLastFocusedField) return;
            const field = wfbLastFocusedField;
            const token = "{{" + chip.dataset.insertLabel + "}}";
            const cursor = field.selectionStart ?? field.value.length;
            field.value = field.value.slice(0, cursor) + token + field.value.slice(cursor);
            const newCursor = cursor + token.length;
            field.focus();
            field.setSelectionRange(newCursor, newCursor);
        });
```

- [ ] **Step 3: Add the `{{`-triggered autocomplete dropdown**

Add right after the click-to-insert code from Step 2:

```javascript
        let wfbSuggestField = null;

        function closeTokenSuggest() {
            document.getElementById("wfb-token-suggest").classList.add("hidden");
            wfbSuggestField = null;
        }

        function openTokenSuggest(field) {
            if (!selectedNodeId) return;
            const labels = directPredecessorLabels(selectedNodeId);
            if (!labels.length) { closeTokenSuggest(); return; }
            const box = document.getElementById("wfb-token-suggest");
            box.innerHTML = labels.map(l => `<div class="px-3 py-1.5 hover:bg-primary/15 cursor-pointer font-mono" data-suggest-label="${escapeHtml(l)}">{{${escapeHtml(l)}}}</div>`).join("");
            const fieldRect = field.getBoundingClientRect();
            const panelRect = field.closest("#wfb-panel-body").getBoundingClientRect();
            box.style.left = (fieldRect.left - panelRect.left) + "px";
            box.style.top = (fieldRect.bottom - panelRect.top) + "px";
            box.style.width = fieldRect.width + "px";
            box.classList.remove("hidden");
            wfbSuggestField = field;
        }

        document.getElementById("wfb-panel-body").addEventListener("input", (e) => {
            const field = e.target;
            if (!field.matches("textarea, input[type='text']")) return;
            const cursor = field.selectionStart;
            const lastTwo = field.value.slice(Math.max(0, cursor - 2), cursor);
            if (lastTwo === "{{") {
                openTokenSuggest(field);
            } else {
                closeTokenSuggest();
            }
        });

        document.getElementById("wfb-token-suggest").addEventListener("mousedown", (e) => {
            const opt = e.target.closest("[data-suggest-label]");
            if (!opt || !wfbSuggestField) return;
            e.preventDefault(); // keep focus (and cursor position) in the field
            const field = wfbSuggestField;
            const cursor = field.selectionStart;
            const insertion = opt.dataset.suggestLabel + "}}";
            field.value = field.value.slice(0, cursor) + insertion + field.value.slice(cursor);
            const newCursor = cursor + insertion.length;
            field.focus();
            field.setSelectionRange(newCursor, newCursor);
            closeTokenSuggest();
        });

        document.addEventListener("click", (e) => {
            if (!e.target.closest("#wfb-token-suggest") && e.target !== wfbSuggestField) closeTokenSuggest();
        });
```

- [ ] **Step 4: Manual verification**

With the dev server running and the Workflow Builder open:
1. Select a node with at least one direct-connected predecessor, confirm its Input(s) chips are listed.
2. Click a chip while a text field has focus, confirm `{{label}}` is inserted at the cursor and the field keeps focus.
3. In a different field, type `{{`, confirm the dropdown appears listing the same labels positioned right under the field.
4. Click a suggestion, confirm it completes to `{{label}}` (no doubled braces) at the cursor.
5. Select a node with no connected predecessors, confirm the Input(s) box reads "No connected inputs yet." and typing `{{` shows no dropdown.
6. Click elsewhere on the page while the dropdown is open, confirm it closes without inserting anything.

- [ ] **Step 5: Commit**

```bash
git add 00_System/templates/workflow-builder.html
git commit -m "$(cat <<'EOF'
Add click-to-insert and {{-triggered autocomplete for input tokens

Both work off the same connection-scoped label list: clicking an Input(s)
chip inserts {{label}} at the last-focused field's cursor, and typing {{
in any field opens the same suggestions inline.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: UI — red outline + tooltip on failed nodes after a run

**Files:**
- Modify: `00_System/templates/workflow-builder.html`

**Interfaces:**
- Consumes: `data.steps` (already returned by `/api/workflow-builder/run`, each entry has `node_id`/`status`/`output`).

- [ ] **Step 1: Add the failure-outline CSS**

Add to the `<style>` block (near line 100, alongside the existing Drawflow theme overrides):

```css
    .wfb-node-failed {
        outline: 2px solid var(--color-danger-400, #ef4444) !important;
        outline-offset: 2px;
    }
```

- [ ] **Step 2: Clear stale outlines at the start of each run, apply fresh ones per failed step**

Modify `wfbRun` (lines 1203-1235):

```javascript
        window.wfbRun = async function() {
            const dryRun = document.getElementById("wfb-dry-run").checked;
            const graphJson = editor.export();

            document.querySelectorAll(".wfb-node-failed").forEach(el => {
                el.classList.remove("wfb-node-failed");
                el.removeAttribute("title");
            });

            wfbSetRunStatus("Running...", "text-warning-400");
            wfbLog(`Starting ${dryRun ? "dry" : "live"} run...`, "text-info-400");

            try {
                const response = await fetch("/api/workflow-builder/run", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ graph_json: graphJson, dry_run: dryRun }),
                });
                const data = await response.json();
                if (!response.ok) { wfbLog(data.detail || "Run failed to start.", "text-danger-400"); wfbSetRunStatus("Failed", "text-danger-400"); return; }

                (data.steps || []).forEach(step => {
                    const color = step.status === "success" ? "text-body" : "text-danger-400";
                    wfbLog(`[${step.kind || "?"}] ${step.title || step.node_id}: ${step.status}${step.output ? " -- " + step.output : ""}`, color);

                    const nodeEl = document.getElementById(`node-${step.node_id}`);
                    if (nodeEl && step.status === "failed") {
                        nodeEl.classList.add("wfb-node-failed");
                        nodeEl.title = step.output || "Failed";
                    }
                });

                if (data.success) {
                    wfbLog("Workflow run complete.", "text-success-400");
                    wfbSetRunStatus("Complete", "text-success-400");
                } else {
                    wfbLog("Workflow run finished with failures.", "text-danger-400");
                    wfbSetRunStatus("Failed", "text-danger-400");
                }
            } catch (err) {
                wfbLog(`System error: ${err.message}`, "text-danger-400");
                wfbSetRunStatus("Error", "text-danger-400");
            }
        };
```

- [ ] **Step 3: Manual verification**

With the dev server running and the Workflow Builder open:
1. Build a 2-node workflow where the second node references a `{{label}}` that isn't directly connected to it (or references a nonexistent label). Click Run (dry run checked).
2. Confirm the second node gets a red outline on the canvas, and hovering over it shows a tooltip with the `Missing input value: {{label}} -- ...` message.
3. Fix the reference (correct the label, or wire the missing connection), click Run again, confirm the outline clears from that node.
4. Reproduce a failure on one node, then in a later run make a DIFFERENT node fail while the first node now succeeds — confirm the first node's outline is cleared (not left stale) once its step reports success.

- [ ] **Step 4: Commit**

```bash
git add 00_System/templates/workflow-builder.html
git commit -m "$(cat <<'EOF'
Show a red outline and error tooltip on nodes that fail during a run

Reuses the run endpoint's existing per-step status/output -- no new
backend data needed. Outlines clear at the start of the next run so a
fixed node doesn't stay marked failed.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
