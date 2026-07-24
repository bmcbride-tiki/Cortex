---
tool_id: 'test_list_teams_channels'
title: 'List Teams Channels Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/teams, connects/list-teams-channels]
---

# test-list-teams-channels

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_teams_channels.py`).

## Purpose

Confirms [[list_teams_channels]]'s `run()` returns a successful result with at least one channel, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_returns_channels` -- calls `run()` directly and asserts `success` is `True` and `channels` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[list_teams_channels]] itself is already mock-mode.
