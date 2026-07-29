---
tool_id: 'test_ask_copilot_agent'
title: 'Ask Copilot Agent Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/copilot, scope/agents, connects/ask-copilot-agent]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-ask-copilot-agent

> **Status:** Active. Runnable both via `pytest` and directly (`python test_ask_copilot_agent.py`).

## Purpose

Confirms [[ask_copilot_agent]] rejects a missing `agent_name` or `prompt` without touching the browser, and that a mocked agent call returns its response correctly.

## Processing Logic

* `test_missing_agent_name_fails_without_touching_browser`
* `test_missing_prompt_fails_without_touching_browser`
* `test_run_returns_response` -- patches `ask_agent` to a fake response and confirms it passes through.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Always mocks the underlying Copilot call -- never launches a real browser, since [[ask_copilot_agent]] performs real (non-mocked) Playwright automation.
