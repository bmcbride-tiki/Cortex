---
tool_id: 'test_list_m365_teams'
title: 'List M365 Teams Tests'
classification: '05_Processes'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/03-process, tier/zero-input, function/testing, scope/teams, connects/list-m365-teams]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-list-m365-teams

> **Status:** Active. Runnable both via `pytest` and directly (`python test_list_m365_teams.py`).

## Purpose

Confirms [[list_m365_teams]]'s `run()` returns a successful result with at least one team, using `m365_graph_bridge`'s existing mock data -- no real Microsoft account needed.

## Processing Logic

`test_run_returns_teams` -- calls `ListM365Teams().run()` directly (no mocking needed, since the underlying adapter is already mock-mode) and asserts `success` is `True` and `teams` is non-empty.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

This test calls the real `run()` end to end rather than mocking anything, since [[list_m365_teams]] itself is already mock-mode (no live Azure AD call happens). Once real Graph API access is wired up, this test would need its own mock of the live HTTP call to stay side-effect-free.
