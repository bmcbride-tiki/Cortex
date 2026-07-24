---
tool_id: 'import_exam_pass_fail'
title: 'Import Exam Pass Fail'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/ingestion, scope/exam-metrics]
---

# import-exam-pass-fail

> **Status:** Active. Tier 1.2 user-configured utility — scans a fixed inbox folder for region-level pass/fail aggregate reports and registers them for trend analysis.

## Purpose

Automates the parsing and database mapping of "ATOMS Management" Exam Pass/Fail aggregate reports. It reconstructs the report's merged-cell structure into flat per-trade, per-period rows so pass/fail/no-stat counts can be tracked and correlated against class schedules and marks data.

## Input

* `.xlsx` workbook(s) placed in `01_inbox/reports/` whose filename contains `pass` or `fail` (case-insensitive). No CLI arguments — running the script simply processes whatever matching files are currently pending.

## Processing Logic

1. Scan `01_inbox/reports/` for pending `.xlsx` files matching the `pass`/`fail` filename filter.
2. Read the first sheet and skip the report's fixed 5-row header banner.
3. Slice out the relevant fixed column positions (Trade, Period, Classification, Exam Type, Exam Name, Ref/Ver, Supp, Pass, Fail, No Stat, Total).
4. Drop report-total and section-subtotal rows, then forward-fill the merged-cell groups (Trade, Period, Classification, Exam Type) so every data row is fully populated.
5. Normalize count columns to integers and bulk `INSERT OR REPLACE` into `exam_pass_fail_aggregates`.
6. Safely archive completed workbooks into `01_inbox/processed/` (timestamp-suffixed on name collision).

## Output

* `brain_state.db` table `exam_pass_fail_aggregates` (see `00_System/database.py`).
