---
tool_id: 'm365_graph_bridge'
title: 'M365 Graph Bridge'
classification: '00_System_Core/adapters'
data_policy: 'internal'
execution_engine: 'mock'
tags: [type/module, domain/system-core, tier/zero-input, function/mock-adapter, scope/m365, scope/graph, scope/powerbi, scope/outlook, scope/teams, scope/sharepoint, scope/lists, scope/onenote, scope/onedrive, connects/core-router, connects/workflow-engine]
---

# m365-graph-bridge

> **Status:** Mock-only. No Azure AD/Entra ID app registration exists for this project yet, so every action simulates a realistic response rather than calling the real Microsoft Graph or Power BI REST APIs.

## Purpose

Lets [[workflow_engine]] connect a workflow to Microsoft 365: OneDrive/
SharePoint file access and Excel's cell-level Workbook API, Outlook
(send/list mail, list/create calendar events), Teams (list teams/
channels, post channel messages, list/send chat messages), SharePoint
Online sites (discover/target a site), Microsoft Lists (read/write
structured list items within a site), OneNote (notebooks/pages), and
extra OneDrive actions (recent files, sharing links) via Microsoft Graph,
plus Power BI dataset refresh/report listing via the Power BI REST API —
all share the same Azure AD app registration and MSAL auth flow, so they
live in one adapter rather than several.

**Power Query has no standalone public automation API.** The real way to
"run" a Power Query transformation programmatically is by triggering a
Power BI dataset refresh (`refresh_powerbi_dataset`) or an Excel workbook
refresh — there is no separate integration surface to build for Power
Query itself.

**Word/Excel/PowerPoint content is not parsed here.** This adapter only
gets files in and out of OneDrive/SharePoint (`download_file`/
`upload_file`); content-level reading/writing composes with the existing
tools that already do that well: `13_Functions/import_from_word` /
`export_to_word` (Word), this project's existing `openpyxl` usage (Excel
files as a whole), `get_excel_range`/`set_excel_range` below (Excel
cell-level), and the new `13_Functions/read_powerpoint`/`write_powerpoint`.

## Processing Logic

### `MOCK_MODE` (env var `M365_MOCK_MODE`, default on)

With `MOCK_MODE` off and no real backend wired in, every action fails
clearly (`NOT_CONFIGURED_MESSAGE`) instead of pretending to succeed.

### Actions (JSON payload, positional CLI arg)

* **`list_files`** — params: `folder_path`. Returns a realistic-shaped
  file listing (`name`, `item_id`, `size`, `web_url`).
* **`download_file`** — params: `file_path`, `local_output_dir`. Still
  writes a real placeholder file to `local_output_dir` even in mock mode,
  so a downstream real parsing step has something real to chain onto.
* **`upload_file`** — params: `local_path`, `destination_path`. Still
  validates `local_path` is a real, existing file before simulating the
  upload — a typo'd path surfaces immediately.
* **`get_excel_range`** — params: `file_path`, `worksheet`,
  `range_address`. Returns a realistic-shaped 2D array of cell values
  (mirrors Graph's real Workbook API response).
* **`set_excel_range`** — params: `file_path`, `worksheet`,
  `range_address`, `values`. Echoes back what would have been written.
* **`refresh_powerbi_dataset`** — params: `dataset_id`. Returns a
  simulated refresh request id + status.
* **`list_powerbi_reports`** — params: `workspace_id` (optional). Returns
  a realistic-shaped report listing.
* **`send_mail`** — params: `to` (comma-separated for multiple), `subject`,
  `body`. Returns a simulated `message_id`.
* **`list_messages`** — params: `folder` (default `inbox`), `top` (max
  count, default 10). Returns a realistic-shaped inbox listing.
* **`list_calendar_events`** — params: `start_date`, `end_date` (both
  optional). Returns a realistic-shaped event listing.
* **`create_calendar_event`** — params: `subject`, `start`, `end`,
  `attendees` (comma-separated, optional). Returns a simulated `event_id`.
* **`list_teams`** — no params. Returns the teams the (mock) signed-in
  user belongs to.
* **`list_channels`** — params: `team_id`. Returns that team's channels.
* **`post_channel_message`** — params: `team_id`, `channel_id`, `message`.
  Returns a simulated `message_id`.
* **`list_chat_messages`** — params: `chat_id`. Returns a realistic-shaped
  1:1/group chat message listing.
* **`send_chat_message`** — params: `chat_id`, `message`. Returns a
  simulated `message_id`.
* **`search_messages`** — params: `query` (keyword/topic), `sender`
  (address filter), `folder`, `top` (at least one of `query`/`sender`
  required). Unlike `list_messages`' plain folder listing, filters by
  sender and echoes the query into each match's preview.
* **`generate_pptx_from_word`** — params: `word_file_path`, `output_dir`,
  `filename`. **Classified as a Copilot connection, not plain M365** (see
  its Task wrapper's `model="copilot"` tag) — represents M365 Copilot's
  "Create presentation from file" feature. Honest limitation: there is no
  mock-able AI generation API, so this performs a straightforward
  mechanical Word → PowerPoint conversion (every 5 non-empty paragraphs
  becomes one slide) rather than genuine AI restructuring/summarization.
  Swap in a real Copilot API call here once one exists.
* **`list_sharepoint_sites`** — params: `query` (optional filter). Returns
  a realistic-shaped site listing.
* **`get_sharepoint_site`** — params: `site_path`. Returns a single site's
  details.
* **`list_sharepoint_lists`** — params: `site_id`. Returns that site's
  Microsoft Lists.
* **`list_sharepoint_list_items`** — params: `site_id`, `list_id`. Returns
  a list's items (each with a `fields` object of column values).
* **`create_sharepoint_list_item`** — params: `site_id`, `list_id`,
  `fields` (JSON object of column values). Returns a simulated `item_id`.
* **`list_onenote_notebooks`** — no params. Returns the signed-in user's
  OneNote notebooks.
* **`list_onenote_pages`** — params: `notebook_id`. Returns that
  notebook's pages.
* **`get_onenote_page_content`** — params: `page_id`. Returns the page's
  content as HTML (Graph's real OneNote pages are HTML-based).
* **`create_onenote_page`** — params: `section_id`, `title`, `content`.
  Returns a simulated `page_id`.
* **`list_recent_onedrive_files`** — no params. Returns recently
  modified/accessed files.
* **`create_onedrive_sharing_link`** — params: `file_path`. Returns a
  simulated share URL.

## Output

One JSON line on stdout per invocation: `{"success": true, ...}` or
`{"success": false, "response": "<error>"}` (non-zero exit code on
failure) — same contract as every other adapter.

## Notes for AI reuse

* Wiring in real access: register an Azure AD app (tenant ID, client
  ID, client secret or certificate), consent the needed Graph (`Files.*`,
  `Sites.*`) and Power BI (`Dataset.*`, `Report.*`) API permissions, then
  use `msal` for token acquisition + either the `msgraph-sdk` package or
  direct REST calls inside each action function. Nothing else (the CLI
  contract, `main()`'s dispatch) needs to change.
* M365/Graph nodes are tagged `model: "m365"` in the Workflow Builder's
  node registry for palette-toggle filtering, but `"m365"` is deliberately
  **not** in `model_classifications.py`'s `MODEL_CLASSIFICATIONS` map — per
  explicit decision, M365 functions don't change a workflow's
  classification ceiling unless they specifically interact with Copilot.

## Required dependencies

None beyond the Python standard library while mock-mode is active. A real
integration would add `msal` and `msgraph-sdk` to `requirements.txt`.
