---
tool_id: 'copilot_prompt_engineer'
title: 'Copilot Prompt Engineer (URL-Based Prompt Test Tool)'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'browser_automation'
tags: [type/script, domain/system-core, tier/interactive, function/browser-automation, scope/m365-copilot, connects/copilot-ask]
---

# copilot-prompt-engineer

> **Status:** Active, manual/diagnostic tool -- not called by [[core_router]], [[server]], or [[workflow_engine]].

## Purpose

Tests one specific way of opening Copilot chat: baking the question directly into the web address as a `?q=<question>` parameter, instead of typing it into the chat box after the page loads. Run from a terminal, type or pass a question, and it builds the URL, prints it, then opens it in a visible automated browser and prints back Copilot's answer.

## Processing Logic

1. `generate_copilot_url(prompt_text)` -- URL-encodes the prompt (`urllib.parse.quote`) and appends it as `https://m365.cloud.microsoft/chat/?q=<encoded>`.
2. `main()` -- reads the prompt from CLI arguments (`sys.argv[1:]` joined) or an interactive `input()` prompt if none were given, builds the URL, then calls [[copilot_ask|copilot_ask.ask_copilot(target_url=..., headless=False)]] to actually drive the browser and print the response.

## Output

Console only: the generated URL, then Copilot's response text.

## Notes for AI reuse

Production ([[copilot_bridge]]) submits prompts by typing into the chat box directly rather than building a URL -- this tool exists specifically to verify the URL-parameter pre-fill approach still works as an alternative, not as the primary submission path. If Microsoft changes how `?q=` pre-filling behaves, this is the script to re-run first.
