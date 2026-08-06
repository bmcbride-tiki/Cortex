---
tool_id: 'test_download_m365_file'
title: 'Download M365 File Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/onedrive, scope/sharepoint, connects/download-m365-file]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-download-m365-file

> **Status:** Active. Runnable both via `pytest` and directly (`python test_download_m365_file.py`).

## Purpose

Confirms [[download_m365_file]]'s `run()` actually writes a local file to a temporary folder, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_writes_local_file` -- runs against a real `tempfile.TemporaryDirectory()` and asserts the returned `local_path` exists on disk.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything -- worth keeping this way since it's what proves the mock adapter really does write a placeholder file for downstream tools to chain onto.
