---
tool_id: 'webscraper'
title: 'Web Scraper'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/user-input, function/ingestion, scope/web]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# webscraper

> **Status:** Active. User-configured utility — crawls a website starting from a given URL and indexes page content into `cortex_scrape.db`.

## Purpose

Crawls a website breadth-first starting from a seed URL, staying on the same hostname, and stores each visited page's title, text content, and outgoing-link count. Useful for building a searchable local record of a site's content without repeatedly re-fetching it live.

## Input

Three positional arguments (supplied via the popup's fields, or directly through the generic execute call):

1. `url` — the seed URL to start crawling from.
2. `max_folders` — cap on the number of distinct URL "folders" (first path segment, e.g. `/docs/...` vs `/blog/...`) the crawl will discover. Pages in already-seen folders keep getting crawled after the cap is hit; only *new* folders stop being queued.
3. `max_files` — cap on the total number of pages scanned, across all folders.

## Processing Logic

1. Read `robots.txt` for the target site and skip any URL it disallows.
2. Breadth-first crawl from the seed URL: fetch a page, extract its `<title>`, visible text (scripts/styles stripped), and outgoing links.
3. Only follow links on the exact same hostname as the seed URL.
4. Queue newly discovered links only if their folder is already known, or the folder cap hasn't been reached yet.
5. Pause briefly between requests (courtesy delay, not configurable).
6. Insert one `web_scrape_data` row per page scanned, and update the run's `web_scrape_jobs` row with final counts/status.

## Output

* `cortex_scrape.db` (separate from `cortex.db`, see `00_System/cortex_database.py`):
  * `web_scrape_jobs` — one row per run (seed URL, caps, status, counts, timestamps).
  * `web_scrape_data` — one row per page scanned (url, title, content, links_found).
