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
#     using that node's own ID as the key. Any later node can pull in an
#     earlier node's output by writing a small placeholder like
#     `{{that_node_id}}` in one of its own settings -- `_substitute_tokens`
#     is what finds and replaces those placeholders with the real captured
#     text before a node actually runs.
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
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from core_router import CoreRouter

# Matches placeholder tokens like {{some_node_id}} anywhere inside a node's
# settings text, so they can be swapped out for that earlier node's real
# captured output before this node actually runs.
TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-]+)\s*\}\}")
MAX_TOTAL_STEPS = 200  # guards against runaway loops even when a gate's own max_attempts is misconfigured


class WorkflowRunError(Exception):
    # A dedicated error type for "something about this specific workflow
    # step failed" -- raising this (rather than a generic Python error)
    # lets the run loop below clearly distinguish "one step in the
    # workflow failed, log it and move on" from a genuine bug in this
    # engine itself.
    pass


class WorkflowEngine:
    """
    Walks a saved Workflow Builder graph (Drawflow export, see workflow_builder.html)
    and executes each node for real, threading captured text output from one node into
    the next via {{node_id}} token substitution. Tasks/Processes dispatch through the
    exact same CoreRouter.execute_app_logic used everywhere else in the app. Skills and
    AI-flavored built-ins dispatch through the existing copilot_bridge adapter (08_Adapters)
    -- the same mechanism templates/copilot.html already uses -- rather than a new AI
    integration. Cycles are allowed (a Review Gate can jump execution back to an earlier
    node); a per-gate max_attempts plus a global MAX_TOTAL_STEPS guarantee termination.
    """

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.router = CoreRouter()
        # Every node's captured text output, keyed by that node's ID -- this
        # is the shared "memory" that lets later nodes reference earlier
        # nodes' results via {{node_id}} tokens.
        self.context: Dict[str, str] = {}
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

    # --- Token substitution + upstream text gathering -----------------------------

    def _substitute_tokens(self, text: str) -> str:
        # Finds every {{node_id}} placeholder in a piece of text and
        # replaces it with that node's actual captured output so far
        # (or an empty string if that node hasn't run yet/produced
        # nothing) -- this is the actual mechanism that lets one step's
        # settings reference an earlier step's result.
        if not text:
            return text
        return TOKEN_PATTERN.sub(lambda m: self.context.get(m.group(1), ""), text)

    def _gather_upstream_text(self, node_id: str) -> str:
        # Collects the output of every node that feeds directly into this
        # one and joins them together (separated by a blank line) -- this
        # is the default "input" most node types receive automatically,
        # without the user needing to manually reference {{...}} tokens.
        parts = [self.context[p] for p in self.backward_edges.get(node_id, []) if p in self.context]
        return "\n\n".join(parts)

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

    def _extract_json_field(self, text: str, key: str) -> str:
        # Lets a node accept an upstream node's raw JSON output (e.g. a
        # Create Notebook node's {"notebook_id": ..., "title": ...}) and
        # pull out just one field, so later nodes can chain directly off it
        # without the user needing to hand-write a {{node_id}} token for
        # each field.
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            return ""
        return str(parsed.get(key, "")) if isinstance(parsed, dict) else ""

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

    def _run_logic_gate(self, params: Dict[str, Any], upstream_text: str) -> Tuple[str, Optional[str]]:
        # An "If/Else" style workflow node: checks the incoming text
        # against a condition (does it contain a certain word/phrase,
        # exactly equal a value, or match a regex pattern?) and reports
        # which of two possible next nodes execution should continue to,
        # based on whether the condition matched.
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

    # --- Built-in node handlers ---------------------------------------------------

    def _run_review_gate(self, node_id: str, params: Dict[str, Any], upstream_text: str) -> Tuple[str, Optional[str]]:
        # Asks an AI to judge the upstream text against a plain-English
        # pass/fail criteria (e.g. "does this summary mention all three key
        # decisions?"). If it fails and there's still an attempt remaining,
        # execution jumps backward to loop_back_node_id to try again
        # (e.g. re-run the step that generated the text); otherwise it lets
        # execution continue forward as normal.
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

    def _execute_node(self, node_id: str, node: Dict[str, Any]) -> Tuple[str, Optional[str]]:
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
        kind = node.get("kind")
        params = node.get("params") or {}
        upstream_text = self._gather_upstream_text(node_id)

        if kind in ("task", "process", "adapter") or (kind == "function" and node.get("category") == "09_Functions"):
            args = [self._substitute_tokens(str(a)) for a in (params.get("args") or [])]
            if self.dry_run:
                return f"[DRY RUN] Would execute {node['category']}/{node['tool_id']} with args {args}", None
            success, log_msg = self.router.execute_app_logic(node["category"], node["tool_id"], args)
            if not success:
                raise WorkflowRunError(log_msg[:600])
            return log_msg, None

        if kind == "skill":
            prompt = f"{node['title']}: {node.get('description', '')}\n\nInput:\n{upstream_text}"
            return self._ask_copilot(prompt), None

        if kind == "function":
            return self._execute_function_node(node_id, node, params, upstream_text)

        raise WorkflowRunError(f"Unknown node kind: {kind}")

    def _execute_function_node(self, node_id: str, node: Dict[str, Any], params: Dict[str, Any], upstream_text: str) -> Tuple[str, Optional[str]]:
        # A big if/elif ladder: given a function node's tool_id (which
        # specific "Function" block type it is, chosen in the Workflow
        # Builder UI), run the matching real logic. Grouped below by
        # category with a comment header for each group.
        tool_id = node.get("tool_id")

        if tool_id == "builtin_review_gate":
            return self._run_review_gate(node_id, params, upstream_text)

        # --- String / logic / data functions (no dependency, no credentials) ---
        if tool_id == "function_concatenate":
            separator = self._substitute_tokens(params.get("separator", "\n\n"))
            parts = [self.context[p] for p in self.backward_edges.get(node_id, []) if p in self.context]
            return separator.join(parts), None

        if tool_id == "function_logic_gate":
            return self._run_logic_gate(params, upstream_text)

        # --- Gemini-backed functions (adapters/gemini-bridge, uses a signed-in browser session, no API key) ---
        if tool_id == "function_google_search":
            instructions = self._substitute_tokens(params.get("instructions", ""))
            prompt = f"{instructions}\n\n{upstream_text}".strip() if instructions else upstream_text
            return self._ask_gemini(prompt, use_search=True), None
        if tool_id == "function_gemini_ask":
            instructions = self._substitute_tokens(params.get("instructions", ""))
            prompt = f"{instructions}\n\nInput:\n{upstream_text}" if instructions else upstream_text
            return self._ask_gemini(prompt), None

        # --- Claude-backed functions (adapters/claude-bridge, mock-mode until real API access exists) ---
        if tool_id == "function_claude_ask":
            instructions = self._substitute_tokens(params.get("instructions", ""))
            prompt = f"{instructions}\n\nInput:\n{upstream_text}" if instructions else upstream_text
            return self._ask_claude(prompt), None

        # --- ChatGPT-backed functions (adapters/chatgpt-bridge, mock-mode until real API access exists) ---
        if tool_id == "function_chatgpt_ask":
            instructions = self._substitute_tokens(params.get("instructions", ""))
            prompt = f"{instructions}\n\nInput:\n{upstream_text}" if instructions else upstream_text
            return self._ask_chatgpt(prompt), None

        if tool_id == "function_image_generate":
            prompt = self._substitute_tokens(params.get("prompt", "")) or upstream_text
            output_dir = params.get("output_dir") or str(self.router.base_dir / "02_vault" / "generated_images")
            return self._generate_image_gemini(prompt, output_dir), None

        # --- NotebookLM-backed functions (adapters/notebooklm-bridge, mock-mode until real API/MCP access exists) ---
        if tool_id == "function_notebooklm_create":
            title = self._substitute_tokens(params.get("title", "")) or "Untitled Notebook"
            return self._create_notebooklm_notebook(title), None

        if tool_id == "function_notebooklm_upload_sources":
            notebook_id = self._substitute_tokens(params.get("notebook_id", "")) or self._extract_json_field(upstream_text, "notebook_id")
            if not notebook_id:
                raise WorkflowRunError("Upload Sources requires a notebook_id (set one directly, or chain from a Create Notebook node).")
            raw_paths = self._substitute_tokens(params.get("file_paths", ""))
            file_paths = [p.strip() for p in raw_paths.splitlines() if p.strip()]
            if not file_paths:
                raise WorkflowRunError("Upload Sources requires at least one file path.")
            return self._upload_notebooklm_sources(notebook_id, file_paths), None

        if tool_id == "function_notebooklm_prompt_loop":
            notebook_id = self._substitute_tokens(params.get("notebook_id", "")) or self._extract_json_field(upstream_text, "notebook_id")
            if not notebook_id:
                raise WorkflowRunError("Prompt Loop requires a notebook_id (set one directly, or chain from a Create Notebook node).")
            raw_prompts = self._substitute_tokens(params.get("prompts", ""))
            prompts = [p.strip() for p in raw_prompts.splitlines() if p.strip()]
            if not prompts:
                raise WorkflowRunError("Prompt Loop requires at least one prompt.")
            return self._run_notebooklm_prompt_loop(notebook_id, prompts), None

        raise WorkflowRunError(f"Unknown function tool_id: {tool_id}")

    # --- Top-level run ---------------------------------------------------------------

    def run(self, graph_json: Dict[str, Any]) -> Dict[str, Any]:
        # This is the method everything above exists to support -- called
        # once per workflow run (see server.py's /api/workflow-builder/run
        # endpoint). It walks the graph starting from its entry node(s),
        # running one node at a time, in roughly the order the diagram's
        # arrows dictate, until there's nothing left queued up to run.
        nodes, forward_edges, backward_edges = self._parse_graph(graph_json)
        self.backward_edges = backward_edges

        if not nodes:
            return {"success": False, "steps": [], "error": "Workflow graph is empty."}

        entry_ids = self._find_entry_nodes(nodes, backward_edges) or [next(iter(nodes))]
        # `queue` is the to-do list of node IDs still waiting to run, in
        # order. Nodes normally get added to the END of the queue (run
        # after everything already waiting); a Review Gate's loop-back
        # jump instead gets inserted at the very FRONT, so it's picked up
        # immediately next, ahead of anything else already queued.
        queue: List[str] = list(entry_ids)

        while queue:
            if len(self.log) >= MAX_TOTAL_STEPS:
                self.log.append({
                    "node_id": None, "title": "Safety Stop", "kind": "system",
                    "status": "failed", "output": "Exceeded maximum step count; stopping to avoid a runaway loop.",
                })
                break

            node_id = queue.pop(0)
            node = nodes.get(node_id)
            if node is None:
                continue

            try:
                output_text, jump_to = self._execute_node(node_id, node)
                self.context[node_id] = output_text
                self.log.append({
                    "node_id": node_id, "title": node["title"], "kind": node["kind"],
                    "status": "success", "output": (output_text or "")[:600],
                })
            except Exception as e:
                self.log.append({
                    "node_id": node_id, "title": node.get("title", node_id), "kind": node.get("kind"),
                    "status": "failed", "output": str(e),
                })
                continue  # do not follow this node's outgoing edges on failure

            if jump_to:
                # A Review Gate (or similar) decided to loop back to an
                # earlier node instead of continuing forward normally.
                queue.insert(0, jump_to)
            else:
                # Normal case: queue up whatever node(s) this one's output
                # arrows point to next.
                queue.extend(forward_edges.get(node_id, []))

        overall_success = bool(self.log) and all(s["status"] == "success" for s in self.log)
        return {"success": overall_success, "steps": self.log}
