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
