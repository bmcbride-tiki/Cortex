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


def _container_graph(outer_specs, container_id, container_label, loop_params, inner_module_name, inner_specs, outer_targets_from_container):
    """Builds a Drawflow-shaped graph_json with one container node wired into the
    Home module, whose own sub-diagram lives in a separate module. outer_specs and
    inner_specs are lists of (node_id, label, tool_id, params, targets) same as
    _graph(); inner node targets are wired within the inner module only."""
    home_data = {}
    for node_id, label, tool_id, params, targets in outer_specs:
        home_data[node_id] = {
            "name": tool_id,
            "data": {"kind": "function", "tool_id": tool_id, "category": None, "title": label, "label": label, "params": params},
            "outputs": {"output_1": {"connections": [{"node": t, "output": "input_1"} for t in targets]}},
        }
    home_data[container_id] = {
        "name": "container",
        "data": {
            "kind": "container", "tool_id": "container", "category": None,
            "title": container_label, "label": container_label, "params": loop_params,
            "module_name": inner_module_name,
        },
        "outputs": {"output_1": {"connections": [{"node": t, "output": "input_1"} for t in outer_targets_from_container]}},
    }
    inner_data = {}
    for node_id, label, tool_id, params, targets in inner_specs:
        inner_data[node_id] = {
            "name": tool_id,
            "data": {"kind": "function", "tool_id": tool_id, "category": None, "title": label, "label": label, "params": params},
            "outputs": {"output_1": {"connections": [{"node": t, "output": "input_1"} for t in targets]}},
        }
    return {"drawflow": {"Home": {"data": home_data}, inner_module_name: {"data": inner_data}}}


def test_apply_to_each_container_extracted_not_flattened():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1,2,3]"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Inner", "function_compose", {"value": "x"}, [])],
        outer_targets_from_container=[],
    )
    nodes, forward_edges, backward_edges = engine._parse_graph(graph)
    assert "10" in nodes and nodes["10"]["kind"] == "container"
    assert "11" not in nodes  # pulled out of the shared graph
    assert "10" in engine.loop_subgraphs
    sub = engine.loop_subgraphs["10"]
    assert list(sub["nodes"].keys()) == ["11"]
    assert sub["entry_ids"] == ["11"] and sub["exit_ids"] == ["11"]


def test_plain_container_nested_inside_loop_container_still_resolves():
    # The specific correctness risk the recursive extraction design targets:
    # a PLAIN container's inner nodes, nested inside a LOOP container's own
    # module, must end up inside the loop's private subgraph, not lost.
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1]"},
        inner_module_name="loop_mod_1",
        inner_specs=[
            ("11", "BeforeNested", "function_compose", {"value": "a"}, ["20"]),
        ],
        outer_targets_from_container=[],
    )
    # Manually splice a plain container ("20") into the loop's module, whose
    # own sub-diagram lives in yet another module ("nested_mod").
    graph["drawflow"]["loop_mod_1"]["data"]["20"] = {
        "name": "container",
        "data": {"kind": "container", "tool_id": "container", "category": None, "title": "Nested", "label": "Nested", "params": {}, "module_name": "nested_mod"},
        "outputs": {"output_1": {"connections": []}},
    }
    graph["drawflow"]["nested_mod"] = {"data": {
        "21": {
            "name": "function_compose",
            "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "Nested Inner", "label": "NestedInner", "params": {"value": "b"}},
            "outputs": {"output_1": {"connections": []}},
        }
    }}

    nodes, forward_edges, backward_edges = engine._parse_graph(graph)
    assert "10" in nodes  # loop container itself survives
    assert "11" not in nodes and "20" not in nodes and "21" not in nodes  # all pulled into the loop's private subgraph
    sub = engine.loop_subgraphs["10"]
    assert set(sub["nodes"].keys()) == {"11", "21"}  # "20" (the nested container) is spliced away WITHIN the private copy, same as top-level
    assert sub["forward_edges"]["11"] == ["21"]  # rewired through the nested container's own entry/exit


def test_backward_compatible_plain_container_unaffected():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[("1", "Before", "function_compose", {"value": "x"}, ["10"])],
        container_id="10", container_label="Group", loop_params={},  # no loop_type -- today's plain container
        inner_module_name="mod_1",
        inner_specs=[("11", "Inner", "function_compose", {"value": "y"}, [])],
        outer_targets_from_container=["2"],
    )
    graph["drawflow"]["Home"]["data"]["2"] = {
        "name": "function_compose",
        "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "After", "label": "After", "params": {"value": "z"}},
        "outputs": {"output_1": {"connections": []}},
    }
    nodes, forward_edges, backward_edges = engine._parse_graph(graph)
    assert "10" not in nodes  # plain container IS spliced away, unchanged from today
    assert "11" in nodes
    assert forward_edges["1"] == ["11"]  # rewired to the inner entry, same as before this slice
    assert engine.loop_subgraphs == {}


def test_apply_to_each_end_to_end():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[("1", "Src", "function_compose", {"value": '[10, 20, 30]'}, [])],
        container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "{{Src}}"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Doubled", "function_compose", {"value": "got {{loop.item}} at {{loop.index}}"}, [])],
        outer_targets_from_container=[],
    )
    graph["drawflow"]["Home"]["data"]["1"]["outputs"]["output_1"]["connections"] = [{"node": "10", "output": "input_1"}]
    result = engine.run(graph)
    assert result["success"], result
    container_step = next(s for s in result["steps"] if s["node_id"] == "10")
    iterations = json.loads(container_step["output"])
    assert iterations == ["got 10 at 0", "got 20 at 1", "got 30 at 2"]


def test_apply_to_each_inner_failure_aborts_whole_loop():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1, 2]"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Bad", "function_parse_json", {"required_keys": ""}, [])],  # gathers upstream text -- none connected -> invalid JSON
        outer_targets_from_container=[],
    )
    result = engine.run(graph)
    assert result["success"] is False
    container_step = next(s for s in result["steps"] if s["node_id"] == "10")
    assert container_step["status"] == "failed"
    # Only ONE inner-node failure log entry -- the loop aborted after the first
    # iteration's failure rather than attempting a second.
    inner_failures = [s for s in result["steps"] if s["node_id"] == "11"]
    assert len(inner_failures) == 1


def test_apply_to_each_context_and_container_output():
    # Connection-scoping is unchanged by loops: "After" is only directly wired to
    # the container ("Loop"), never to the loop-body node ("Inner") -- it can only
    # read the container's own aggregate JSON array via {{Loop}}, exactly like any
    # other node's output is referenced. {{Inner}} from outside the loop's module
    # would raise MissingInputError, same as referencing any non-adjacent label
    # would today -- this test doesn't attempt that unreachable reference.
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1, 2, 3]"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Inner", "function_compose", {"value": "n={{loop.item}}"}, [])],
        outer_targets_from_container=["2"],
    )
    graph["drawflow"]["Home"]["data"]["2"] = {
        "name": "function_compose",
        "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "After", "label": "After", "params": {"value": "loop result: {{Loop}}"}},
        "outputs": {"output_1": {"connections": []}},
    }
    result = engine.run(graph)
    assert result["success"], result
    after_step = next(s for s in result["steps"] if s["node_id"] == "2")
    prefix = "loop result: "
    assert after_step["output"].startswith(prefix)
    assert json.loads(after_step["output"][len(prefix):]) == ["n=1", "n=2", "n=3"]
    # Internally, self.context["Inner"] (the inner node's OWN label) still holds
    # the last iteration's value, same as any node re-run in place would -- not
    # reachable from outside the loop's module, but real and correct internally.
    assert engine.context["Inner"] == "n=3"


def test_do_until_stops_when_condition_true():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[("1", "Init", "function_initialize_variable", {"name": "counter", "type": "Number", "value": "0"}, ["10"])],
        container_id="10", container_label="Loop",
        loop_params={"loop_type": "do_until", "condition": "counter >= 3", "max_iterations": 10},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Inc", "function_increment_variable", {"name": "counter", "increment_by": "1"}, [])],
        outer_targets_from_container=[],
    )
    result = engine.run(graph)
    assert result["success"], result
    container_step = next(s for s in result["steps"] if s["node_id"] == "10")
    iterations = json.loads(container_step["output"])
    assert len(iterations) == 3  # 0->1, 1->2, 2->3, condition true after 3rd
    assert engine.variables["counter"] == 3


def test_do_until_stops_at_max_iterations_without_raising():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[("1", "Init", "function_initialize_variable", {"name": "counter", "type": "Number", "value": "0"}, ["10"])],
        container_id="10", container_label="Loop",
        loop_params={"loop_type": "do_until", "condition": "counter >= 1000", "max_iterations": 5},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Inc", "function_increment_variable", {"name": "counter", "increment_by": "1"}, [])],
        outer_targets_from_container=[],
    )
    result = engine.run(graph)
    assert result["success"], result
    container_step = next(s for s in result["steps"] if s["node_id"] == "10")
    assert len(json.loads(container_step["output"])) == 5
    assert engine.variables["counter"] == 5


def test_terminate_inside_loop_ends_entire_run():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Loop",
        loop_params={"loop_type": "apply_to_each", "items": "[1, 2, 3]"},
        inner_module_name="loop_mod_1",
        inner_specs=[("11", "Stop", "function_terminate", {"status": "Failed", "message": "stop from inside loop"}, [])],
        outer_targets_from_container=["2"],
    )
    graph["drawflow"]["Home"]["data"]["2"] = {
        "name": "function_compose",
        "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "Never", "label": "Never", "params": {"value": "should not run"}},
        "outputs": {"output_1": {"connections": []}},
    }
    result = engine.run(graph)
    assert result["success"] is False
    assert result["terminated"] == {"status": "Failed", "message": "stop from inside loop"}
    ran_ids = [s["node_id"] for s in result["steps"]]
    assert "2" not in ran_ids  # the whole run stopped, not just the loop


def test_nested_apply_to_each_resolves_innermost_loop_stack():
    engine = WorkflowEngine(dry_run=True)
    graph = _container_graph(
        outer_specs=[], container_id="10", container_label="Outer",
        loop_params={"loop_type": "apply_to_each", "items": '["a", "b"]'},
        inner_module_name="outer_mod",
        inner_specs=[],
        outer_targets_from_container=[],
    )
    # Nest an inner Apply to Each container inside the outer loop's own module.
    graph["drawflow"]["outer_mod"]["data"]["20"] = {
        "name": "container",
        "data": {
            "kind": "container", "tool_id": "container", "category": None,
            "title": "Inner", "label": "Inner",
            "params": {"loop_type": "apply_to_each", "items": "[1, 2]"},
            "module_name": "inner_mod",
        },
        "outputs": {"output_1": {"connections": []}},
    }
    graph["drawflow"]["inner_mod"] = {"data": {
        "21": {
            "name": "function_compose",
            "data": {"kind": "function", "tool_id": "function_compose", "category": None, "title": "Combine", "label": "Combine", "params": {"value": "outer={{loop.item}}"}},
            "outputs": {"output_1": {"connections": []}},
        }
    }}
    result = engine.run(graph)
    assert result["success"], result
    outer_step = next(s for s in result["steps"] if s["node_id"] == "10")
    outer_iterations = json.loads(outer_step["output"])
    # Every node output in this engine is text (self.context: Dict[str, str]) --
    # the outer loop's own aggregate is a JSON array of strings, each itself a
    # JSON-encoded array (the inner loop's own aggregate), same as any other
    # node's JSON-shaped text output needs an explicit json.loads to unpack.
    assert len(outer_iterations) == 2  # outer ran twice, once per "a"/"b"
    for inner_text in outer_iterations:
        # Each outer iteration's inner loop result: the "Combine" node's
        # {{loop.item}} must resolve to the INNER loop's current item (1, then 2)
        # both times, NOT the outer loop's "a"/"b" -- proving innermost-frame
        # resolution, not just "some" loop context leaking through.
        assert json.loads(inner_text) == ["outer=1", "outer=2"]


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
