---
tool_id: 'curriculum_guide_to_tos'
title: 'Curriculum Guide To TOS'
classification: '06_Tasks'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/task, domain/04-task, tier/single-input, function/transform, scope/curriculum-guides]
---

# curriculum-guide-to-tos

> **Status:** Active. Tier 1.1 single-input utility — converts a Curriculum Guide Word document into a populated TOS Excel workbook.

## Purpose

Converts an Alberta-style Curriculum Guide `.docx` (periods, sections, and topics with their hours/percentages) into a TOS (Table of Specifications) Excel workbook, using `TOS_Template_May_2026.xlsx` as the locked template. Ported from a standalone PySide6 desktop tool (the "BluePrint" launcher) into a headless CLI script; the GUI, background `QThread` worker, and file-dialog chrome were dropped since workbrain has no GUI runtime — `core_router.py` runs every task as a subprocess and captures its printed output.

## Input

* **Curriculum Guide file**: a `.docx` path, supplied as a CLI argument (`python curriculum_guide_to_tos.py <curriculum_guide.docx> [trade_name_override] [exam_questions]`) or via interactive prompt if omitted. Legacy `.doc` files are rejected with a clear message (python-docx cannot open the old binary format) — save as `.docx` first.
* **Trade name override** (optional, 2nd argument): overrides the trade name the parser would otherwise guess from the document's first paragraphs. Defaults to the guessed name.
* **Exam questions** (optional, 3rd argument): written into each period sheet's header. Defaults to `100`.
* Requires `TOS_Template_May_2026.xlsx` to be present in the tool's own folder — this is the locked workbook layout every conversion copies and writes into.
* **From Cortex**: has a dedicated popup (`templates/popup/curriculum_guide_to_tos.html`, registered in `tasks.html`) with a real browser file picker (accepts `.doc`/`.docx`) plus optional trade name/exam questions fields. Submitting it posts to `POST /api/uploads/curriculum-guide-to-tos`, which saves the upload into the tool's own `incoming/` folder and dispatches this script through `core_router.py`.

## Processing Logic

1. Walk the Curriculum Guide's paragraphs and tables in document order, detecting `PERIOD {word} COURSE CONTENT` headings, `SECTION {word}:` headings, and `Topic {letter}.` tables, pulling hours/percentages from nearby summary tables and topic tables.
2. Duplicate `TOS_Template_May_2026.xlsx` into `output/` as `{current user} - Curriculum Guide to TOS - {MM-DD-YYYY}.xlsx` (auto-incrementing on name collision).
3. For each parsed period, match it to a workbook sheet (by period number or name) and locate that sheet's section blocks — rows starting with `Section`/`Core Competence` down to the next `Subtotals` row.
4. Write the trade name, period hours, exam question count, and each section's title/hours/percentage plus its topic rows (letter, name, hours, percentage) into the matching block. If a section has more topics than the template has rows for, the extras are skipped and logged as a warning rather than stopping the conversion.
5. Replace any literal `[Trade Name]` placeholder text found elsewhere in the workbook.
6. Add a `CG to TOS Summary` sheet listing every period/section/topic that was written, for review.

## Output

* `99_Outbox/curriculum_guide_to_tos/{user} - Curriculum Guide to TOS - {date}.xlsx` — the populated TOS workbook plus its summary sheet.
