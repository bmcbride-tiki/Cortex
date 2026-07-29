---
tool_id: 'test_upload_m365_file'
title: 'Upload M365 File Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/onedrive, scope/sharepoint, connects/upload-m365-file]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-upload-m365-file

> **Status:** Active. Runnable both via `pytest` and directly (`python test_upload_m365_file.py`).

## Purpose

Confirms [[upload_m365_file]]'s `run()` returns a successful result with a real-looking item ID, using a real temporary local file and m365_graph_bridge's existing mock upload logic (which validates the local file actually exists even in mock mode).

## Processing Logic

`test_run_uploads_real_file` -- writes a real file into a `tempfile.TemporaryDirectory()`, runs `run()` against it, and asserts `success` is `True` and `item_id` starts with `item_`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[upload_m365_file]] itself is already mock-mode.
