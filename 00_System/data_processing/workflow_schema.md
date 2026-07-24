---
tool_id: 'workflow_schema'
title: 'Workflow Schema'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/schema-definition, function/workflow-execution, scope/workflow-builder, connects/core-router, connects/user-identity, connects/canvas-parser, connects/observer-transformer, connects/runtime-state]
---

# workflow-schema

> **Status:** Active. Pydantic v2 model file, no `__main__` block. Imported by nearly everything else in `data_processing/`, plus [[core_router]]'s `CoreWorkflowRouter`.

## Purpose

Defines the standard "envelope" every workflow step passes to the next -- one consistent shape (`WorkflowPayload`) for a step's data, attached files, and run history, so any building block can plug into any other without custom wiring per pair. This is the newer, `CoreWorkflowRouter`-based execution model -- a separate thing from the Drawflow-graph model [[workflow_engine]] runs for the live Workflow Builder page.

## Processing Logic

### `FileReference`

A pointer to one file a workflow is working with -- never the file's bytes, just where to find it (`uri`) and identifying details (`source`, `filename`, `mime_type`).

### `WorkflowInputData`

The actual working data for the current step: free-form `data` (key/value), the list of attached `files`, and any `parameters`/flags.

### `StepHistory` / `WorkflowContext.history`

A running, append-only log of every step that's run so far (step ID, block type, status, output keys) -- what a tool like the Workflow Map's execution trace reads to show what happened during a run.

### `WorkflowContext`

Everything about the run itself: which workflow, current step, the signed-in user's resolved license entitlements (`user_entitlements`, see [[user_identity]]), and the `history` log above.

### `WorkflowPayload.validate_capability_access(required_capability) -> bool`

Resolves the current user's entitlements if not already cached on the payload, then checks whether they hold the given capability. Called by [[core_router]]'s `CoreWorkflowRouter` before running a license-gated step.

### `WorkflowPayload.transition_to_next_step(next_step_id, block_output, block_type) -> WorkflowPayload`

The one function that advances a workflow. Merges the just-finished step's output into the running `data`, appends a `StepHistory` entry, and returns a brand-new `WorkflowPayload` pointed at the next step -- carrying the same `user_entitlements` forward rather than losing them (a bug fixed during this feature's build: the reconstructed `WorkflowContext` didn't originally carry entitlements forward, silently re-resolving the user on every single step).

## Output

A `WorkflowPayload` instance per step -- consumed by [[core_router]]'s `CoreWorkflowRouter.execute_block_async`, `canvas_parser.py`'s `VisualWorkflowExecutor`, and `observer_transformer.py`'s `PipelineObserverTransformer`. Serializable to/from plain JSON via `runtime_state.py`.

## Notes for AI reuse

Any code that builds a new `WorkflowContext` from an existing one (a transition, a clone) must explicitly carry `user_entitlements` forward -- Pydantic won't do it automatically since it's a fresh model instance, not a mutation. See `transition_to_next_step` for the reference pattern.
