---
tool_id: 'test_list_copilot_agents'
title: 'List Copilot Agents Tests'
classification: '05_Processes'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/03-process, tier/zero-input, function/testing, scope/agents, connects/list-copilot-agents]
---

# test-list-copilot-agents

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_copilot_agents.py`).

## Purpose

Confirms [[list_copilot_agents]]'s `run()` handles both a successful agent list and a browser-automation failure correctly, without ever launching a real browser.

## Processing Logic

* `test_run_returns_agents` -- patches `list_agents` to return a fake agent list; confirms `run()` reports success and passes the fake data through.
* `test_run_handles_browser_error` -- patches `list_agents` to raise (simulating no signed-in session); confirms `run()` catches it and reports failure rather than crashing.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Always mocks `list_agents` via `unittest.mock.patch.object` -- never calls the real Playwright browser automation, since [[list_copilot_agents]]'s own docs warn against running that speculatively in automated tests.
