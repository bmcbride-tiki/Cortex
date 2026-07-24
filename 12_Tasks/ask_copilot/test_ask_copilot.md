---
tool_id: 'test_ask_copilot'
title: 'Ask Copilot Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/copilot, connects/ask-copilot]
---

# test-ask-copilot

> **Status:** Active. Runnable both via `pytest` and directly (`python test_ask_copilot.py`).

## Purpose

Confirms [[ask_copilot]] rejects an empty prompt without touching the browser, and that a mocked Copilot call returns its response correctly.

## Processing Logic

* `test_missing_prompt_fails_without_touching_browser` -- empty `prompt` returns `success: false` immediately.
* `test_run_returns_response` -- patches `_ask_copilot` to a fake response and confirms it passes through.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Always mocks the underlying Copilot call -- never launches a real browser, since [[ask_copilot]] performs real (non-mocked) Playwright automation.
