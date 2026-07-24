---
tool_id: 'import_marks_correlation'
title: 'Import Marks Correlation'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/zero-input, function/ingestion, scope/exam-metrics]
---

# import-marks-correlation

> **Status:** Active. Tier 1.2 user-configured utility — scans folders recursively, resolves chronological rewrites, and registers bulk training data.

## Purpose

Automates the parsing, validation, and database mapping of consolidated "Marks Correlation Reports". It extracts periods from exam names, chronologically processes student rewrites, and maintains precise historical records.

## Processing Logic

1. Scan `01_inbox/reports/` for any outstanding `.xlsx` workbook files.
2. For each workbook, parse `Section Scores Details` and clean out metadata footer rows (by filtering out rows with blank/null fields).
3. Extract the training **Period** from the second section of the `/`-delimited `Exam Name`.
4. Chronologically sort overall exam dates per student ID (`AITID`) per class code:
   * **First Date (Chronological):** Marked as baseline session (`is_rewrite = 0`).
   * **Subsequent Dates:** Marked as exam rewrite attempts (`is_rewrite = 1`).
5. Bulk insert records transactionally into the relational schema.
6. Safely archive completed workbooks in `01_inbox/processed/`.