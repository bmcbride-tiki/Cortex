---
tool_id: 'word_to_excel_exam'
title: 'Word To Excel Exam'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/single-input, function/transform, scope/exam-questions]
---

# word-to-excel-exam

> **Status:** Active. Tier 1.1 single-input utility — converts a Word exam question bank into the CE item-import Excel layout.

## Purpose

Converts exam question banks authored in Word (three known source formats — AI Generated & Validated, AI-2 (Rob), and CE Formatted hierarchical tables) into a flat Excel workbook matching the `item_import_template.xlsx` column layout used for question bank imports.

## Input

* **Source file**: a `.docx` question bank, supplied as a CLI argument (`python word_to_excel_exam.py <source_file_path> <format>`).
* **Format**: one of `ai` (AI Generated & Validated, default), `ai2` (AI-2 / Rob), or `ce` (CE Formatted hierarchical tables).
* Requires `item_import_template.xlsx` to be present in the tool's own folder — this is the locked column layout every conversion writes into. (Note: this template was originally shipped as a legacy binary `item_import_template.xls`, which `openpyxl` cannot open; it was converted to `.xlsx` once to unblock this pipeline.)

## Processing Logic

1. Select the parser for the given format:
   * `ai` — walks paragraphs, matching `Item N` markers, question stems, `A)`–`D)` options, `Correct Answer:`/`Answer:`/`Key:` lines, and `Difficulty`/`Rationale` metadata lines.
   * `ai2` — walks paragraphs at the run level to detect **bold** answer options, inferring the correct option from bold formatting rather than an explicit answer line.
   * `ce` — walks nested Word tables, extracting the item number, question stem, and A–D options (with the correct option flagged by an asterisk) from each item's table structure.
2. Discard any parsed record missing a question stem or all four options.
3. Duplicate `item_import_template.xlsx` into `output/` as `{current user}-Question Importer - {MM-DD-YYYY}.xlsx` (auto-incrementing on name collision).
4. Locate the template's `QuestionText` header column to find the first data row, then write each record's title/stem/options/correct-answer into the corresponding columns.

## Output

* `output/{user}-Question Importer - {date}.xlsx` — one row per extracted question, ready for CE item import.
