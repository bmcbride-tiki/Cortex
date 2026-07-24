---
tool_id: 'list_copilot_agents'
title: 'List Copilot Agents'
classification: '05_Processes'
data_policy: 'protected'
execution_engine: 'browser_automation'
tags: [type/process, domain/03-process, tier/zero-input, function/copilot, scope/agents]
---

# list-copilot-agents

> **Status:** Active. Zero-input, click-and-run Process (like [[generate_vault_map]]) — lists the agents available to @-mention in M365 Copilot chat. **Real browser automation, not mocked** — requires a signed-in session.

## Purpose

Lists the agents available to @-mention in M365 Copilot chat (name +
description). Uses your signed-in Edge session via [[copilot_bridge]] — no
API key. Requires a completed "Initialize Session Auth" run first (see
[[copilot_bridge]]).

## Input

None. Running the script processes with no arguments.

## Processing Logic

Imports and calls `list_agents()` directly from
`14_Adapters/copilot_bridge/copilot_bridge.py` (same Python environment,
no subprocess) — a real Playwright browser automation call, not a mock.

## Output

`{"success": true, "agents": [{"name", "description"}, ...]}`.

## Notes for AI reuse

Tagged `model: "copilot"` in `server.py`'s `TOOL_MODELS`. Feed an agent
name into [[ask_copilot_agent]]. Unlike the M365/Power BI tools, this has
real side effects (launches a headless Edge session) — don't run it
speculatively in automated tests; mock `list_agents` instead.
