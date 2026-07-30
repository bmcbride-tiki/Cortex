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
