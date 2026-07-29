---
tool_id: 'test_populate_word_template_from_json'
title: 'Populate Word Template from JSON Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/docx, scope/json, connects/populate-word-template-from-json]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-populate-word-template-from-json

> **Status:** Active. Runnable both via `pytest` and directly (`python test_populate_word_template_from_json.py`).

## Purpose

Confirms [[populate_word_template_from_json]]'s `run()` fills multiple distinct named placeholders in a real generated `.docx` template, and fails cleanly on a missing template or empty data.

## Processing Logic

* `test_fills_multiple_named_placeholders` -- a template with `{{ name }}`/`{{trade}}` placeholders gets both filled correctly from a two-key `data` dict.
* `test_missing_template_fails_cleanly` -- a nonexistent template path returns `success: false`.
* `test_empty_data_fails_cleanly` -- an empty `data` dict returns `success: false`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Generates its own throwaway `.docx` template via `python-docx` rather than relying on a fixture file, keeping the test self-contained.
