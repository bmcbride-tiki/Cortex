---
tool_id: 'test_generate_copilot_image'
title: 'Generate Copilot Image Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/copilot, scope/image-generation, connects/generate-copilot-image]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-generate-copilot-image

> **Status:** Active. Runnable both via `pytest` and directly (`python test_generate_copilot_image.py`).

## Purpose

Confirms [[generate_copilot_image]] rejects a missing `prompt` or `output_dir` without touching the browser, and that a mocked image-generation call returns the file's path.

## Processing Logic

* `test_missing_prompt_fails_without_touching_browser`
* `test_missing_output_dir_fails_without_touching_browser`
* `test_run_returns_file_path` -- patches `generate_image` to a fake path and confirms it passes through.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Always mocks the underlying Copilot call -- never launches a real browser, since [[generate_copilot_image]] performs real (non-mocked) Playwright automation.
