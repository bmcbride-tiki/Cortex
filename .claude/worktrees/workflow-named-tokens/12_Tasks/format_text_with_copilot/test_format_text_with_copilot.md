---
tool_id: 'test_format_text_with_copilot'
title: 'Format Text with Copilot Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/copilot, connects/format-text-with-copilot]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-format-text-with-copilot

> **Status:** Active. Runnable both via `pytest` and directly (`python test_format_text_with_copilot.py`).

## Purpose

Confirms [[format_text_with_copilot]] rejects an empty `text` without touching the browser, and that a mocked Copilot call is built with a prompt containing both the input text and style notes.

## Processing Logic

* `test_missing_text_fails_without_touching_browser`
* `test_run_builds_prompt_and_returns_response` -- captures the prompt passed to a faked `ask_copilot` and checks both inputs appear in it.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Always mocks the underlying Copilot call -- never launches a real browser, since [[format_text_with_copilot]] performs real (non-mocked) Playwright automation.
