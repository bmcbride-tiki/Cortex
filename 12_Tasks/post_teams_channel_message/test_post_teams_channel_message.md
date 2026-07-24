---
tool_id: 'test_post_teams_channel_message'
title: 'Post Teams Channel Message Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/teams, connects/post-teams-channel-message]
---

# test-post-teams-channel-message

> **Status:** Active. Runnable both via `pytest` and directly (`python test_post_teams_channel_message.py`).

## Purpose

Confirms [[post_teams_channel_message]]'s `run()` returns a successful, "posted (mock)" result, using m365_graph_bridge's existing mock data.

## Processing Logic

`test_run_posts_message` -- calls `run()` directly and asserts `success` is `True` and `status` equals `"posted (mock)"`.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end rather than mocking anything, since [[post_teams_channel_message]] itself is already mock-mode.
