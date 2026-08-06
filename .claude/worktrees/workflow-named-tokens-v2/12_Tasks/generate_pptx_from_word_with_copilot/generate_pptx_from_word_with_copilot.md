---
tool_id: 'generate_pptx_from_word_with_copilot'
title: 'M365 PowerPoint Copilot'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/copilot, scope/powerpoint, scope/word]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# generate-pptx-from-word-with-copilot

> **Status:** Active. Requires a setting (`word_file_path`) before running — a Task, not a Process. **Classified as a Copilot connection, not plain M365** — see below.

## Purpose

Has M365 Copilot generate/populate a PowerPoint presentation using a Word
file — mirrors Microsoft 365 Copilot's real "Create presentation from
file" feature. Mock-mode until an Azure AD app registration exists (see
[[m365_graph_bridge]]).

**Classification note:** unlike the other M365 Tasks (tagged `model: "m365"`,
classification-neutral), this one is tagged `model: "copilot"` in
`server.py`'s `TOOL_MODELS` — because it specifically invokes Copilot, per
the decision that M365 functions only affect a workflow's classification
ceiling when they touch Copilot.

**Honest limitation:** there is no mock-able AI generation API, so this
performs a straightforward mechanical Word → PowerPoint conversion (every
5 non-empty paragraphs becomes one slide, clearly labeled
`[MOCK Copilot-generated]`) rather than genuine AI restructuring or
summarization. Swap in a real Copilot API call inside
`m365_graph_bridge.generate_pptx_from_word()` once one exists — nothing
else here needs to change.

## Input

One JSON payload, positional CLI arg:
`{"word_file_path": "...", "output_dir": "...", "filename": "..."}`.
`output_dir`/`filename` are optional.

## Processing Logic

Imports and calls `generate_pptx_from_word()` directly from
`14_Adapters/m365_graph_bridge/m365_graph_bridge.py` (same Python
environment, no subprocess) — reads the Word file's paragraphs via
`python-docx`, groups them into slides via `python-pptx`.

## Output

`{"success": true, "file_path": "...", "slide_count": N}`.

## Notes for AI reuse

Pairs with [[download_m365_file]] (get the Word file from OneDrive first)
and [[upload_m365_file]] (push the generated `.pptx` back).
