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


def test_initialize_variable_all_types():
    engine = WorkflowEngine(dry_run=True)
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "s", "type": "String", "value": "hello"})
    assert engine.variables["s"] == "hello"
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "num", "type": "Number", "value": "42"})
    assert engine.variables["num"] == 42.0
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "b", "type": "Boolean", "value": "true"})
    assert engine.variables["b"] is True
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "arr", "type": "Array", "value": "[1, 2, 3]"})
    assert engine.variables["arr"] == [1, 2, 3]
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "obj", "type": "Object", "value": '{"a": 1}'})
    assert engine.variables["obj"] == {"a": 1}


def test_initialize_variable_duplicate_name_raises():
    engine = WorkflowEngine(dry_run=True)
    engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "x", "type": "String", "value": "a"})
    try:
        engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "x", "type": "String", "value": "b"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_initialize_variable_invalid_array_json_raises():
    engine = WorkflowEngine(dry_run=True)
    try:
        engine._execute_function_node("n", {"tool_id": "function_initialize_variable"}, {"name": "bad", "type": "Array", "value": "not json"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_set_variable_requires_initialized():
    engine = WorkflowEngine(dry_run=True)
    try:
        engine._execute_function_node("n", {"tool_id": "function_set_variable"}, {"name": "missing", "value": "x"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_set_variable_overwrites_and_preserves_json_type():
    engine = WorkflowEngine(dry_run=True)
    engine.variables["x"] = "initial"
    engine._execute_function_node("n", {"tool_id": "function_set_variable"}, {"name": "x", "value": '["a", "b"]'})
    assert engine.variables["x"] == ["a", "b"]
    engine._execute_function_node("n", {"tool_id": "function_set_variable"}, {"name": "x", "value": "plain text"})
    assert engine.variables["x"] == "plain text"


def test_increment_variable_requires_initialized_numeric():
    engine = WorkflowEngine(dry_run=True)
    try:
        engine._execute_function_node("n", {"tool_id": "function_increment_variable"}, {"name": "missing", "increment_by": "1"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass
    engine.variables["s"] = "not a number"
    try:
        engine._execute_function_node("n", {"tool_id": "function_increment_variable"}, {"name": "s", "increment_by": "1"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_increment_variable_produces_whole_number_ints():
    engine = WorkflowEngine(dry_run=True)
    engine.variables["count"] = 0
    output, jump = engine._execute_function_node("n", {"tool_id": "function_increment_variable"}, {"name": "count", "increment_by": "1"})
    assert engine.variables["count"] == 1
    assert output == "1"  # not "1.0"
    engine._execute_function_node("n", {"tool_id": "function_increment_variable"}, {"name": "count", "increment_by": "0.5"})
    assert engine.variables["count"] == 1.5


def test_append_variable_requires_initialized_list():
    engine = WorkflowEngine(dry_run=True)
    try:
        engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "missing", "value": "x"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass
    engine.variables["notalist"] = "x"
    try:
        engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "notalist", "value": "y"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_append_variable_preserves_json_types():
    engine = WorkflowEngine(dry_run=True)
    engine.variables["arr"] = []
    engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "arr", "value": "plain"})
    engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "arr", "value": "42"})
    engine._execute_function_node("n", {"tool_id": "function_append_variable"}, {"name": "arr", "value": '{"a": 1}'})
    assert engine.variables["arr"] == ["plain", 42, {"a": 1}]


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
