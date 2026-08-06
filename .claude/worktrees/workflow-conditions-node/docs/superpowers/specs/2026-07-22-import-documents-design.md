# Import Documents — Design Spec

**Date:** 2026-07-22
**Status:** Approved by user, ready for implementation plan

## Purpose

Add a new ingestion task, `import_documents`, that scrapes DOCX and PDF files
dropped into an inbox folder, extracts both a handful of reliable header
fields and a variable set of report-specific fields, and loads the result
into a new `documents_metadata` table in `cortex.db` so it can be joined
against other data (trades) and searched alongside transcripts.

This follows the exact shape of the existing `12_Tasks/import_transcripts`
task, extended to handle PDF input and structured-field extraction.

## Input

* `.pdf` and `.docx` files placed in `01_inbox/documents/`. No CLI arguments —
  running the script processes whatever is currently pending, same as
  `import_transcripts`.
* Legacy `.doc` is not supported (same restriction as
  `curriculum_guide_to_tos`) — user must re-save as `.docx`.

## Processing Logic

1. Scan `01_inbox/documents/` for pending `.pdf`/`.docx` files (skip
   `~$`-prefixed temp files).
2. Extract full text:
   - `.docx` — reuse the paragraph + table walking approach already in
     `import_transcripts._read_docx` (paragraphs in order, plus
     pipe-joined table rows).
   - `.pdf` — extract text per page via `pypdf.PdfReader`, joined with
     newlines. (Raw text only; pypdf does not preserve table cell
     structure. If these PDFs contain real tables that need structured
     extraction, that's a follow-up requiring a new dependency like
     `pdfplumber` — out of scope here.)
3. Scan the extracted text line-by-line for `Label: Value` style lines
   (regex: `^([A-Za-z][A-Za-z0-9 /_-]{1,40}):\s+(.+)$`), the same
   label-scanning technique already used in `curriculum_guide_to_tos.py`.
   Collect every match into a flat `{label: value}` dict — this is the
   "slightly different formats" tolerance: no fixed positions assumed.
4. Pull `title`, `doc_date`, and `trades` out of that dict (case-insensitive
   key match against common variants: `Title`/`Report Title`,
   `Date`/`Report Date`, `Trade`/`Trades`). `trades` is split on commas/`;`
   into a list. Any field not found in-body falls back to filename parsing,
   using the same `YYYY-MM-DD_Title.ext` convention as
   `import_transcripts._parse_filename`.
5. Archive the original file into `02_vault/documents/` with a
   timestamp-suffixed filename (permanent, never overwritten) — same
   pattern as the transcripts vault.
6. Insert one row into `documents_metadata` (see schema below), storing the
   full label:value dict as JSON in `extracted_fields` and the trades list
   as a JSON array in `trades`.
7. Insert the full extracted text into the existing `global_search_index`
   FTS5 table with `content_type='document'`, linked via `origin_id`.
8. Remove the original from the inbox once committed (matches
   `import_transcripts`; on error, roll back and leave the file in place).

## Schema (added to `00_System/database.py`)

```sql
CREATE TABLE IF NOT EXISTS documents_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    doc_date TEXT,
    trades TEXT NOT NULL DEFAULT '[]',
    source_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    extracted_fields TEXT NOT NULL DEFAULT '{}',
    created TEXT NOT NULL DEFAULT (datetime('now'))
);
```

* `trades` — JSON array of trade name strings. A document can list more
  than one trade; this avoids a join table since queries against it can
  use SQLite's built-in `json_each(trades)` (no new dependency).
* `extracted_fields` — JSON object of every `Label: Value` pair found in
  the document body, beyond the three promoted columns above. This is the
  “simplify the data conversion” JSON output the task exists to produce.
* No new join table for trades — add one later only if trade-scoped
  queries need to be fast/frequent at scale.

## Output

* `02_vault/documents/` — permanent copies of every ingested file.
* `cortex.db` tables `documents_metadata` and `global_search_index`.

## Explicitly Out of Scope

* Structured PDF table-cell extraction (would need `pdfplumber` or
  similar — not needed unless these PDFs' key data lives inside real
  table grids rather than `Label: Value` lines).
* A trades join table — JSON array column is sufficient for now.
* Any UI/search page for the new table — this spec covers ingestion only.
