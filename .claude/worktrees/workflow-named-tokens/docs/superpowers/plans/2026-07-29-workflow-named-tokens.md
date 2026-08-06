# Workflow Builder Named Tokens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Workflow Builder nodes be referenced by a human-friendly `{Name}` token (the node's own title) instead of only the raw `{{node_id}}`, with a reserved `{input}` token for "everything directly upstream," while keeping `{{node_id}}` working unchanged.

**Architecture:** `workflow_engine.py`'s `_substitute_tokens` gains a second, order-safe regex pass for single-brace `{Name}` tokens resolved through a `title -> node_id` map built once per run from each node's explicitly-set title; `{input}` is a literal pre-pass using the same value `_gather_upstream_text` already computes. `workflow-builder.html` gains one universal node-rename control (replacing the container-only one) with duplicate-name validation, and a lightweight `{`-triggered autocomplete dropdown wired once via event delegation so it works for every field type without touching each panel renderer.

**Tech Stack:** Python 3 (stdlib `re`), vanilla JS (no new dependencies), Drawflow (already in use).

## Global Constraints

- `{{node_id}}` must keep resolving exactly as it does today — this is strictly additive.
- No new Python or JS dependencies.
- Reserved word `input` (case-insensitive) cannot be used as a node's custom title, since it would be permanently shadowed by the literal `{input}` token.
- Match existing code conventions: this file's comment style (`# ...` explaining *why*, not what), existing Tailwind utility classes, existing `escapeHtml`/`wfbLog` helpers in `workflow-builder.html`.

---

### Task 1: Engine — title-based tokens + `{input}` in `workflow_engine.py`

**Files:**
- Modify: `00_System/workflow_engine.py`
- Create: `00_System/test_workflow_engine.py`

**Interfaces:**
- Produces: `WorkflowEngine.title_to_node_id: Dict[str, str]` (built fresh on every `run()` call), `WorkflowEngine._substitute_tokens(text: str, upstream_text: str = "") -> str` (signature change — now takes an explicit `upstream_text` second argument).
- Consumes: nothing new from other tasks; this is the foundation Task 2/3 (UI) build on top of.

- [ ] **Step 1: Write the failing tests**

Create `00_System/test_workflow_engine.py`:

```python
# 00_System/test_workflow_engine.py
"""Assert-based smoke tests for WorkflowEngine's named-token substitution.
Run directly: python test_workflow_engine.py
"""
import sys
sys.dont_write_bytecode = True

from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from workflow_engine import WorkflowEngine, WorkflowRunError


def _minimal_graph(node_specs):
    """Builds a minimal valid Drawflow-shaped graph_json from a list of
    (node_id, title, tool_id, params, outgoing_targets) tuples, all in the
    "Home" module, wired in the given order."""
    data = {}
    for node_id, title, tool_id, params, targets in node_specs:
        data[node_id] = {
            "name": tool_id,
            "data": {
                "kind": "function",
                "tool_id": tool_id,
                "category": None,
                "title": title,
                "params": params,
            },
            "outputs": {
                "output_1": {
                    "connections": [{"node": t, "output": "input_1"} for t in targets]
                }
            },
        }
    return {"drawflow": {"Home": {"data": data}}}


def test_named_token_resolves_via_title():
    engine = WorkflowEngine(dry_run=True)
    engine.context = {"5": "hello from node 5"}
    engine.title_to_node_id = {"Alpha": "5"}
    result = engine._substitute_tokens("value is {Alpha}", upstream_text="")
    assert result == "value is hello from node 5", result


def test_input_literal_resolves_to_upstream_text():
    engine = WorkflowEngine(dry_run=True)
    result = engine._substitute_tokens("wrapped: [{input}]", upstream_text="UPSTREAM")
    assert result == "wrapped: [UPSTREAM]", result


def test_double_and_single_brace_coexist():
    engine = WorkflowEngine(dry_run=True)
    engine.context = {"5": "FIVE", "6": "SIX"}
    engine.title_to_node_id = {"Alpha": "5"}
    result = engine._substitute_tokens("{{6}} and {Alpha} and {input}", upstream_text="UP")
    assert result == "SIX and FIVE and UP", result


def test_unknown_named_token_resolves_to_empty_string():
    engine = WorkflowEngine(dry_run=True)
    result = engine._substitute_tokens("[{DoesNotExist}]", upstream_text="")
    assert result == "[]", result


def test_duplicate_titles_raise_at_run_start():
    engine = WorkflowEngine(dry_run=True)
    graph = _minimal_graph([
        ("1", "Same Name", "function_concatenate", {"separator": ""}, ["3"]),
        ("2", "Same Name", "function_concatenate", {"separator": ""}, ["3"]),
        ("3", "Combine", "function_concatenate", {"separator": "-"}, []),
    ])
    try:
        engine.run(graph)
        assert False, "expected WorkflowRunError for duplicate titles"
    except WorkflowRunError as e:
        assert "Same Name" in str(e), str(e)


def test_reserved_input_title_rejected():
    engine = WorkflowEngine(dry_run=True)
    graph = _minimal_graph([
        ("1", "input", "function_concatenate", {"separator": ""}, []),
    ])
    try:
        engine.run(graph)
        assert False, "expected WorkflowRunError for reserved 'input' title"
    except WorkflowRunError as e:
        assert "reserved" in str(e).lower(), str(e)


def test_named_token_end_to_end_through_run():
    engine = WorkflowEngine(dry_run=True)
    graph = _minimal_graph([
        ("10", "Source", "function_concatenate", {"separator": ""}, ["20"]),
        ("20", "Combine", "function_concatenate", {"separator": "|{Source}|"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    combine_entry = next(s for s in result["steps"] if s["node_id"] == "20")
    assert combine_entry["output"] == "|" + "" + "|", combine_entry


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

Run: `python 00_System/test_workflow_engine.py`
Expected: `FAIL test_named_token_resolves_via_title: ...` and similar — `_substitute_tokens` doesn't accept `upstream_text` yet, `title_to_node_id` doesn't exist, and duplicate-title/reserved-word checks don't exist yet. (This will actually raise a `TypeError` on the first test rather than a clean assertion failure, since the current `_substitute_tokens(self, text)` doesn't accept a second positional arg — that's expected and confirms the tests are exercising the not-yet-built interface.)

- [ ] **Step 3: Add `explicit_title` to parsed node data**

In `00_System/workflow_engine.py`, modify `_parse_graph` (around line 165-175):

```python
            for node_id, raw in raw_nodes.items():
                node_id = str(node_id)
                data = raw.get("data") or {}
                nodes[node_id] = {
                    "kind": data.get("kind"),
                    "tool_id": data.get("tool_id"),
                    "category": data.get("category"),
                    "title": data.get("title") or raw.get("name") or node_id,
                    "explicit_title": data.get("title") or None,
                    "params": data.get("params") or {},
                    "module_name": data.get("module_name"),
                }
```

(Only the new `"explicit_title": data.get("title") or None,` line is added — `explicit_title` is `None` unless the user actually set a custom title, distinguishing it from `title`'s Drawflow-default-name fallback used for display/logging.)

- [ ] **Step 4: Add the reserved single-brace regex and `title_to_node_id` init**

Near the existing `TOKEN_PATTERN` (line 96), add:

```python
TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-]+)\s*\}\}")
# Single-brace named tokens, e.g. {CG-File}. The negative lookaround/lookahead
# stop this from matching the inner text of a {{node_id}} pair -- {{x}} has an
# outer { immediately before and an outer } immediately after the inner {x},
# so both syntaxes can coexist in the same field.
NAMED_TOKEN_PATTERN = re.compile(r"(?<!\{)\{([^{}]+)\}(?!\})")
RESERVED_TOKEN_NAMES = {"input"}
```

In `WorkflowEngine.__init__` (around line 121-137), add one line after `self.context: Dict[str, str] = {}`:

```python
        self.title_to_node_id: Dict[str, str] = {}
```

- [ ] **Step 5: Rewrite `_substitute_tokens` and thread `upstream_text` through every call site**

Replace `_substitute_tokens` (lines 258-266):

```python
    def _substitute_tokens(self, text: str, upstream_text: str = "") -> str:
        # Three passes, in order: (1) the reserved {input} literal, standing in for
        # "everything directly upstream, concatenated" -- the same value
        # _gather_upstream_text already computes; (2) single-brace {Name} tokens,
        # resolved via title_to_node_id then the same self.context lookup as (3);
        # (3) the original {{node_id}} tokens, unchanged.
        if not text:
            return text
        text = text.replace("{input}", upstream_text)
        text = NAMED_TOKEN_PATTERN.sub(
            lambda m: self.context.get(self.title_to_node_id.get(m.group(1).strip(), ""), ""),
            text,
        )
        return TOKEN_PATTERN.sub(lambda m: self.context.get(m.group(1), ""), text)
```

Then update every call site to pass `upstream_text` as the second argument. `upstream_text` is already a local variable or parameter in scope at each one:

In `_run_logic_gate` (line 414):
```python
        condition_value = self._substitute_tokens(params.get("condition_value", ""), upstream_text)
```

In `_execute_node` (line 481):
```python
            args = [self._substitute_tokens(str(a), upstream_text) for a in (params.get("args") or [])]
```

In `_execute_function_node` (lines 510, 519, 523, 529, 535, 540, 546, 550, 553, 560, 563) — every `self._substitute_tokens(params.get(...))` call in that method becomes `self._substitute_tokens(params.get(...), upstream_text)`, e.g.:

```python
        if tool_id == "function_concatenate":
            separator = self._substitute_tokens(params.get("separator", "\n\n"), upstream_text)
```
```python
        if tool_id == "function_google_search":
            instructions = self._substitute_tokens(params.get("instructions", ""), upstream_text)
```
```python
        if tool_id == "function_gemini_ask":
            instructions = self._substitute_tokens(params.get("instructions", ""), upstream_text)
```
```python
        if tool_id == "function_claude_ask":
            instructions = self._substitute_tokens(params.get("instructions", ""), upstream_text)
```
```python
        if tool_id == "function_chatgpt_ask":
            instructions = self._substitute_tokens(params.get("instructions", ""), upstream_text)
```
```python
        if tool_id == "function_image_generate":
            prompt = self._substitute_tokens(params.get("prompt", ""), upstream_text) or upstream_text
```
```python
        if tool_id == "function_notebooklm_create":
            title = self._substitute_tokens(params.get("title", ""), upstream_text) or "Untitled Notebook"
```
```python
        if tool_id == "function_notebooklm_upload_sources":
            notebook_id = self._substitute_tokens(params.get("notebook_id", ""), upstream_text) or self._extract_json_field(upstream_text, "notebook_id")
            if not notebook_id:
                raise WorkflowRunError("Upload Sources requires a notebook_id (set one directly, or chain from a Create Notebook node).")
            raw_paths = self._substitute_tokens(params.get("file_paths", ""), upstream_text)
```
```python
        if tool_id == "function_notebooklm_prompt_loop":
            notebook_id = self._substitute_tokens(params.get("notebook_id", ""), upstream_text) or self._extract_json_field(upstream_text, "notebook_id")
            if not notebook_id:
                raise WorkflowRunError("Prompt Loop requires a notebook_id (set one directly, or chain from a Create Notebook node).")
            raw_prompts = self._substitute_tokens(params.get("prompts", ""), upstream_text)
```

- [ ] **Step 6: Build and validate `title_to_node_id` in `run()`**

In `run()` (around line 579-580), right after `self.backward_edges = backward_edges`, add:

```python
        self.title_to_node_id = {}
        for nid, n in nodes.items():
            explicit = (n.get("explicit_title") or "").strip()
            if not explicit:
                continue
            if explicit.lower() in RESERVED_TOKEN_NAMES:
                raise WorkflowRunError(
                    f'Node "{explicit}" cannot use the reserved name "{explicit}" -- '
                    f'that name is reserved for the automatic upstream-input token.'
                )
            if explicit in self.title_to_node_id:
                raise WorkflowRunError(
                    f'Two nodes are both named "{explicit}" -- node names must be unique '
                    f'to be used as {{tokens}}. Rename one of them.'
                )
            self.title_to_node_id[explicit] = nid
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python 00_System/test_workflow_engine.py`
Expected: `7/7 passed`

- [ ] **Step 8: Commit**

```bash
git add 00_System/workflow_engine.py 00_System/test_workflow_engine.py
git commit -m "$(cat <<'EOF'
Add human-friendly {Name} workflow tokens alongside {{node_id}}

Node titles now double as token names; {input} is a reserved literal for
"everything directly upstream". {{node_id}} keeps working unchanged.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: UI — universal node rename control with duplicate validation

**Files:**
- Modify: `00_System/templates/workflow-builder.html`

**Interfaces:**
- Consumes: nothing from Task 1 directly (this only edits `title` in the saved graph JSON; Task 1's engine reads whatever `title` ends up saved).
- Produces: a global helper `allCanvasNodes(excludeNodeId)` that Task 3's autocomplete will also use.

This task also removes the container-only rename control (`data-panel-container-name` / the `"container-name"` branch in `wfbSaveNodePanel`), since every node now gets the same rename control.

- [ ] **Step 1: Add the persistent rename row to the panel HTML**

In `00_System/templates/workflow-builder.html`, modify the right panel markup (lines 88-96):

```html
    <!-- Right panel: selected node's config, identical fields to its popup where one exists -->
    <div class="w-80 shrink-0 bg-surface border border-border rounded-xl flex flex-col overflow-hidden">
        <div class="px-4 py-3 border-b border-border shrink-0">
            <h4 class="text-xs font-semibold text-heading uppercase tracking-wider">Node Configuration</h4>
        </div>
        <div id="wfb-panel-name-row" class="hidden px-4 py-3 border-b border-border shrink-0 space-y-1.5">
            <label class="block text-muted font-mono uppercase tracking-wider text-[10px]">Node Name (used as its {token})</label>
            <div class="flex gap-1.5">
                <input type="text" id="wfb-panel-name-input" class="flex-1 bg-canvas border border-border rounded px-3 py-2 text-heading text-xs focus:outline-none focus:border-primary">
                <button onclick="window.wfbRenameSelectedNode()" class="px-3 py-1.5 bg-primary/15 hover:bg-primary/25 text-primary-400 border border-primary/30 text-xs font-semibold rounded transition-colors">Save</button>
            </div>
        </div>
        <div id="wfb-panel-body" class="flex-1 overflow-y-auto custom-scrollbar p-4 text-xs space-y-3">
            <div class="text-muted">Select a node on the canvas to configure it.</div>
        </div>
    </div>
```

- [ ] **Step 2: Add `allCanvasNodes`, populate/clear the name row, and the rename handler**

Add a graph-wide sibling to the existing module-scoped `otherCanvasNodes` (right after it, around line 956):

```javascript
        function allCanvasNodes(excludeNodeId) {
            // Graph-wide (every module, not just the currently open one) -- needed
            // because token uniqueness is enforced across the whole flattened graph,
            // not just the container/module currently being edited.
            const exported = editor.export().drawflow;
            const result = [];
            Object.values(exported).forEach(mod => {
                Object.entries(mod.data || {}).forEach(([id, node]) => {
                    if (id !== excludeNodeId) result.push({ id, title: node.data.title });
                });
            });
            return result;
        }
```

Modify `selectNode` (lines 1040-1059) to show/populate the name row, and `clearPanel` (lines 1061-1064) to hide it:

```javascript
        function selectNode(nodeId) {
            selectedNodeId = nodeId;
            const data = currentNodeData(nodeId);

            const nameRow = document.getElementById("wfb-panel-name-row");
            nameRow.classList.remove("hidden");
            document.getElementById("wfb-panel-name-input").value = data.title || "";

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
            document.getElementById("wfb-panel-name-row").classList.add("hidden");
            document.getElementById("wfb-panel-body").innerHTML = `<div class="text-muted">Select a node on the canvas to configure it.</div>`;
        }
```

Add the rename handler near `wfbSaveNodePanel` (around line 1066):

```javascript
        window.wfbRenameSelectedNode = function() {
            if (!selectedNodeId) return;
            const newTitle = document.getElementById("wfb-panel-name-input").value.trim();
            if (!newTitle) { alert("Node name can't be empty."); return; }
            if (newTitle.toLowerCase() === "input") {
                alert('"input" is a reserved name (it always means "everything directly upstream") -- choose a different name.');
                return;
            }
            const collision = allCanvasNodes(selectedNodeId).find(n => n.title === newTitle);
            if (collision) {
                alert(`A node named "${newTitle}" already exists -- choose a different name.`);
                return;
            }
            const node = editor.getNodeFromId(selectedNodeId);
            editor.updateNodeDataFromId(selectedNodeId, { ...node.data, title: newTitle });
            const titleEl = document.querySelector(`#node-${selectedNodeId} .wfb-node-title`);
            if (titleEl) titleEl.textContent = newTitle;
            wfbLog(`Renamed node to "${newTitle}". Reference it elsewhere as {${newTitle}}.`, "text-success-400");
        };
```

- [ ] **Step 3: Remove the now-redundant container-only rename UI**

In `renderContainerPanel` (lines 958-968), remove the "Container Name" label/input/"Save Name" button (the universal row above now covers it), leaving:

```javascript
        function renderContainerPanel(nodeId, data) {
            const body = document.getElementById("wfb-panel-body");
            body.innerHTML = `
                <button onclick="window.wfbEnterContainerFromPanel('${nodeId}')" class="w-full px-3 py-1.5 bg-surface-2 hover:bg-border border border-border-strong text-xs font-mono rounded text-heading transition-colors">Open Container <i class="fa-solid fa-up-right-and-down-left-from-center ml-1"></i></button>
                <p class="text-[10px] text-muted mt-3 leading-relaxed">Contains its own mini sub-flow. From the outside it connects like any other block; open it to build or edit what's inside.</p>
            `;
            body.dataset.readFn = "";
        }
```

In `wfbSaveNodePanel` (lines 1066-1078), remove the now-dead `container-name` branch:

```javascript
        window.wfbSaveNodePanel = function(nodeId) {
            const body = document.getElementById("wfb-panel-body");
            const readFn = body.dataset.readFn;

            let params = {};
```

(i.e. delete the `if (readFn === "container-name") { ... return; }` block that used to come right after `const readFn = body.dataset.readFn;`.)

- [ ] **Step 4: Manual verification**

Start the dev server the way this project normally runs it (check `00_System/server.py`'s `if __name__ == "__main__"` block or existing run instructions if unfamiliar), open the Workflow Builder page, and:
1. Drag any node onto the canvas, select it, confirm the "Node Name" row appears above its config panel pre-filled with its default title.
2. Rename it to `CG-File`, click Save, confirm the canvas label updates and the log shows the "Reference it elsewhere as {CG-File}" message.
3. Add a second node, try renaming it to `CG-File` too, confirm the alert blocks it.
4. Try renaming a node to `input`, confirm the reserved-word alert blocks it.
5. Open a Container node, confirm it still opens correctly and no longer shows its own separate "Container Name" field (just the universal one).

- [ ] **Step 5: Commit**

```bash
git add 00_System/templates/workflow-builder.html
git commit -m "$(cat <<'EOF'
Add a universal node-rename control with duplicate-name validation

Every node (not just containers) can now be renamed from one shared panel
control, doubling as its {token} name; renaming validates uniqueness and
blocks the reserved "input" name across the whole graph.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: UI — `{`-triggered token autocomplete

**Files:**
- Modify: `00_System/templates/workflow-builder.html`

**Interfaces:**
- Consumes: `allCanvasNodes(excludeNodeId)` from Task 2.

- [ ] **Step 1: Add the suggestion dropdown element**

Add a hidden, absolutely-positioned suggestion box to the panel markup, right after the `wfb-panel-body` div added/kept from Task 2 (still inside the same `w-80` panel `<div>`, so it can be positioned relative to it):

```html
        <div id="wfb-panel-body" class="flex-1 overflow-y-auto custom-scrollbar p-4 text-xs space-y-3">
            <div class="text-muted">Select a node on the canvas to configure it.</div>
        </div>
        <div id="wfb-token-suggest" class="hidden absolute z-50 bg-surface border border-border-strong rounded-lg shadow-lg max-h-48 overflow-y-auto custom-scrollbar text-xs"></div>
    </div>
```

- [ ] **Step 2: Wire one delegated listener for every current and future text/textarea field**

Add near the bottom of the file, right before the closing `document.getElementById("wfb-palette-search").addEventListener(...)` block (around line 1282), so it registers once when the page loads:

```javascript
        // One delegated listener covers every text/textarea field in the node
        // config panel, present and future, without each renderXPanel needing
        // its own autocomplete wiring.
        let tokenSuggestField = null;

        function closeTokenSuggest() {
            document.getElementById("wfb-token-suggest").classList.add("hidden");
            tokenSuggestField = null;
        }

        function openTokenSuggest(field) {
            const box = document.getElementById("wfb-token-suggest");
            const options = [{ id: "__input__", title: "input" }, ...allCanvasNodes(selectedNodeId)]
                .filter(n => n.title);

            if (!options.length) { closeTokenSuggest(); return; }

            box.innerHTML = options.map(n => `
                <div class="px-3 py-1.5 hover:bg-primary/15 cursor-pointer font-mono" data-token-name="${escapeHtml(n.title)}">{${escapeHtml(n.title)}}</div>
            `).join("");

            const fieldRect = field.getBoundingClientRect();
            const panelRect = field.closest("#wfb-panel-body").getBoundingClientRect();
            box.style.left = (fieldRect.left - panelRect.left) + "px";
            box.style.top = (fieldRect.bottom - panelRect.top) + "px";
            box.style.width = fieldRect.width + "px";
            box.classList.remove("hidden");
            tokenSuggestField = field;
        }

        document.getElementById("wfb-panel-body").addEventListener("input", (e) => {
            const field = e.target;
            if (!field.matches("textarea, input[type='text']")) return;
            const cursor = field.selectionStart;
            const justTyped = field.value[cursor - 1];
            if (justTyped === "{") {
                openTokenSuggest(field);
            } else {
                closeTokenSuggest();
            }
        });

        document.getElementById("wfb-token-suggest").addEventListener("mousedown", (e) => {
            const opt = e.target.closest("[data-token-name]");
            if (!opt || !tokenSuggestField) return;
            e.preventDefault(); // keep focus (and cursor position) in the field
            const field = tokenSuggestField;
            const cursor = field.selectionStart;
            const before = field.value.slice(0, cursor); // ends with the "{" that triggered this
            const after = field.value.slice(cursor);
            const insertion = opt.dataset.tokenName + "}";
            field.value = before + insertion + after;
            const newCursor = before.length + insertion.length;
            field.setSelectionRange(newCursor, newCursor);
            field.focus();
            closeTokenSuggest();
        });

        document.addEventListener("click", (e) => {
            if (!e.target.closest("#wfb-token-suggest") && e.target !== tokenSuggestField) closeTokenSuggest();
        });
```

- [ ] **Step 3: Manual verification**

With the dev server running and the Workflow Builder open:
1. Rename two nodes to `CG-File` and `TOS` (per Task 2).
2. Select a third node with a text or textarea field (e.g. a Concatenate node's Separator field), type `{` in it.
3. Confirm a dropdown appears listing `{input}`, `{CG-File}`, `{TOS}`.
4. Click `{TOS}`, confirm it's inserted at the cursor and the field regains focus with the cursor positioned right after the inserted `}`.
5. Click elsewhere on the page, confirm the dropdown closes.
6. Type `{` again and press Escape or click elsewhere without selecting — confirm no stray token gets inserted.

- [ ] **Step 4: Commit**

```bash
git add 00_System/templates/workflow-builder.html
git commit -m "$(cat <<'EOF'
Add {-triggered token autocomplete to workflow node config fields

One delegated listener on the panel body covers every text/textarea field,
present and future, suggesting {input} plus every other named node on the
canvas -- no per-field-type wiring needed.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
