---
tool_id: 'test_export_to_markdown'
title: 'Export to Markdown Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/markdown, connects/export-to-markdown]
---

# test-export-to-markdown

> **Status:** Active. Runnable both via `pytest` and directly (`python test_export_to_markdown.py`).

## Purpose

Confirms [[export_to_markdown]]'s `run()` writes text unchanged into a real `.md` file in a temporary folder.

## Processing Logic

`test_writes_text_as_is` -- writes text with markdown formatting and asserts the file content matches exactly, with a `.md` extension.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Uses a real `tempfile.TemporaryDirectory()` rather than mocking the filesystem, since this Function's only real behavior is file I/O.
