---
tool_id: 'test_send_teams_chat_message'
title: 'Send Teams Chat Message Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/teams, connects/send-teams-chat-message]
---

# test-send-teams-chat-message

> **Status:** Active. Runnable both via `pytest` and directly (`python test_send_teams_chat_message.py`).

## Purpose

Confirms [[send_teams_chat_message]]'s `run()` returns a successful, "sent (mock)" result, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_sends_message` -- calls `run()` directly and asserts `success` is `True` and `status` equals `"sent (mock)"`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[send_teams_chat_message]] itself is already mock-mode.
