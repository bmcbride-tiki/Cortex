# =============================================================================
# workflow_engine.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   This is the engine that actually RUNS the visual workflows built in the
#   Cortex web app's drag-and-drop "Workflow Builder" page. In that page, a
#   user connects a series of boxes ("nodes") together with lines -- e.g.
#   "read this file" -> "ask an AI to summarize it" -> "save the summary
#   as a Word document." This file is what takes that saved diagram and
#   actually carries it out step by step, running each box's real action in
#   the right order and passing each step's output along to whichever
#   box(es) come next.
#
#   If you think of the Workflow Builder page as drawing a flowchart, this
#   file is the thing that walks that flowchart and does what it says.
#
# WHAT IT INTERACTS WITH
#   - `core_router.py`'s `CoreRouter`, used to actually launch Task/Process
#     scripts and the AI bridge adapters (Gemini/Copilot), the same way the
#     rest of Cortex does.
#   - `adapters/copilot-bridge/copilot_bridge.py`,
#     `adapters/gemini-bridge/gemini_bridge.py`, and
#     `adapters/notebooklm-bridge/notebooklm_bridge.py` (mock-mode until real
#     API/MCP access exists), for every workflow node that involves asking an
#     AI something, generating an image, chatting with a specific Copilot
#     agent, or running a NotebookLM notebook.
#   - The `docx` (Word documents), `fpdf` (PDF documents), and `pypdf`
#     (reading PDFs) libraries, for workflow nodes that export or import
#     files in those formats.
#   - `requests` and `lxml`, for the "Web Scrape" node, which fetches a web
#     page and pulls out its readable text.
#   - The saved workflow diagram itself, which arrives as a "Drawflow"
#     export -- Drawflow is the JavaScript library the Workflow Builder
#     page uses to draw the boxes and connecting lines on screen; what it
#     saves is a structured description of every box and every line, which
#     is what `graph_json` (see `run()` near the bottom) actually is.
#
# KEY FUNCTIONALITY NOTES
#   - Nodes and edges: this file thinks of the whole workflow as a "graph"
#     -- a technical term for a collection of "nodes" (the boxes) connected
#     by "edges" (the lines/arrows between them). "Forward edges" trace
#     which node(s) come after a given node; "backward edges" trace which
#     node(s) came before it. Both directions are tracked because some
#     nodes need to look backward (e.g. "combine everything that fed into
#     me") and the overall run loop needs to look forward (e.g. "what runs
#     next").
#   - Passing data between boxes: whatever text a node produces gets stored
#     using that node's human-readable output LABEL as the key (each box has
#     one, editable in the builder's right-hand panel). A node can pull in an
#     earlier node's output by writing a small placeholder like `{{that_label}}`
#     in one of its own settings -- `_substitute_tokens` is what finds and
#     replaces those placeholders with the real captured text before a node
#     actually runs. Only labels belonging to boxes wired DIRECTLY into this
#     one can be referenced; anything else is a hard error, not a silent blank.
#   - "Containers" are the Workflow Builder's way of letting you group a
#     cluster of boxes into one collapsible sub-diagram (like a folder full
#     of steps that displays as a single box on the main canvas). Before
#     running anything, this file "flattens" every container out of the
#     graph -- rewiring the connections so the steps that were inside it
#     get spliced directly into the main flow -- so the rest of this file
#     never has to treat a container any differently from a normal step.
#   - Loops are allowed: a "Review Gate" style node can decide the work
#     done so far didn't pass some check, and jump execution backward to
#     an earlier node to try again (e.g. "ask the AI to redo this until it
#     meets my criteria"). To stop that from looping forever if something
#     is misconfigured, each individual gate has its own attempt limit AND
#     there's a hard overall cap (`MAX_TOTAL_STEPS`) on the total number of
#     steps any single workflow run is allowed to take.
#   - "Dry run" mode (the default, `dry_run=True`) lets a workflow be
#     validated/tested WITHOUT actually calling any AI, downloading
#     anything, or writing real files -- every action instead returns a
#     clearly labeled "[DRY RUN] ..." placeholder describing what it WOULD
#     have done. This is what lets someone test a workflow's wiring/logic
#     safely and instantly before running it for real (`dry_run=False`),
#     which can be slow and has real side effects (real AI calls, real
#     files written to disk).
# =============================================================================

# 00_System/workflow_engine.py
import sys
sys.dont_write_bytecode = True

import re
import ast
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union

import requests

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from core_router import CoreRouter

# Matches placeholder tokens like {{some_label}} anywhere inside a node's
# settings text, so they can be swapped out for that earlier node's real
# captured output before this node actually runs. The allowed character set
# here is what workflow-builder.html's wfbSaveLabel enforces on labels.
TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-]+)\s*\}\}")
MAX_TOTAL_STEPS = 200  # guards against runaway loops even when a gate's own max_attempts is misconfigured


class WorkflowRunError(Exception):
    # A dedicated error type for "something about this specific workflow
    # step failed" -- raising this (rather than a generic Python error)
    # lets the run loop below clearly distinguish "one step in the
    # workflow failed, log it and move on" from a genuine bug in this
    # engine itself.
    pass


class MissingInputError(WorkflowRunError):
    # Raised when a {{label}} reference can't be resolved -- either the
    # label doesn't exist anywhere in the graph, or it exists but isn't on
    # a node directly wired into the one currently executing. Unlike a
    # generic WorkflowRunError, callers can catch this one specifically if
    # they ever need to distinguish "bad wiring" from other failure modes.
    pass


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
        is_and = isinstance(node.op, ast.And)
        result = is_and
        for v in node.values:
            result = bool(_eval_condition_ast(v, namespace))
            if is_and and not result:
                return False
            if not is_and and result:
                return True
        return result
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
    try:
        return bool(_eval_condition_ast(tree, namespace))
    except TypeError as e:
        raise WorkflowRunError(f"Invalid comparison in condition expression: {e}")


class WorkflowEngine:
    """
    Walks a saved Workflow Builder graph (Drawflow export, see workflow_builder.html)
    and executes each node for real, threading captured text output from one node into
    the next via {{label}} token substitution, scoped to direct connections only (an
    unresolvable label raises MissingInputError rather than resolving to a blank).
    A node waits until every one of its direct predecessors has run. Tasks/Processes dispatch through the
    exact same CoreRouter.execute_app_logic used everywhere else in the app. Skills and
    AI-flavored built-ins dispatch through the existing copilot_bridge adapter (08_Adapters)
    -- the same mechanism templates/copilot.html already uses -- rather than a new AI
    integration. Cycles are allowed (a Review Gate can jump execution back to an earlier
    node); a per-gate max_attempts plus a global MAX_TOTAL_STEPS guarantee termination.
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.router = CoreRouter()
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
        # Labels of ALL direct predecessors of the currently-executing node,
        # including any that haven't produced output -- lets _substitute_tokens
        # tell "not connected" apart from "connected but empty".
        self._current_pred_labels: set = set()
        # How many times each Review-Gate-style node has been attempted so
        # far, keyed by that node's ID -- used to enforce each gate's own
        # max_attempts limit.
        self.gate_attempts: Dict[str, int] = {}
        self.backward_edges: Dict[str, List[str]] = {}
        # A running, step-by-step log of everything that happened during
        # this run (what node, whether it succeeded, what it output) --
        # this is what gets shown back to the user afterward as the
        # workflow's execution report.
        self.log: List[Dict[str, Any]] = []

    # --- Graph parsing -----------------------------------------------------------

    def _parse_graph(self, graph_json: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, List[str]], Dict[str, List[str]]]:
        """Parses every Drawflow module (Home + one per Container node) into one flat
        node/edge map -- Drawflow node ids are globally unique across modules, and
        connections never cross modules, so this is safe. Container nodes are then
        spliced out via _flatten_containers so run()'s single-pass walk transparently
        handles nested sub-flows with no recursive execution needed.
        """
        # A Drawflow export is organized into "modules" -- one for the main
        # canvas ("Home") and one more for each Container box's own
        # internal sub-diagram. This function reads all of them and merges
        # everything into one single, flat map of nodes and connections,
        # so the rest of this file doesn't need to care which module a
        # node originally came from.
        drawflow = (graph_json or {}).get("drawflow", {})

        nodes: Dict[str, Any] = {}
        forward_edges: Dict[str, List[str]] = {}
        backward_edges: Dict[str, List[str]] = {}
        module_nodes: Dict[str, List[str]] = {}

        for module_name, module_data in drawflow.items():
            raw_nodes = (module_data or {}).get("data", {}) or {}
            module_nodes[module_name] = [str(nid) for nid in raw_nodes.keys()]

            for node_id, raw in raw_nodes.items():
                node_id = str(node_id)
                data = raw.get("data") or {}
                nodes[node_id] = {
                    "kind": data.get("kind"),
                    "tool_id": data.get("tool_id"),
                    "category": data.get("category"),
                    "title": data.get("title") or raw.get("name") or node_id,
                    "label": data.get("label") or node_id,
                    "params": data.get("params") or {},
                    "module_name": data.get("module_name"),
                }
                forward_edges.setdefault(node_id, [])
                backward_edges.setdefault(node_id, [])

            for node_id, raw in raw_nodes.items():
                node_id = str(node_id)
                for output_val in (raw.get("outputs") or {}).values():
                    for conn in output_val.get("connections", []):
                        target = str(conn.get("node"))
                        if target in nodes:
                            forward_edges[node_id].append(target)
                            backward_edges[target].append(node_id)

        self._flatten_containers(nodes, forward_edges, backward_edges, module_nodes)
        return nodes, forward_edges, backward_edges

    def _flatten_containers(
        self,
        nodes: Dict[str, Any],
        forward_edges: Dict[str, List[str]],
        backward_edges: Dict[str, List[str]],
        module_nodes: Dict[str, List[str]],
    ) -> None:
        """Splices every container node out of the flat graph in place, rewiring its
        module's own entry/exit nodes directly to its former predecessors/successors.
        Repeats until no container nodes remain, so containers nested inside containers
        resolve too."""
        # A "container" node on the main canvas is really just a visual
        # stand-in for a whole separate mini-diagram of its own steps. This
        # function removes that stand-in box entirely and rewires the
        # connections so whatever used to point INTO the container now
        # points to the first real step inside it, and whatever used to
        # come OUT of the container now comes from the last real step
        # inside it -- as if the container had never existed and its
        # inner steps had been drawn directly on the main canvas all along.
        while True:
            container_ids = [nid for nid, n in nodes.items() if n.get("kind") == "container"]
            if not container_ids:
                break

            for cid in container_ids:
                module_name = nodes[cid].get("module_name")
                inner_ids = module_nodes.get(module_name, [])
                preds = list(backward_edges.get(cid, []))
                succs = list(forward_edges.get(cid, []))

                if inner_ids:
                    # The "entry" node(s) of the sub-diagram are whichever inner
                    # nodes have nothing feeding into them; "exit" node(s) are
                    # whichever have nothing coming out of them.
                    entry_ids = [nid for nid in inner_ids if not backward_edges.get(nid)] or [inner_ids[0]]
                    exit_ids = [nid for nid in inner_ids if not forward_edges.get(nid)] or [inner_ids[-1]]
                else:
                    entry_ids, exit_ids = [], []

                if not entry_ids or not exit_ids:
                    # Empty (or entry/exit-less) container: bypass it directly.
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

    def _find_entry_nodes(self, nodes: Dict[str, Any], backward_edges: Dict[str, List[str]]) -> List[str]:
        # The "starting point(s)" of the workflow: any node that has
        # nothing feeding into it is assumed to be a place execution can
        # begin.
        return [n for n in nodes if not backward_edges.get(n)]

    def _build_scope(self, node_id: str) -> Dict[str, str]:
        # Only labels belonging to nodes with a DIRECT edge into node_id are
        # visible to it -- this is what makes {{label}} a connection, not a
        # graph-wide lookup. run() now holds a node back until every one of its
        # predecessors has finished, so the only way a predecessor's label is
        # missing from self.context is that it failed -- leave it out of scope
        # rather than crashing here, and let _substitute_tokens report it.
        scope: Dict[str, str] = {}
        self._current_pred_labels = set()
        for pred_id in self.backward_edges.get(node_id, []):
            label = self.node_labels.get(pred_id)
            if not label:
                continue
            self._current_pred_labels.add(label)
            if label in self.context:
                scope[label] = self.context[label]
        return scope

    # --- Token substitution + upstream text gathering -----------------------------

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

        return TOKEN_PATTERN.sub(replace, text)

    def _direct_predecessor_texts(self, node_id: str) -> List[str]:
        # Every direct predecessor's captured output, in edge order -- the
        # raw material both _gather_upstream_text (whole-text join) and the
        # Concatenate function (custom-separator join) build on.
        return [
            self.context[self.node_labels[p]]
            for p in self.backward_edges.get(node_id, [])
            if self.node_labels.get(p) in self.context
        ]

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

    def _gather_upstream_text(self, node_id: str) -> str:
        # Used only by node types whose entire defined behavior IS "operate
        # on whatever's directly connected" -- Skill nodes, Logic Gate, and
        # Review Gate -- which have no settings field to explicitly bind a
        # {{label}} into instead.
        return "\n\n".join(self._direct_predecessor_texts(node_id))

    # --- AI bridge (reuses adapters/copilot-bridge via the existing 05_Processes route) --

    @staticmethod
    def _parse_bridge_json(log_msg: str, bridge_name: str) -> dict:
        """Bridge scripts (copilot_bridge.py / gemini_bridge.py) always print exactly one
        JSON line. execute_app_logic's captured output can have other lines before or
        after it (status prints, stderr logs appended by the router), so pick out that
        one line specifically rather than assuming everything from the first match to
        the end of the string is valid JSON."""
        json_line = next(
            (line for line in log_msg.splitlines() if line.strip().startswith('{"success"')),
            None,
        )
        if json_line is None:
            raise WorkflowRunError(f"Could not parse {bridge_name} response: {log_msg[:400]}")
        try:
            return json.loads(json_line.strip())
        except ValueError as e:
            raise WorkflowRunError(f"Malformed {bridge_name} JSON: {e}")

    def _ask_copilot(self, prompt_text: str) -> str:
        # Sends prompt_text to Microsoft 365 Copilot via copilot_bridge.py's
        # "ask" action and returns its plain-text answer. In dry_run mode,
        # nothing is actually sent -- a placeholder describing what would
        # have been asked is returned instead.
        if self.dry_run:
            return f"[DRY RUN] Simulated Copilot response for prompt:\n{prompt_text[:400]}"

        payload = json.dumps({"action": "ask", "prompt": prompt_text, "headless": True})
        success, log_msg = self.router.execute_app_logic("08_Adapters", "copilot_bridge", [payload])
        if not success:
            raise WorkflowRunError(f"copilot_bridge call failed: {log_msg[:400]}")
        return self._parse_bridge_json(log_msg, "copilot_bridge").get("response", "")

    def _ask_gemini(self, prompt_text: str, use_search: bool = False) -> str:
        # Sends prompt_text to Google Gemini via gemini_bridge.py.
        # use_search=True runs it as a full "Deep Research" multi-step pass
        # instead of a normal single-turn answer.
        if self.dry_run:
            mode = "search-grounded " if use_search else ""
            return f"[DRY RUN] Simulated {mode}Gemini response for prompt:\n{prompt_text[:400]}"

        payload = json.dumps({"action": "search" if use_search else "ask", "prompt": prompt_text})
        success, log_msg = self.router.execute_app_logic("08_Adapters", "gemini_bridge", [payload])
        if not success:
            raise WorkflowRunError(f"gemini_bridge call failed: {log_msg[:400]}")
        return self._parse_bridge_json(log_msg, "gemini_bridge").get("response", "")

    def _ask_claude(self, prompt_text: str) -> str:
        # Sends prompt_text to Anthropic Claude via claude_bridge.py (mock-mode until a real API key exists).
        if self.dry_run:
            return f"[DRY RUN] Simulated Claude response for prompt:\n{prompt_text[:400]}"

        payload = json.dumps({"action": "ask", "prompt": prompt_text})
        success, log_msg = self.router.execute_app_logic("08_Adapters", "claude_bridge", [payload])
        if not success:
            raise WorkflowRunError(f"claude_bridge call failed: {log_msg[:400]}")
        return self._parse_bridge_json(log_msg, "claude_bridge").get("response", "")

    def _ask_chatgpt(self, prompt_text: str) -> str:
        # Sends prompt_text to OpenAI ChatGPT via chatgpt_bridge.py (mock-mode until a real API key exists).
        if self.dry_run:
            return f"[DRY RUN] Simulated ChatGPT response for prompt:\n{prompt_text[:400]}"

        payload = json.dumps({"action": "ask", "prompt": prompt_text})
        success, log_msg = self.router.execute_app_logic("08_Adapters", "chatgpt_bridge", [payload])
        if not success:
            raise WorkflowRunError(f"chatgpt_bridge call failed: {log_msg[:400]}")
        return self._parse_bridge_json(log_msg, "chatgpt_bridge").get("response", "")

    def _generate_image_gemini(self, prompt_text: str, output_dir: str) -> str:
        # Same idea as _generate_image_copilot, but via Gemini's own image
        # generation instead of Copilot's Designer feature.
        if self.dry_run:
            return f"[DRY RUN] Would generate an image into {output_dir} for prompt:\n{prompt_text[:200]}"

        payload = json.dumps({"action": "generate_image", "prompt": prompt_text, "output_dir": output_dir})
        success, log_msg = self.router.execute_app_logic("08_Adapters", "gemini_bridge", [payload])
        if not success:
            raise WorkflowRunError(f"gemini_bridge call failed: {log_msg[:400]}")
        return self._parse_bridge_json(log_msg, "gemini_bridge").get("file_path", "")

    # --- NotebookLM (notebooklm_bridge, mock-mode until real API/MCP access exists) ---

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

    def _create_notebooklm_notebook(self, title: str) -> str:
        if self.dry_run:
            return f"[DRY RUN] Would create a NotebookLM notebook titled:\n{title[:200]}"

        payload = json.dumps({"action": "create_notebook", "title": title})
        success, log_msg = self.router.execute_app_logic("08_Adapters", "notebooklm_bridge", [payload])
        if not success:
            raise WorkflowRunError(f"notebooklm_bridge call failed: {log_msg[:400]}")
        result = self._parse_bridge_json(log_msg, "notebooklm_bridge")
        return json.dumps({"notebook_id": result.get("notebook_id", ""), "title": result.get("title", "")})

    def _upload_notebooklm_sources(self, notebook_id: str, file_paths: List[str]) -> str:
        if self.dry_run:
            return f"[DRY RUN] Would upload {len(file_paths)} source(s) to notebook {notebook_id}:\n" + "\n".join(file_paths)

        payload = json.dumps({"action": "upload_sources", "notebook_id": notebook_id, "file_paths": file_paths})
        success, log_msg = self.router.execute_app_logic("08_Adapters", "notebooklm_bridge", [payload])
        if not success:
            raise WorkflowRunError(f"notebooklm_bridge call failed: {log_msg[:400]}")
        result = self._parse_bridge_json(log_msg, "notebooklm_bridge")
        return json.dumps({"notebook_id": notebook_id, "sources": result.get("sources", [])})

    def _run_notebooklm_prompt_loop(self, notebook_id: str, prompts: List[str]) -> str:
        if self.dry_run:
            return f"[DRY RUN] Would ask notebook {notebook_id} {len(prompts)} prompt(s):\n" + "\n".join(prompts)

        payload = json.dumps({"action": "prompt_loop", "notebook_id": notebook_id, "prompts": prompts})
        success, log_msg = self.router.execute_app_logic("08_Adapters", "notebooklm_bridge", [payload])
        if not success:
            raise WorkflowRunError(f"notebooklm_bridge call failed: {log_msg[:400]}")
        result = self._parse_bridge_json(log_msg, "notebooklm_bridge")
        return json.dumps(result.get("qa_pairs", []), indent=2)

    # --- Logic / data function handlers --------------------------------------------

    def _run_logic_gate(self, node_id: str, params: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        # An "If/Else" style workflow node: checks the incoming text
        # against a condition (does it contain a certain word/phrase,
        # exactly equal a value, or match a regex pattern?) and reports
        # which of two possible next nodes execution should continue to,
        # based on whether the condition matched.
        upstream_text = self._gather_upstream_text(node_id)
        condition_type = params.get("condition_type", "contains")
        condition_value = self._substitute_tokens(params.get("condition_value", ""))
        true_node = params.get("true_node_id") or None
        false_node = params.get("false_node_id") or None

        if condition_type == "regex":
            matched = bool(re.search(condition_value, upstream_text))
        elif condition_type == "equals":
            matched = upstream_text.strip() == condition_value.strip()
        else:
            matched = condition_value in upstream_text

        target = true_node if matched else false_node
        verdict = f"Condition {'matched' if matched else 'did not match'} ({condition_type}: {condition_value!r})"
        return verdict, target

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

    # --- Built-in node handlers ---------------------------------------------------

    def _run_review_gate(self, node_id: str, params: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        # Asks an AI to judge the upstream text against a plain-English
        # pass/fail criteria (e.g. "does this summary mention all three key
        # decisions?"). If it fails and there's still an attempt remaining,
        # execution jumps backward to loop_back_node_id to try again
        # (e.g. re-run the step that generated the text); otherwise it lets
        # execution continue forward as normal.
        upstream_text = self._gather_upstream_text(node_id)
        criteria = params.get("criteria", "")
        loop_back = params.get("loop_back_node_id")
        max_attempts = int(params.get("max_attempts") or 3)
        attempts = self.gate_attempts.get(node_id, 0) + 1
        self.gate_attempts[node_id] = attempts

        if self.dry_run:
            # Deterministic simulation: fail until the final allowed attempt, then pass --
            # this is what exercises the loop-back path during verification without a live call.
            passed = attempts >= max_attempts
            verdict_text = f"[DRY RUN] Simulated verdict (attempt {attempts}/{max_attempts}): {'PASS' if passed else 'FAIL'}"
        else:
            prompt = (
                f"Judge the following text against this criteria: {criteria}\n"
                f"Reply with the single word PASS or FAIL as the first word of your response.\n\nText:\n{upstream_text}"
            )
            verdict_text = self._ask_copilot(prompt)
            passed = verdict_text.strip().upper().startswith("PASS")

        if not passed and loop_back and attempts < max_attempts:
            return verdict_text, loop_back
        return verdict_text, None

    # --- Per-node dispatch ---------------------------------------------------------

    def _execute_node(self, node_id: str, node: Dict[str, Any]) -> Tuple[str, Optional[Union[str, List[str]]]]:
        # The main "what kind of box is this, and what does running it
        # actually mean?" dispatcher, called once per node during the
        # run loop at the bottom of this file. Every node falls into one
        # of four broad kinds:
        #   - "task"/"process"/"adapter": run an existing automation script
        #     (or AI bridge adapter) via the router
        #   - "skill": ask Copilot to act as a described persona/skill
        #   - "function": either a real script from 13_Functions
        #     (category == "09_Functions", dispatched exactly like
        #     task/process/adapter above) or one of the many built-in
        #     operations handled by _execute_function_node below (string
        #     ops, file export/import, AI calls, web scraping, etc.)
        self._current_scope = self._build_scope(node_id)
        kind = node.get("kind")
        params = node.get("params") or {}

        if kind in ("task", "process", "adapter") or (kind == "function" and node.get("category") == "09_Functions"):
            args = [self._substitute_tokens(str(a)) for a in (params.get("args") or [])]
            if self.dry_run:
                return f"[DRY RUN] Would execute {node['category']}/{node['tool_id']} with args {args}", None
            success, log_msg = self.router.execute_app_logic(node["category"], node["tool_id"], args)
            if not success:
                raise WorkflowRunError(log_msg[:600])
            return log_msg, None

        if kind == "skill":
            upstream_text = self._gather_upstream_text(node_id)
            prompt = f"{node['title']}: {node.get('description', '')}\n\nInput:\n{upstream_text}"
            return self._ask_copilot(prompt), None

        if kind == "function":
            return self._execute_function_node(node_id, node, params)

        raise WorkflowRunError(f"Unknown node kind: {kind}")

    def _execute_function_node(self, node_id: str, node: Dict[str, Any], params: Dict[str, Any]) -> Tuple[str, Optional[Union[str, List[str]]]]:
        # A big if/elif ladder: given a function node's tool_id (which
        # specific "Function" block type it is, chosen in the Workflow
        # Builder UI), run the matching real logic. Grouped below by
        # category with a comment header for each group.
        tool_id = node.get("tool_id")

        if tool_id == "builtin_review_gate":
            return self._run_review_gate(node_id, params)

        # --- String / logic / data functions (no dependency, no credentials) ---
        if tool_id == "function_concatenate":
            separator = self._substitute_tokens(params.get("separator", "\n\n"))
            return separator.join(self._direct_predecessor_texts(node_id)), None

        if tool_id == "function_logic_gate":
            return self._run_logic_gate(node_id, params)

        if tool_id == "function_conditions":
            return self._run_conditions(node_id, params)

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

        # --- Prompt-driven AI functions (Gemini / Claude / ChatGPT / image gen) ---
        # There's no implicit "whatever flowed in" fallback any more, so an empty
        # prompt means the node is misconfigured -- fail loudly instead of firing
        # an empty request at the model.
        AI_PROMPT_NODES = {
            "function_google_search": ("Google Search", "instructions"),
            "function_gemini_ask": ("Gemini Ask", "instructions"),
            "function_claude_ask": ("Claude Ask", "instructions"),
            "function_chatgpt_ask": ("ChatGPT Ask", "instructions"),
            "function_image_generate": ("Image Generate", "prompt"),
        }
        if tool_id in AI_PROMPT_NODES:
            friendly_name, field = AI_PROMPT_NODES[tool_id]
            prompt = self._substitute_tokens(params.get(field, ""))
            if not prompt.strip():
                raise WorkflowRunError(
                    f"{friendly_name} requires {field} -- bind {{{{label}}}} or type a prompt directly."
                )
            if tool_id == "function_image_generate":
                output_dir = params.get("output_dir") or str(self.router.base_dir / "02_vault" / "generated_images")
                return self._generate_image_gemini(prompt, output_dir), None
            if tool_id == "function_claude_ask":
                return self._ask_claude(prompt), None
            if tool_id == "function_chatgpt_ask":
                return self._ask_chatgpt(prompt), None
            return self._ask_gemini(prompt, use_search=(tool_id == "function_google_search")), None

        # --- NotebookLM-backed functions (adapters/notebooklm-bridge, mock-mode until real API/MCP access exists) ---
        if tool_id == "function_notebooklm_create":
            title = self._substitute_tokens(params.get("title", "")) or "Untitled Notebook"
            return self._create_notebooklm_notebook(title), None

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

        raise WorkflowRunError(f"Unknown function tool_id: {tool_id}")

    # --- Run-loop scheduling ---------------------------------------------------------

    @staticmethod
    def _pick_next(
        queue: List[str],
        forward_edges: Dict[str, List[str]],
        backward_edges: Dict[str, List[str]],
        finished: set,
    ) -> str:
        """Which queued node to run next. Normally the first one whose direct
        predecessors have ALL finished -- running a node before everything feeding
        it has produced output is what made a join node fail on a token that was
        only moments away, then run a second time once it arrived.

        When nothing is runnable, something has to be forced or the run stalls.
        The node to force is one whose unfinished predecessors can never run --
        i.e. aren't reachable from anything still queued. That's a dead branch a
        Logic Gate never took. Picking the queue's head instead would force a node
        whose blocker IS still coming, re-creating the exact double-execution bug
        (silently, if that node's params happen not to reference the missing
        label -- a duplicated live AI call or file write with nothing to show it).
        """
        for nid in queue:
            if all(p in finished for p in backward_edges.get(nid, [])):
                return nid

        # Everything still reachable from a queued node may yet run, so it doesn't
        # count as a dead blocker.
        pending = set(queue)
        stack = list(queue)
        while stack:
            for nxt in forward_edges.get(stack.pop(), []):
                if nxt not in pending:
                    pending.add(nxt)
                    stack.append(nxt)

        for nid in queue:
            if all(p in finished or p not in pending for p in backward_edges.get(nid, [])):
                return nid

        # ponytail: every queued node is blocked by something still pending, which
        # only happens in a real cycle that no Review Gate jump breaks. Force the
        # head to guarantee progress -- that node may run more than once before
        # MAX_TOTAL_STEPS halts the run. Upgrade path: reject cyclic graphs (that
        # aren't gate loop-backs) up front, at save time, instead of at run time.
        return queue[0]

    # --- Top-level run ---------------------------------------------------------------

    def run(self, graph_json: Dict[str, Any]) -> Dict[str, Any]:
        # This is the method everything above exists to support -- called
        # once per workflow run (see server.py's /api/workflow-builder/run
        # endpoint). It walks the graph starting from its entry node(s),
        # running one node at a time, in roughly the order the diagram's
        # arrows dictate, until there's nothing left queued up to run.
        nodes, forward_edges, backward_edges = self._parse_graph(graph_json)
        self.backward_edges = backward_edges
        self.node_labels = {nid: (n.get("label") or nid) for nid, n in nodes.items()}

        if not nodes:
            return {"success": False, "steps": [], "error": "Workflow graph is empty."}

        entry_ids = self._find_entry_nodes(nodes, backward_edges) or [next(iter(nodes))]
        # `queue` is the to-do list of node IDs still waiting to run, in
        # order. Nodes normally get added to the END of the queue (run
        # after everything already waiting); a Review Gate's loop-back
        # jump instead gets inserted at the very FRONT, so it's picked up
        # immediately next, ahead of anything else already queued.
        queue: List[str] = list(entry_ids)
        # Every node that has finished running (succeeded OR failed). A node is
        # only allowed to run once ALL of its direct predecessors are in here --
        # without that, a diamond (A->B->C->D plus a direct A->D) would pop D via
        # the short A->D edge before C had produced anything, fail it on {{C}},
        # then run it a second time via C->D.
        finished: set = set()

        while queue:
            if len(self.log) >= MAX_TOTAL_STEPS:
                self.log.append({
                    "node_id": None, "title": "Safety Stop", "kind": "system",
                    "status": "failed", "output": "Exceeded maximum step count; stopping to avoid a runaway loop.",
                })
                break

            node_id = self._pick_next(queue, forward_edges, backward_edges, finished)
            queue.remove(node_id)
            node = nodes.get(node_id)
            if node is None:
                continue

            try:
                output_text, jump_to = self._execute_node(node_id, node)
                label = self.node_labels.get(node_id, node_id)
                self.context[label] = output_text
                self.log.append({
                    "node_id": node_id, "title": node["title"], "kind": node["kind"],
                    "status": "success", "output": (output_text or "")[:600],
                })
            except Exception as e:
                self.log.append({
                    "node_id": node_id, "title": node.get("title", node_id), "kind": node.get("kind"),
                    "status": "failed", "output": str(e),
                })
                # Marked finished even though it failed, so nodes waiting on it
                # aren't blocked forever -- they'll fail on the missing token.
                finished.add(node_id)
                continue  # do not follow this node's outgoing edges on failure

            finished.add(node_id)
            if jump_to:
                # A Review Gate (or similar) decided to loop back to an
                # earlier node instead of continuing forward normally. A
                # Conditions node in all_matches mode returns a LIST of
                # target ids instead of one -- queue every one of them at
                # the front, in order, same as a single jump_to would be.
                if isinstance(jump_to, list):
                    # Insert in reverse so the resulting queue order matches
                    # the original list order (each insert(0, t) puts t at
                    # the very front) -- and skip anything already queued,
                    # same guard as the forward-edges path below, so two
                    # condition rows targeting the same node don't run it twice.
                    for t in reversed(jump_to):
                        if t not in queue:
                            queue.insert(0, t)
                else:
                    queue.insert(0, jump_to)
            else:
                # Normal case: queue up whatever node(s) this one's output
                # arrows point to next -- skipping any already waiting in the
                # queue, so a node fed by two paths is only ever run once.
                queue.extend(t for t in forward_edges.get(node_id, []) if t not in queue)

        overall_success = bool(self.log) and all(s["status"] == "success" for s in self.log)
        return {"success": overall_success, "steps": self.log}
