---
tool_id: 'model_classifications'
title: 'AI Model Classification Levels'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/classification, scope/workflow-builder, connects/server, connects/test-model-classifications]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# model-classifications

> **Status:** Active. No `__main__` block. Imported by [[server]] and its own test file [[test_model_classifications]].

## Purpose

Single source of truth for which AI model backends this project talks to are approved for which information-security classification level, per the Government of Alberta AI Academy classification guide. Used by [[server]] to annotate the Workflow Builder's node registry, and by `templates/workflow-builder.html` (via that same registry response) to compute a workflow's live classification ceiling from the models its nodes use.

## Processing Logic

### `CLASSIFICATION_LEVELS` / `CLASSIFICATION_LABELS`

Ordered least -> most sensitive: `public`, `protected_a`, `protected_b`, `protected_c`, with display labels.

### `MODEL_CLASSIFICATIONS`

Model key -> classification level: `copilot` -> `protected_b`, `gemini`/`notebooklm` -> `protected_a`, `chatgpt`/`claude` -> `public` (Claude isn't in the official list this was built from -- defaulted to the most conservative level until officially classified).

### `classification_ceiling(model_keys) -> Optional[str]`

"Most restrictive model wins": returns the lowest classification level among the given model keys (a tool cleared for a higher level is trusted for every level below it too), or `None` if no known model keys were given.

## Output

A classification level string (or `None`), surfaced by [[server]]'s `/api/workflow-builder/node-registry` endpoint as `model_classifications.levels/labels/models`.

## Notes for AI reuse

The moment Claude gets an official classification from the source guide, update `MODEL_CLASSIFICATIONS["claude"]` here -- nothing else needs to change, `classification_ceiling` and every consumer already read from this one dict.
