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
