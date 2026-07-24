---
tool_id: 'test_import_documents'
title: 'Import Documents Tests'
classification: '06_Tasks'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/test, domain/04-task, tier/zero-input, function/testing, scope/documents, connects/import-documents]
---

# test-import-documents

> **Status:** Active. Runnable both via `pytest` and directly (`python test_import_documents.py`).

## Purpose

Checks [[import_documents]]'s text-parsing helpers in isolation (label extraction, trade-list splitting, filename-fallback metadata, and body-vs-filename precedence) -- does not touch the filesystem/database side of a real `run()`.

## Processing Logic

* `test_extract_labeled_fields` -- pulls `Label: Value` pairs out of raw text, ignoring lines without a colon.
* `test_split_trades` -- splits a comma/semicolon-separated trade string into a clean list.
* `test_filename_fallback_used_when_body_missing_fields` -- confirms filename-derived title/date are used when the body has no matching labels.
* `test_body_field_overrides_filename` -- confirms a real labeled field in the body wins over the filename fallback.

## Output

Passes silently (or prints a pass message when run directly); a failed `assert` raises with a traceback.

## Notes for AI reuse

Deliberately unit-level -- doesn't exercise `run()`'s real inbox-scan/DB-write path, so it stays fast and side-effect-free. A future integration test would need a real `01_inbox/documents/` fixture and a throwaway database.
