---
tool_id: 'cortex_database'
title: 'Cortex Auxiliary Database'
classification: '00_System_Core'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/schema-management, scope/cortex-db, connects/webscraper]
---

# cortex-database

> **Status:** Active. Both an importable module (`get_db_connection`, `initialize_database`) and a runnable script (`python cortex_database.py` re-applies the schema and exits).

## Purpose

Owns a second, separate SQLite database (`cortex.db`, next to [[database|brain_state.db]]) for data that doesn't belong in the main Workbrain database -- currently just web-scraped page content. Kept as its own file since scraped content can grow large and has nothing to do with Workbrain's trade/exam/contact records.

## Processing Logic

### `get_db_connection() -> sqlite3.Connection`

Opens `cortex.db` (created next to this file if it doesn't exist yet) with `row_factory = sqlite3.Row`.

### `initialize_database() -> None`

Idempotent, safe to call repeatedly. Creates (via `CREATE TABLE IF NOT EXISTS`):

* `web_scrape_jobs` -- one row per scraper run: seed URL, limits, progress counters, status, start/finish timestamps.
* `web_scrape_data` -- one row per page actually visited, `REFERENCES web_scrape_jobs(id) ON DELETE CASCADE`, unique on `(job_id, url)` so re-scanning the same page in one job updates rather than duplicates.

Plus two indexes (`job_id`, `url`) for the lookups `webscraper.py` actually does.

## Output

The live schema inside `cortex.db` (gitignored, never checked in). Console message on direct run only implicitly (no explicit print statement here, unlike [[database]]).

## Notes for AI reuse

The only current consumer is `12_Tasks/webscraper/webscraper.py`, which imports `get_db_connection`/`initialize_database` directly (`from cortex_database import ...`) -- not through [[server]] or [[core_router]]. If a second tool ever needs to write scraped/auxiliary data, it should import this same module rather than opening its own SQLite connection to a third file.
