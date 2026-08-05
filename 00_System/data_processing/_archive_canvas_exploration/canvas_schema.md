---
tool_id: 'canvas_schema'
title: 'Visual Canvas Graph Schema'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/schema-definition, scope/workflow-builder, connects/svgl-icon-manager, connects/canvas-parser]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# canvas-schema

> **Status:** Active but standalone -- exercised only by `sandbox_smoke_test.py`, not by any live page. No `__main__` block.

## Purpose

Defines the shape of an n8n-style visual workflow graph -- a list of `CanvasNode`s (boxes with a position, icon, and status) and `CanvasEdge`s (connecting lines). Built during an early visual-canvas exploration; **not** the same graph format the real, running Workflow Builder page uses (that page saves/loads a raw Drawflow.js export, parsed by [[workflow_engine]], not this schema).

## Processing Logic

### `CanvasNodeStyle` / `IconSource`

A node's visual styling: which icon system (`svgl` or `lucide`), the icon name, a resolved URL, badge label, and brand color.

### `CanvasNode.model_post_init()`

Runs automatically right after a `CanvasNode` is constructed -- if its style says `icon_source: svgl` and no URL was given directly, calls [[svgl_icon_manager]]'s `get_icon_url()` to fill one in.

### `WorkflowCanvasGraph`

The top-level container: `workflow_id`, `theme_mode`, and the `nodes`/`edges` lists.

## Output

A `WorkflowCanvasGraph` instance, consumed by `canvas_parser.py`'s `VisualWorkflowExecutor`.

## Notes for AI reuse

`CanvasNode.status` is a plain mutable string (`IDLE`/`RUNNING`/`SUCCESS`/`FAILED`/`GREYED_OUT`) that gets overwritten in place as a graph runs -- there's no history of past statuses. `required_capability` is stored as a plain string, not the `CapabilityFlag` enum itself; convert it back before checking (see `canvas_parser.py` for the reference pattern).
