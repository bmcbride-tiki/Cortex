---
tool_id: 'test_write_powerpoint'
title: 'Write PowerPoint Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/pptx, connects/write-powerpoint]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-write-powerpoint

> **Status:** Active. Runnable both via `pytest` and directly (`python test_write_powerpoint.py`).

## Purpose

Confirms [[write_powerpoint]]'s `run()` creates a real `.pptx` with one slide per double-newline-separated text block, titled from each block's first line.

## Processing Logic

`test_creates_one_slide_per_block` -- two blocks of text produce a real two-slide `.pptx`, read back with `python-pptx` to confirm each slide's title.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Reads the generated file back with the real `python-pptx` library rather than just checking it exists -- confirms the slide/title structure, not just that bytes were written.
