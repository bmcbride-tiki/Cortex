---
tool_id: 'test_generate_pptx_from_word_with_copilot'
title: 'Generate PPTX from Word with Copilot Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/powerpoint, scope/word, connects/generate-pptx-from-word-with-copilot]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# test-generate-pptx-from-word-with-copilot

> **Status:** Active. Runnable both via `pytest` and directly (`python test_generate_pptx_from_word_with_copilot.py`).

## Purpose

Confirms [[generate_pptx_from_word_with_copilot]]'s `run()` produces a real `.pptx` file on disk from a small generated `.docx` source, using m365_graph_bridge's existing mock conversion logic.

## Processing Logic

`test_run_generates_pptx` -- generates a throwaway source `.docx` via `python-docx`, runs the real conversion against a real `tempfile.TemporaryDirectory()`, and asserts the returned `file_path` exists.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Calls the real `run()` end to end (no mocking) -- this is what proves the mock mechanical conversion genuinely produces an openable `.pptx`, not just a plausible-looking dict.
