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


def test_expression_and_short_circuits_missing_field():
    # has_discount is false, so discount_pct must never be looked up.
    assert _eval_condition_expression("has_discount and discount_pct > 10", {"has_discount": False}) is False


def test_expression_or_short_circuits_missing_field():
    # already_approved is true, so needs_review must never be looked up.
    assert _eval_condition_expression("already_approved or needs_review", {"already_approved": True}) is True


def test_expression_type_mismatch_raises_workflow_run_error():
    try:
        _eval_condition_expression("total > region", {"total": 5, "region": "west"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def _conditions_engine(upstream_text):
    # Manually wires just enough WorkflowEngine state for _run_conditions to read
    # one upstream node's captured text via _gather_upstream_text, without going
    # through a full engine.run() (whose dry-run AI stubs wrap/prefix their output,
    # which would get in the way of testing exact JSON field extraction here).
    engine = WorkflowEngine(dry_run=True)
    engine.backward_edges = {"cond": ["src"]}
    engine.node_labels = {"src": "Src", "cond": "Cond"}
    engine.context = {"Src": upstream_text}
    return engine


def test_conditions_first_match_stops_at_first_true():
    engine = _conditions_engine('{"status": "approved", "region": "west"}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "status", "operator": "equals", "value": "approved", "target_node_id": "3"},
            {"mode": "simple", "field": "region", "operator": "equals", "value": "west", "target_node_id": "4"},
        ],
    })
    # Both conditions are true; first_match must return only the first one's target.
    assert target == "3", (verdict, target)


def test_conditions_all_matches_returns_every_true_target():
    engine = _conditions_engine('{"status": "approved", "region": "west"}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "all_matches",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "status", "operator": "equals", "value": "approved", "target_node_id": "3"},
            {"mode": "simple", "field": "region", "operator": "equals", "value": "west", "target_node_id": "4"},
            {"mode": "simple", "field": "status", "operator": "equals", "value": "denied", "target_node_id": "5"},
        ],
    })
    assert target == ["3", "4"], (verdict, target)


def test_conditions_default_used_when_none_match():
    engine = _conditions_engine('{"status": "pending"}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "status", "operator": "equals", "value": "approved", "target_node_id": "3"},
        ],
    })
    assert target == "9", (verdict, target)


def test_conditions_numeric_operators():
    engine = _conditions_engine('{"total": 1500}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "total", "operator": "gt", "value": "1000", "target_node_id": "3"},
        ],
    })
    assert target == "3", (verdict, target)

    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "total", "operator": "lt", "value": "1000", "target_node_id": "3"},
        ],
    })
    assert target == "9", (verdict, target)  # 1500 is not < 1000 -- falls through to default


def test_conditions_expression_mode_uses_parsed_fields_and_raw_input():
    engine = _conditions_engine('{"total": 1500, "region": "west"}')
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "expression", "expression": "total > 1000 and region == 'west'", "target_node_id": "3"},
        ],
    })
    assert target == "3", (verdict, target)

    # "input" is always bound to the raw upstream text, even when it's not JSON.
    engine2 = _conditions_engine("plain text here")
    verdict, target = engine2._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "expression", "expression": "'plain' in input", "target_node_id": "3"},
        ],
    })
    assert target == "3", (verdict, target)


def test_conditions_blank_field_tests_whole_upstream_text():
    engine = _conditions_engine("the quick brown fox")
    verdict, target = engine._run_conditions("cond", {
        "match_mode": "first_match",
        "default_target_node_id": "9",
        "conditions": [
            {"mode": "simple", "field": "", "operator": "contains", "value": "brown", "target_node_id": "3"},
        ],
    })
    assert target == "3", (verdict, target)


def test_conditions_all_matches_runs_every_target_node_end_to_end():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Src", "function_gemini_ask", {"instructions": "the quick brown fox"}, ["2"]),
        ("2", "Cond", "function_conditions", {
            "match_mode": "all_matches",
            "default_target_node_id": "5",
            "conditions": [
                {"mode": "simple", "field": "", "operator": "contains", "value": "quick", "target_node_id": "3"},
                {"mode": "simple", "field": "", "operator": "contains", "value": "fox", "target_node_id": "4"},
            ],
        }, ["3", "4", "5"]),
        ("3", "First", "function_gemini_ask", {"instructions": "AAA"}, []),
        ("4", "Second", "function_gemini_ask", {"instructions": "BBB"}, []),
        ("5", "Default", "function_gemini_ask", {"instructions": "CCC"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    ran_ids = [s["node_id"] for s in result["steps"]]
    # Both matching branches run, in order; the default branch does NOT run.
    assert ran_ids == ["1", "2", "3", "4"], ran_ids


def test_conditions_first_match_runs_only_one_target_node_end_to_end():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Src", "function_gemini_ask", {"instructions": "the quick brown fox"}, ["2"]),
        ("2", "Cond", "function_conditions", {
            "match_mode": "first_match",
            "default_target_node_id": "5",
            "conditions": [
                {"mode": "simple", "field": "", "operator": "contains", "value": "quick", "target_node_id": "3"},
                {"mode": "simple", "field": "", "operator": "contains", "value": "fox", "target_node_id": "4"},
            ],
        }, ["3", "4", "5"]),
        ("3", "First", "function_gemini_ask", {"instructions": "AAA"}, []),
        ("4", "Second", "function_gemini_ask", {"instructions": "BBB"}, []),
        ("5", "Default", "function_gemini_ask", {"instructions": "CCC"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    ran_ids = [s["node_id"] for s in result["steps"]]
    assert ran_ids == ["1", "2", "3"], ran_ids


def test_conditions_all_matches_does_not_double_execute_shared_target():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Src", "function_gemini_ask", {"instructions": "the quick brown fox"}, ["2"]),
        ("2", "Cond", "function_conditions", {
            "match_mode": "all_matches",
            "default_target_node_id": "4",
            "conditions": [
                {"mode": "simple", "field": "", "operator": "contains", "value": "quick", "target_node_id": "3"},
                {"mode": "simple", "field": "", "operator": "contains", "value": "fox", "target_node_id": "3"},
            ],
        }, ["3", "4"]),
        ("3", "Shared", "function_gemini_ask", {"instructions": "AAA"}, []),
        ("4", "Default", "function_gemini_ask", {"instructions": "CCC"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    ran_ids = [s["node_id"] for s in result["steps"]]
    # Both conditions match the same target "3" -- it must run exactly once, not twice.
    assert ran_ids == ["1", "2", "3"], ran_ids
    assert ran_ids.count("3") == 1, ran_ids


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
