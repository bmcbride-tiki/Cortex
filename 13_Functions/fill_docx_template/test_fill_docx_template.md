---
tool_id: 'test_fill_docx_template'
title: 'Fill Docx Template Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/docx, connects/fill-docx-template]
---

# test-fill-docx-template

> **Status:** Active. Runnable both via `pytest` and directly (`python test_fill_docx_template.py`).

## Purpose

Confirms [[fill_docx_template]]'s `run()` replaces a `{{ content }}` token in a real generated `.docx` template, and fails cleanly on a missing template file.

## Processing Logic

* `test_fills_content_token` -- generates a throwaway template with a `{{ content }}` paragraph, runs the fill, and asserts the output paragraph has the real text substituted in.
* `test_missing_template_fails_cleanly` -- a nonexistent template path returns `success: false`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Generates its own throwaway `.docx` template via `python-docx` rather than relying on a fixture file, keeping the test self-contained.
