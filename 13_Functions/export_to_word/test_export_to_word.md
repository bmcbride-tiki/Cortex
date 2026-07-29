---
tool_id: 'test_export_to_word'
title: 'Export to Word Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/docx, connects/export-to-word]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-export-to-word

> **Status:** Active. Runnable both via `pytest` and directly (`python test_export_to_word.py`).

## Purpose

Confirms [[export_to_word]]'s `run()` writes a real `.docx` with one paragraph per input line.

## Processing Logic

`test_writes_docx` -- writes two-line text, then reads the result back with `python-docx` and asserts each line became its own paragraph.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Reads the generated file back with the real `python-docx` library rather than just checking it exists -- confirms the paragraph structure, not just that bytes were written.
