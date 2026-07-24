---
tool_id: 'enterprise_adapters'
title: 'Enterprise File Adapters'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/data-ingestion, scope/enterprise-adapters, connects/workflow-schema, connects/auth, connects/canvas-parser]
---

# enterprise-adapters

> **Status:** Active, partially mocked. No `__main__` block. Imported by `canvas_parser.py`/`sandbox_smoke_test.py`.

## Purpose

Translates a raw API response from Microsoft Graph (OneDrive/SharePoint) or Google Drive into Cortex's standard `FileReference` shape (see [[workflow_schema]]), so the rest of the app never has to know or care whether a file came from M365 or Google.

## Processing Logic

### `M365OneDriveAdapter.ingest_drive_item(graph_item_response, internal_vault_uri) -> FileReference`

Pure data mapper -- no network call. Reshapes a Graph `driveItem` JSON dict into a `FileReference`, pulling `eTag`, `createdBy`, and `size` into `metadata`.

### `M365OneDriveAdapter.fetch_remote_metadata_with_retry(item_id, auth_references) -> Dict`

The one method that actually "talks" to an external service -- wrapped in `tenacity`'s `@retry(wait_random_exponential, stop_after_attempt(3))` so a transient network hiccup or enterprise rate limit (HTTP 429/503) gets retried before failing the whole workflow step. Calls [[auth]]'s `get_m365_access_token` for the bearer token. Currently returns a hardcoded, clearly-fake response rather than a live HTTP call (see the inline comment marking where a real `httpx.get(...)` would go), consistent with the project's mock-mode stage.

### `GoogleDriveAdapter.ingest_drive_file(gdrive_file_response, internal_vault_uri) -> FileReference`

Same pure-mapper pattern for a Google Drive v3 API file resource.

## Output

`FileReference` instances, fed into a `WorkflowInputData.files` list.

## Notes for AI reuse

When real Graph/Drive API calls are wired up, only `fetch_remote_metadata_with_retry`'s body needs to change (swap the hardcoded dict for a real `httpx` call using the token from [[auth]]) -- the retry/backoff wrapper and the ingest mappers are already correct and don't need touching.
