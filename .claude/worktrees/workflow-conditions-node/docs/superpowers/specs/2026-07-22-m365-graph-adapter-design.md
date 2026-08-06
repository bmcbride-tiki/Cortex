# M365/Graph Adapter, Power BI, PowerPoint Support — Design Spec

**Date:** 2026-07-22
**Status:** Approved by user, implementing directly

## Background

Extends the Workflow Builder with a Microsoft 365 connectivity layer (Azure
AD/Entra ID + Microsoft Graph), mirroring what Power Automate offers for
M365 desktop/cloud apps. No Azure AD app registration exists yet, so this
is mock-mode-first, same pattern as `claude_bridge`/`chatgpt_bridge`/
`notebooklm_bridge`. First-pass scope is Word/Excel/PowerPoint (per user
direction: "we will do all of these but start with Word, Excel, PowerPoint
as the baseline") — Outlook/Teams/SharePoint/Calendar/Users are future
sub-projects.

Research finding (see conversation): Power BI has a real, documented REST
API (dataset refresh, list reports/datasets) using the same Azure AD/MSAL
auth as Graph. Power Query itself has no standalone automation API — the
only way to run a Power Query transformation programmatically is via a
Power BI dataset refresh or an Excel workbook refresh, both already covered
by adapter actions below. Power BI therefore folds into this same adapter
rather than getting its own.

## 1. New adapter: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`

Same CLI contract as every other adapter (one JSON payload arg in, one JSON
line out), `MOCK_MODE` env-toggle (default on, `M365_MOCK_MODE`). Real
integration later: MSAL for auth (tenant ID/client ID/secret or cert) +
either the `msgraph-sdk` Python package or direct REST calls to
`https://graph.microsoft.com/v1.0/...` and
`https://api.powerbi.com/v1.0/myorg/...`.

### Actions

* **`list_files`** — params: `folder_path`. Mock: returns a small
  realistic-shaped file listing (`name`, `item_id`, `size`, `web_url`).
* **`download_file`** — params: `file_path`, `local_output_dir`. Mock:
  still validates `local_output_dir` is creatable and writes a small
  placeholder file there (realistic side effect, not just a fake response)
  so downstream nodes (`import_from_word`, etc.) have something real to
  chain onto.
* **`upload_file`** — params: `local_path`, `destination_path`. Mock: still
  validates `local_path` is a real, existing file (same "realistic data
  contracts" principle as `notebooklm_bridge.upload_sources`) before
  simulating the upload.
* **`get_excel_range`** — params: `file_path`, `worksheet`, `range_address`.
  Mock: returns a small placeholder 2D array of cell values (mirrors
  Graph's real Workbook API response shape).
* **`set_excel_range`** — params: `file_path`, `worksheet`, `range_address`,
  `values`. Mock: echoes back what would have been written.
* **`refresh_powerbi_dataset`** — params: `dataset_id`. Mock: returns a
  simulated refresh request id + status.
* **`list_powerbi_reports`** — params: `workspace_id` (optional). Mock:
  returns a small realistic-shaped report listing.

`.md` doc + `test_m365_graph_bridge.py` follow the established adapter
convention.

## 2. Word/Excel content: reuse, don't rebuild

No new Word/Excel parsing code. `import_from_word`/`export_to_word`
(python-docx) and this project's existing `openpyxl` usage already cover
content-level read/write. The new M365 nodes only get files in and out of
OneDrive/SharePoint; a workflow composes `M365: Download File` ->
`Import from Word` -> ... -> `M365: Upload File` to work with a Word doc
that lives in OneDrive, for example.

## 3. New Function: PowerPoint (genuinely missing today)

`13_Functions/read_powerpoint/` and `13_Functions/write_powerpoint/`,
using `python-pptx` (new dependency — added to `requirements.txt`),
mirroring `import_from_word`/`export_to_word`'s shape exactly (JSON-payload
CLI arg, `.md`, test):

* **`read_powerpoint`** — params: `file_path`. Extracts all text frames
  from every slide, returns as text (one line per text run, slides
  separated by a `--- Slide N ---` marker for readability).
* **`write_powerpoint`** — params: `text`, `output_dir`, `filename`.
  Creates one slide per double-newline-separated block of `text` (title +
  body layout), writes a new `.pptx`.

## 4. Engine wiring (`workflow_engine.py`)

7 new helper methods (`_m365_list_files`, `_m365_download_file`,
`_m365_upload_file`, `_m365_excel_get_range`, `_m365_excel_set_range`,
`_powerbi_refresh_dataset`, `_powerbi_list_reports`), each with the
established dry-run/real-dispatch/`_parse_bridge_json` shape, dispatching
via `execute_app_logic("08_Adapters", "m365_graph_bridge", [payload])`.
7 matching `function_m365_*`/`function_powerbi_*` tool_id branches in
`_execute_function_node`.

## 5. Classification (`model_classifications.py` — unchanged file, deliberate non-entry)

M365/Graph nodes are tagged `model: "m365"` (for palette-toggle filtering)
but `"m365"` is **not** added to `MODEL_CLASSIFICATIONS`. Per user
decision: M365 functions don't change or impact a workflow's classification
ceiling unless they specifically interact with Copilot (none of the
baseline actions do) — `classification_ceiling()` already silently skips
any model key not present in `MODEL_CLASSIFICATIONS`, so this is a
zero-code side effect of simply not adding an entry, not a special case
that needs its own logic.

## 6. Workflow Builder UI

* Model toggle row gains "M365", positioned **before** Copilot, default
  **on** (per user instruction) — Copilot stays default on too; every
  other model stays default off. Requires a small restructure: toggle
  rendering currently iterates `Object.keys(model_classifications.models)`
  (the classification map); since `m365` is deliberately absent from that
  map, toggle order/defaults move to a new explicit `toggle_order` list
  (`["m365", "copilot", "gemini", "notebooklm", "claude", "chatgpt"]`) sent
  alongside `model_classifications` in the node-registry response.
* New `FUNCTION_FIELD_SCHEMAS` entries for the 7 new engine functions.
* New `ARG_FIELD_SCHEMAS` entries for the raw `m365_graph_bridge` adapter
  node and for `read_powerpoint`/`write_powerpoint`.

## Explicitly Out of Scope

* Real Azure AD app registration / MSAL wiring (mock-mode only, per user
  decision).
* Outlook, Teams, SharePoint (beyond raw file list/download/upload),
  Calendar, Users Graph endpoints — future sub-projects, per user's
  explicit "start with Word, Excel, PowerPoint" direction.
* A standalone Power Query automation path — confirmed not to exist;
  Power BI dataset refresh / Excel workbook refresh are the real
  mechanisms, both covered above.
