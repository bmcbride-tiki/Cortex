---
tool_id: 'observer_transformer'
title: 'Pipeline Observer Transformer'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/workflow-observer, scope/workflow-observer, connects/workflow-schema, connects/observer-schema, connects/svgl-icon-manager, connects/user-identity]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# observer-transformer

> **Status:** Active but standalone -- exercised only by `sandbox_smoke_test.py`, not by any live page. No `__main__` block.

## Purpose

Converts a real, in-progress [[workflow_schema|WorkflowPayload]] (a workflow's current state plus its step-by-step history) into the fixed 6-stage [[observer_schema|PipelineObserverView]] shape, so it could be rendered as a visual pipeline dashboard.

## Processing Logic

### `PipelineObserverTransformer.build_observer_view(payload, pipeline_title) -> PipelineObserverView`

1. Resolves the current user (via [[user_identity]]) if the payload doesn't already carry entitlements.
2. Builds the fixed 6 stages (Capture/Classify/Route/Process/Human Gate/Execute).
3. Populates Stage 1 with an ingestion node reflecting `payload.input.files`.
4. Distributes each `payload.context.history` entry across stages 2-4 by its position in the history list (`min(idx + 1, 3)`) -- a simple placeholder mapping, not a real analysis of what kind of work each step did.
5. Marks the Human Gate stage `WAITING_APPROVAL` only when `payload.step_id` is literally the string `"human_gate"`.
6. Builds two `TelemetryLogEntry` rows (init + current-step) with wall-clock timestamps.

## Output

A `PipelineObserverView` instance; printed as JSON by `sandbox_smoke_test.py`'s `test_observer_pipeline`.

## Notes for AI reuse

Same tech-debt note as [[observer_schema]]: this transformer isn't wired into any real page yet -- the live Workflow Map tool computes its own stage layout directly in `server.py` instead of calling this. If unifying the two, this file's history-to-stage distribution logic (step 4 above) would need to become a real graph-depth calculation like the Workflow Map endpoint's, not the current placeholder `min(idx + 1, 3)`.
