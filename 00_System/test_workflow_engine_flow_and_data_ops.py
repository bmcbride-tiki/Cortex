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

from workflow_engine import WorkflowEngine, WorkflowRunError


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


def test_compose_substitutes_tokens():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Name", "function_gemini_ask", {"instructions": "Alice"}, ["2"]),
        ("2", "Greeting", "function_compose", {"value": "Hello, {{Name}}!"}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    assert result["steps"][1]["output"] == "Hello, [DRY RUN] Simulated Gemini response for prompt:\nAlice!"


def test_parse_json_valid_passthrough():
    engine = _single_input_engine("n", '{"a": 1}')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_parse_json"}, {"required_keys": ""})
    assert json.loads(output) == {"a": 1}
    assert jump is None


def test_parse_json_invalid_raises():
    engine = _single_input_engine("n", "not json")
    try:
        engine._execute_function_node("n", {"tool_id": "function_parse_json"}, {"required_keys": ""})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_parse_json_missing_required_key_raises():
    engine = _single_input_engine("n", '{"a": 1}')
    try:
        engine._execute_function_node("n", {"tool_id": "function_parse_json"}, {"required_keys": "a\nb"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError as e:
        assert "b" in str(e)


def test_parse_json_present_required_keys_pass():
    engine = _single_input_engine("n", '{"a": 1, "b": 2}')
    output, jump = engine._execute_function_node("n", {"tool_id": "function_parse_json"}, {"required_keys": "a\nb"})
    assert json.loads(output) == {"a": 1, "b": 2}


from unittest.mock import patch, MagicMock


def test_http_dry_run_no_network_call():
    engine = _single_input_engine("n", "")
    with patch("requests.request") as mock_request:
        output, jump = engine._execute_function_node("n", {"tool_id": "function_http"}, {
            "method": "GET", "uri": "https://example.com/api", "headers": "", "body": "",
        })
    mock_request.assert_not_called()
    assert "https://example.com/api" in output


def test_http_live_success():
    engine = WorkflowEngine(dry_run=False)
    engine.backward_edges, engine.node_labels, engine.context = {}, {}, {}
    mock_resp = MagicMock(status_code=200, headers={"Content-Type": "application/json"}, text='{"ok": true}')
    with patch("requests.request", return_value=mock_resp) as mock_request:
        output, jump = engine._execute_function_node("n", {"tool_id": "function_http"}, {
            "method": "POST", "uri": "https://example.com/api", "headers": '{"X-Test": "1"}', "body": '{"x": 1}',
        })
    mock_request.assert_called_once_with("POST", "https://example.com/api", headers={"X-Test": "1"}, data='{"x": 1}', timeout=30)
    parsed = json.loads(output)
    assert parsed["status_code"] == 200
    assert parsed["body"] == '{"ok": true}'


def test_http_non_2xx_raises():
    engine = WorkflowEngine(dry_run=False)
    engine.backward_edges, engine.node_labels, engine.context = {}, {}, {}
    mock_resp = MagicMock(status_code=404, reason="Not Found", text="no such resource")
    with patch("requests.request", return_value=mock_resp):
        try:
            engine._execute_function_node("n", {"tool_id": "function_http"}, {
                "method": "GET", "uri": "https://example.com/missing", "headers": "", "body": "",
            })
            assert False, "expected WorkflowRunError"
        except WorkflowRunError as e:
            assert "404" in str(e)


def test_http_blank_uri_raises():
    engine = _single_input_engine("n", "")
    try:
        engine._execute_function_node("n", {"tool_id": "function_http"}, {"method": "GET", "uri": "", "headers": "", "body": ""})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass


def test_response_passes_through_and_is_recorded():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Src", "function_compose", {"value": "final answer"}, ["2"]),
        ("2", "Out", "function_response", {}, []),
    ])
    result = engine.run(graph)
    assert result["success"], result
    assert result["responses"] == [{"node_id": "2", "label": "Out", "output": "final answer"}], result["responses"]


def test_response_absent_when_no_response_node():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([("1", "Src", "function_compose", {"value": "x"}, [])])
    result = engine.run(graph)
    assert result["responses"] == [], result["responses"]


def test_terminate_failed_stops_run_before_later_node():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([
        ("1", "Stop", "function_terminate", {"status": "Failed", "message": "stopping here"}, ["2"]),
        ("2", "Never", "function_compose", {"value": "should not run"}, []),
    ])
    result = engine.run(graph)
    assert result["success"] is False, result
    assert result["terminated"] == {"status": "Failed", "message": "stopping here"}, result["terminated"]
    ran_ids = [s["node_id"] for s in result["steps"]]
    assert ran_ids == ["1"], ran_ids


def test_terminate_succeeded_marks_run_successful():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([("1", "Stop", "function_terminate", {"status": "Succeeded", "message": "done"}, [])])
    result = engine.run(graph)
    assert result["success"] is True, result
    assert result["terminated"]["status"] == "Succeeded"


def test_no_terminate_leaves_terminated_none():
    engine = WorkflowEngine(dry_run=True)
    graph = _graph([("1", "Src", "function_compose", {"value": "x"}, [])])
    result = engine.run(graph)
    assert result["terminated"] is None


import time as _time


def test_delay_dry_run_does_not_sleep():
    engine = WorkflowEngine(dry_run=True)
    start = _time.monotonic()
    output, jump = engine._execute_function_node("n", {"tool_id": "function_delay"}, {"duration": 3600, "unit": "Seconds"})
    assert _time.monotonic() - start < 1
    assert "[DRY RUN]" in output


def test_delay_over_cap_raises_without_sleeping():
    engine = WorkflowEngine(dry_run=False)
    start = _time.monotonic()
    try:
        engine._execute_function_node("n", {"tool_id": "function_delay"}, {"duration": 10, "unit": "Minutes"})
        assert False, "expected WorkflowRunError"
    except WorkflowRunError:
        pass
    assert _time.monotonic() - start < 1


def test_delay_live_short_actually_sleeps():
    engine = WorkflowEngine(dry_run=False)
    start = _time.monotonic()
    output, jump = engine._execute_function_node("n", {"tool_id": "function_delay"}, {"duration": 0.2, "unit": "Seconds"})
    elapsed = _time.monotonic() - start
    assert elapsed >= 0.2, elapsed


def test_delay_until_past_timestamp_continues_immediately():
    engine = WorkflowEngine(dry_run=False)
    output, jump = engine._execute_function_node("n", {"tool_id": "function_delay_until"}, {"timestamp": "2000-01-01T00:00:00"})
    assert "already passed" in output


def test_delay_until_far_future_raises():
    engine = WorkflowEngine(dry_run=False)
    try:
        engine._execute_function_node("n", {"tool_id": "function_delay_until"}, {"timestamp": "2099-01-01T00:00:00"})
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
