# 00_System/tests/test_workflow_engine_tokens.py
"""Assert-based smoke tests for WorkflowEngine's named-label token substitution.
Run directly: python test_workflow_engine_tokens.py
"""
import sys
sys.dont_write_bytecode = True

from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parents[1]
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


def test_blank_ai_prompt_fails_instead_of_sending_nothing():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Up", "function_gemini_ask", {"instructions": "AAA"}, ["2"]),
        ("2", "Blank", "function_gemini_ask", {"instructions": "   "}, []),
    ])
    result = engine.run(graph)
    step = next(s for s in result["steps"] if s["node_id"] == "2")
    assert step["status"] == "failed", step
    assert "requires instructions" in step["output"], step


def test_diamond_join_waits_for_all_predecessors():
    """A -> B -> C -> D plus a direct A -> D edge. D must run exactly once, after
    BOTH A and C have produced output -- a plain BFS pops D as soon as the A -> D
    edge is followed, fails it on {{C}}, then re-queues and re-runs it via C -> D."""
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "A", "function_gemini_ask", {"instructions": "AAA"}, ["2", "4"]),
        ("2", "B", "function_gemini_ask", {"instructions": "BBB"}, ["3"]),
        ("3", "C", "function_gemini_ask", {"instructions": "CCC"}, ["4"]),
        ("4", "D", "function_gemini_ask", {"instructions": "{{A}} ++ {{C}}"}, []),
    ])
    result = engine.run(graph)
    d_steps = [s for s in result["steps"] if s["node_id"] == "4"]
    assert len(d_steps) == 1, f"D ran {len(d_steps)} time(s): {d_steps}"
    assert result["success"], result
    assert "AAA" in d_steps[0]["output"] and "CCC" in d_steps[0]["output"], d_steps


def test_logic_gate_join_does_not_double_execute():
    """Gate -> A (taken) / B (never taken); A -> J, A -> C, B -> C, C -> J.
    At the stall point the queue is [J, C]: J is blocked on C, which IS queued and
    will run; C is blocked on B, which never will. Forcing the queue's head picks
    J -- too early -- so J fails on {{C}} and then runs again via C -> J. The dead
    branch (C) has to be the one forced."""
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "G", "function_logic_gate",
         {"condition_type": "contains", "condition_value": "", "true_node_id": "2", "false_node_id": "3"}, ["2", "3"]),
        ("2", "A", "function_gemini_ask", {"instructions": "AAA"}, ["5", "4"]),
        ("3", "B", "function_gemini_ask", {"instructions": "BBB"}, ["4"]),
        ("4", "C", "function_gemini_ask", {"instructions": "CCC"}, ["5"]),
        ("5", "J", "function_gemini_ask", {"instructions": "{{A}} ++ {{C}}"}, []),
    ])
    result = engine.run(graph)
    j_steps = [s for s in result["steps"] if s["node_id"] == "5"]
    assert len(j_steps) == 1, f"J ran {len(j_steps)} time(s): {j_steps}"
    assert result["success"], result
    assert "AAA" in j_steps[0]["output"] and "CCC" in j_steps[0]["output"], j_steps
    assert not [s for s in result["steps"] if s["node_id"] == "3"], "untaken branch B ran"


def test_stall_pick_looks_past_the_queue_itself():
    """Same shape one level deeper: G -> A (taken) / B (dead); A -> J, A -> C,
    B -> C, C -> X, X -> J. Stall queue is [J, C]. J's blocker X isn't in the queue
    yet, but IS reachable from C, which is -- so X will run and J must keep waiting.
    Only C is truly dead-blocked (on B). Checking just 'is the blocker queued right
    now' picks J and double-executes it."""
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "G", "function_logic_gate",
         {"condition_type": "contains", "condition_value": "", "true_node_id": "2", "false_node_id": "3"}, ["2", "3"]),
        ("2", "A", "function_gemini_ask", {"instructions": "AAA"}, ["5", "4"]),
        ("3", "B", "function_gemini_ask", {"instructions": "BBB"}, ["4"]),
        ("4", "C", "function_gemini_ask", {"instructions": "CCC"}, ["6"]),
        ("6", "X", "function_gemini_ask", {"instructions": "XXX"}, ["5"]),
        ("5", "J", "function_gemini_ask", {"instructions": "{{A}} ++ {{X}}"}, []),
    ])
    result = engine.run(graph)
    j_steps = [s for s in result["steps"] if s["node_id"] == "5"]
    assert len(j_steps) == 1, f"J ran {len(j_steps)} time(s): {j_steps}"
    assert result["success"], result


def test_review_gate_loop_back_still_terminates():
    """Regression guard for the predecessor gating above: a Review Gate's loop-back
    jump re-runs an already-executed node, so gating must not stall it."""
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Src", "function_gemini_ask", {"instructions": "SSS"}, ["2"]),
        ("2", "Gate", "builtin_review_gate", {"criteria": "ok", "loop_back_node_id": "1", "max_attempts": 2}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    gate_steps = [s for s in result["steps"] if s["node_id"] == "2"]
    assert len(gate_steps) == 2, gate_steps  # fails attempt 1, loops back, passes attempt 2
    assert "PASS" in gate_steps[-1]["output"], gate_steps


def test_upload_sources_requires_notebook_id():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Upload", "function_notebooklm_upload_sources", {"notebook_id": "", "file_paths": "a.pdf"}, []),
    ])
    result = engine.run(graph)
    step = next(s for s in result["steps"] if s["node_id"] == "1")
    assert step["status"] == "failed", step
    assert "notebook_id" in step["output"], step


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
