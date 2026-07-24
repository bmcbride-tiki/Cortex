---
tool_id: 'test_format_json'
title: 'Format JSON Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/json, connects/format-json]
---

# test-format-json

> **Status:** Active. Runnable both via `pytest` and directly (`python test_format_json.py`).

## Purpose

Confirms [[format_json]]'s `run()` pretty-prints valid JSON and fails cleanly (rather than crashing) on invalid JSON.

## Processing Logic

* `test_reformats_valid_json` -- compact JSON gets pretty-printed with indentation.
* `test_invalid_json_fails_cleanly` -- non-JSON text returns `success: false` with "Invalid JSON" in the message.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Pure in-memory test -- no filesystem/mocking needed, since [[format_json]] itself has no I/O.
