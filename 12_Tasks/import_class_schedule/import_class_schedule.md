---
tool_id: 'import_class_schedule'
title: 'Import Class Schedule Catalogue Scraper'
classification: '06_Tasks'
data_policy: 'public'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/single-input, function/ingestion, scope/class-schedules]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# import-class-schedule

> **Status:** Active. Tier 1.1 single-input utility — scrapes the Alberta Tradesecrets training catalogue for a given school year and registers class schedule data.

## Purpose

Automates the collection of classroom instruction schedules from the Alberta Apprenticeship and Industry Training "Training Catalogue" (`tradesecrets.alberta.ca`). For a given school year, it walks every trade in the catalogue, pulls each Training Provider's campus-level class schedule, and normalizes the results into JSON and `brain_state.db`.

## Input

* **School year**, format `YYYY-YYYY` (e.g. `2026-2027`), supplied either as a CLI argument (`python import_class_schedule.py 2026-2027`) or via interactive prompt if omitted. The first year of the pair maps to the site's `Year` query parameter (e.g. `2026-2027` -> `Year=2026`).

## Processing Logic

1. Fetch the base training catalogue page and extract every trade's name and internal `Trade` code from its year-selector links. Trades marked "Temporarily Unavailable" (no catalogue link at all) are skipped.
2. For each trade, request `training-catalogue/?Trade={code}&Year={start_year}`.
3. Walk the page's `<h1>` Training Provider headings. Between one heading and the next, track the current **Campus** name (parsed from the info table's linked heading) and parse each `class-schedule` table's data rows for **Period**, **Class Date**, and **Class Code**, resolving column positions from the table's own header row rather than hard-coded indexes.
4. Split the **Class Date** range (e.g. `August 20, 2026 - May 11, 2027`) into a `start_date` and `end_date`, normalized to ISO `YYYY-MM-DD`.
5. Write all collected records to `output/{school_year}.json`.
6. Bulk `INSERT OR REPLACE` the records into the `class_schedules` table in `brain_state.db`, keyed on `(class_code, trade_code, school_year)` so re-runs are idempotent. Note that a single `class_code` can legitimately appear under more than one trade — some trades (e.g. Heavy Equipment Technician and its sub-specializations) share the same physical class session and class code, so the key includes `trade_code` rather than treating `class_code` alone as unique.

## Output

* `output/{school_year}.json` — flat list of records: `school_year`, `trade`, `trade_code`, `training_provider`, `campus`, `period`, `class_code`, `start_date`, `end_date`.
* `brain_state.db` table `class_schedules` (see `00_System/database.py`) with the same fields.
