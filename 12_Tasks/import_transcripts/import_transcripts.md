---
tool_id: 'import_transcripts'
title: 'Import Transcripts'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/ingestion, scope/transcripts]
---

# import-transcripts

> **Status:** Active. Tier 1.2 user-configured utility — scans a fixed inbox folder for meeting/transcript files, vaults the originals, and indexes their text for search.

## Purpose

Automates ingestion of raw meeting transcripts (`.txt` or `.docx`) dropped into the inbox. Each file is parsed for metadata from its filename, copied into permanent vault storage, cataloged in the database, and its full text is indexed for global search.

## Input

* `.txt` or `.docx` file(s) placed in `01_Inbox/transcripts/`. No CLI arguments — running the script processes whatever files are currently pending.
* Filenames are optionally parsed using the convention `YYYY-MM-DD_Type_Trade_Title.[ext]` (e.g. `2026-06-18_Meeting_Sheet-Metal_Apprentice-Sync.docx`). Missing segments fall back to today's date, `Internal` type, and `General` trade.

## Processing Logic

1. Scan `01_Inbox/transcripts/` for pending `.txt`/`.docx` files.
2. Extract body text — `.docx` files are read paragraph-by-paragraph plus any tables (common for Teams-exported Speaker | Time | Message transcripts); `.txt` files are read directly.
3. Parse date/type/trade/title metadata out of the filename.
4. Copy the original file into `02_vault/transcripts/` with a timestamp-suffixed filename (permanent archive, never overwritten).
5. Insert a catalog row into `transcripts_metadata` and index the extracted body text into `global_search_index`.
6. Remove the original file from the inbox once committed.

## Output

* `02_vault/transcripts/` — permanent copies of every ingested transcript file.
* `brain_state.db` tables `transcripts_metadata` and `global_search_index` (see `00_System/database.py`).
