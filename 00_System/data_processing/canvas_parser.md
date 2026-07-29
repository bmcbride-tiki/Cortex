---
tool_id: 'canvas_parser'
title: 'Visual Canvas Graph Executor'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/workflow-execution, function/license-gating, scope/workflow-builder, connects/workflow-schema, connects/canvas-schema, connects/user-identity, connects/core-router]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# canvas-parser

> **Status:** Active but standalone -- exercised only by `sandbox_smoke_test.py`, not by any live page. No `__main__` block.

## Purpose

Actually runs a [[canvas_schema|WorkflowCanvasGraph]] -- walks its nodes in order, calls each node's real Python function, and updates that node's on-screen `status` (`SUCCESS`/`FAILED`/`GREYED_OUT`) as it goes. This is the bridge between the standalone `canvas_schema.py` graph model and [[core_router]]'s actual execution engine -- nothing else in the codebase connected the two before this file was written.

## Processing Logic

### `VisualWorkflowExecutor.execute_canvas_graph_async(graph, payload) -> WorkflowPayload`

For each node in `graph.nodes`, in list order:

1. Looks up the node's `func_name` in the `registry` dict passed to the constructor. No match -> node marked `FAILED`, execution stops.
2. Converts the node's plain-string `required_capability` back into a real `CapabilityFlag` (see [[user_identity]]).
3. Calls [[core_router]]'s `CoreWorkflowRouter.execute_block_async(...)` with that capability. On `PermissionError` (unlicensed), the node is marked `GREYED_OUT` and execution stops. On any other exception, `FAILED` and stops. On success, `SUCCESS` and the loop continues to the next node with the updated payload.

## Output

The final `WorkflowPayload` reached before the graph completed or stopped; `graph.nodes[*].status` mutated in place for the UI to read.

## Notes for AI reuse

This executor is strictly sequential and stops at the first non-success -- it does not skip a blocked/failed node and try downstream ones. If a future graph needs branching or parallel execution, this file (not `canvas_schema.py`) is where that logic would need to be added.
