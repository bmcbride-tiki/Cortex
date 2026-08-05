---
tool_id: 'observer_schema'
title: 'Pipeline Observer Schema'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/schema-definition, scope/workflow-observer, connects/observer-transformer]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# observer-schema

> **Status:** Active but standalone -- exercised only by `sandbox_smoke_test.py`, not by any live page. No `__main__` block.

## Purpose

Defines the data shape for a "pipeline observer" view: a workflow drawn as a fixed sequence of named stages (Capture -> Classify -> Route -> Process -> Human Gate -> Execute), each holding one or more nodes with a status, plus a running telemetry log. Built for a proposed n8n-style execution dashboard.

## Processing Logic

### `StageStatus` (enum)

The fixed set of states a stage/node can be in, including `WAITING_APPROVAL` (human-in-the-loop checkpoint) and `GREYED_OUT` (licensing block).

### `PipelineNode.human_gate`

Only set for a node representing a human approval checkpoint -- carries who needs to approve it (`approver_upn`) and their decision so far.

### `PipelineObserverView`

The top-level container returned by `observer_transformer.py`: workflow ID/title, overall status, current stage, the ordered `stages` list, and `telemetry_logs`.

## Output

Consumed exclusively by `observer_transformer.py`'s `PipelineObserverTransformer.build_observer_view()`.

## Notes for AI reuse

⚠ **Tech-debt finding from this documentation pass:** this schema's fixed 6-stage shape is **not** what the actual, live Workflow Map tool (`server.py`'s `GET /api/workflow-builder/workflows/{id}/map`) uses -- that endpoint computes its own, more general stage columns directly from a saved workflow's real graph (by BFS depth), independent of this file. `PipelineObserverView`/`PipelineObserverTransformer` are currently exercised only by the smoke test, not by any page a user can open. Either wire this into a real page, or fold its useful ideas (the status enum, telemetry log entries) into the Workflow Map endpoint and retire this one, so there aren't two competing "workflow status view" models in the codebase.
