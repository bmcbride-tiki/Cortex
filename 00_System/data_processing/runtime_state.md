---
tool_id: 'runtime_state'
title: 'Runtime State Persistence'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/state-persistence, scope/workflow-builder, connects/workflow-schema]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# runtime-state

> **Status:** Active, not yet wired into any live page. No `__main__` block.

## Purpose

Saves a workflow's current state ([[workflow_schema|WorkflowPayload]]) to a plain JSON file on disk, and loads it back later -- the mechanism that would let a paused or long-running workflow be picked up again without losing track of what step it's on. Not a database; a single JSON snapshot per call.

## Processing Logic

### `save_state(payload, path=STATE_FILE) -> None`

Overwrites the target file with `payload.model_dump_json(indent=2)`. No custom serialization -- relies entirely on Pydantic.

### `load_state(path=STATE_FILE) -> WorkflowPayload`

Reads the file and reconstructs a `WorkflowPayload` via `model_validate_json`. Raises a plain `FileNotFoundError` if nothing has been saved yet -- callers are expected to handle that rather than getting a silent default payload back.

## Output

`runtime_state.json`, written next to this file inside `00_System/data_processing/` by default (overridable via the `path` argument on both functions).

## Notes for AI reuse

There is no history here -- `save_state` always overwrites the one file. If multiple concurrent workflow runs ever need independent persisted state, `path` needs to become per-workflow (e.g. keyed by `workflow_id`) rather than a single shared default.
