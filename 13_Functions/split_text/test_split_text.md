---
tool_id: 'test_split_text'
title: 'Split Text Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, connects/split-text]
---

# test-split-text

> **Status:** Active. Runnable both via `pytest` and directly (`python test_split_text.py`).

## Purpose

Confirms [[split_text]]'s `run()` splits on a given/default delimiter and selects the right segment, and fails cleanly on an out-of-range index.

## Processing Logic

* `test_splits_and_selects_segment` -- comma-delimited text returns the correct indexed segment.
* `test_default_delimiter_is_newline` -- omitting `delimiter` splits on `\n`.
* `test_out_of_range_index_fails_cleanly` -- an index past the segment count returns `success: false`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Pure in-memory test -- no filesystem/mocking needed, since [[split_text]] itself has no I/O.
