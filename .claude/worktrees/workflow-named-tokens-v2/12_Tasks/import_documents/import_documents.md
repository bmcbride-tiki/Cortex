---
tool_id: 'import_documents'
title: 'Import Documents'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/ingestion, scope/documents]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# import-documents

> **Status:** Active. Tier 1.2 user-configured utility — scans a fixed inbox folder for DOCX/PDF reports, extracts their fields to JSONL, then loads that JSONL into the database.

## Purpose

Automates ingestion of structured reports (`.docx` or `.pdf`) dropped into
the inbox, even when their internal layout varies slightly file to file.
Each file's text is scanned for `Label: Value` lines rather than assuming a
fixed layout, written out as one JSON object per file (JSONL), and that
JSONL is then loaded into `documents_metadata` and indexed for search — so
the raw extraction step and the database load step are separate, auditable
phases.

## Input

* `.pdf` or `.docx` file(s) placed in `01_inbox/documents/`. No CLI
  arguments — running the script processes whatever files are currently
  pending. Legacy `.doc` is not supported (save as `.docx` first).
* Fields are pulled from any line in the document matching `Label: Value`
  (e.g. `Trade: Electrical, Plumbing`, `Date: 2026-01-15`). Missing
  `title`/`date` fall back to the filename convention
  `YYYY-MM-DD_Title.[ext]`, same as `import_transcripts`.

## Processing Logic

1. Scan `01_inbox/documents/` for pending `.pdf`/`.docx` files.
2. **Extract phase** (`extract_to_jsonl`) — read each file's full text
   (`.docx` via paragraphs + tables, `.pdf` via `pypdf` page text), scan it
   for `Label: Value` pairs, resolve `title`/`doc_date`/`trades` (with
   filename fallback), and write one JSON object per file to a timestamped
   `.jsonl` file in `02_vault/documents/`.
3. **Load phase** (`load_jsonl_to_db`) — read that JSONL back, archive each
   original file into `02_vault/documents/` (timestamp-suffixed, permanent),
   insert a row into `documents_metadata`, and index the full body text into
   `global_search_index` (`content_type='document'`).
4. Remove each original file from the inbox once its row is committed.

## Output

* `02_vault/documents/` — the JSONL extraction file, plus permanent copies
  of every ingested source file.
* `cortex.db` tables `documents_metadata` and `global_search_index` (see
  `00_System/database.py`).

## Known Limitations

* PDF extraction is raw page text (`pypdf`) — table cell structure isn't
  preserved. If a PDF's key data lives inside real table grids rather than
  `Label: Value` lines, it won't be captured; that would need a table-aware
  library like `pdfplumber` (not currently a project dependency).
* Trades are stored as a JSON array in one column (query with SQLite's
  `json_each(trades)`) rather than a join table — add a join table only if
  trade-scoped queries need to be fast/frequent at scale.
