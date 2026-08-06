---
tool_id: 'test_list_teams_chat_messages'
title: 'List Teams Chat Messages Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/teams, connects/list-teams-chat-messages]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-list-teams-chat-messages

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_teams_chat_messages.py`).

## Purpose

Confirms [[list_teams_chat_messages]]'s `run()` returns a successful result with at least one message, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_returns_messages` -- calls `run()` directly and asserts `success` is `True` and `messages` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[list_teams_chat_messages]] itself is already mock-mode.
