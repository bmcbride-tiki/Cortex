# 00_System/test_workflow_engine_flow_and_data_ops.py
"""Assert-based smoke tests for the flow-control and data-operation Function
nodes (Compose, Parse JSON, HTTP, Response, Terminate, Delay, Delay Until,
and the array data-op family). Run directly: python test_workflow_engine_flow_and_data_ops.py
"""
import sys
sys.dont_write_bytecode = True
import json

from pathlib import Path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from workflow_engine import WorkflowEngine, WorkflowRunError, WorkflowTerminate, _eval_condition_expression


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
