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
