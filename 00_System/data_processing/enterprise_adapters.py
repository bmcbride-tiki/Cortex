# =============================================================================
# enterprise_adapters.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Translates a raw API response from Microsoft Graph (OneDrive/SharePoint)
#   or Google Drive into Cortex's own standard `FileReference` shape (see
#   `workflow_schema.py`), so the rest of the app never has to know or care
#   whether a file originally came from M365 or Google -- every ingested
#   file looks the same once it reaches a workflow step.
#
# WHAT IT INTERACTS WITH
#   - `workflow_schema.py`, for the `FileReference` model every method here
#     builds and returns.
#   - `auth.py`'s `EnterpriseAuthManager`, for the access token needed
#     before calling the (currently simulated) Graph API in
#     `fetch_remote_metadata_with_retry`.
#   - The `tenacity` package, which wraps that same method in automatic
#     retry-with-backoff -- so a transient network hiccup or an enterprise
#     rate limit (HTTP 429/503) gets retried a few times before giving up,
#     instead of failing the whole workflow step on the first blip.
#   - `canvas_parser.py` / `sandbox_smoke_test.py`, which call
#     `M365OneDriveAdapter.ingest_drive_item()` and
#     `GoogleDriveAdapter.ingest_drive_file()` to turn a sample API response
#     into a real `FileReference` for a workflow to carry around.
#
# KEY FUNCTIONALITY NOTES
#   - `ingest_drive_item()` / `ingest_drive_file()` are pure data mappers --
#     no network call, no side effects. They just reshape whatever JSON
#     dict the API already returned.
#   - `fetch_remote_metadata_with_retry()` is the one method that actually
#     "talks" to an external service -- today it returns a hardcoded,
#     clearly-fake response rather than a live HTTP call (see the comment
#     inline marking where a real `httpx.get(...)` would go), consistent
#     with the project's current mock-mode stage.
# =============================================================================

from typing import Dict, Any
from tenacity import retry, stop_after_attempt, wait_random_exponential
from .workflow_schema import FileReference
from .auth import EnterpriseAuthManager

class M365OneDriveAdapter:
    """Ingests and normalizes Microsoft Graph API OneDrive/SharePoint file representations."""

    @staticmethod
    def ingest_drive_item(graph_item_response: Dict[str, Any], internal_vault_uri: str) -> FileReference:
        file_info = graph_item_response.get("file", {})
        return FileReference(
            file_id=str(graph_item_response.get("id", "")),
            source="m365_onedrive",
            filename=graph_item_response.get("name", "unnamed_m365_file"),
            mime_type=file_info.get("mimeType", "application/octet-stream"),
            uri=internal_vault_uri,
            external_url=graph_item_response.get("webUrl"),
            metadata={
                "eTag": graph_item_response.get("eTag"),
                "createdBy": graph_item_response.get("createdBy", {}).get("user", {}).get("email"),
                "size": graph_item_response.get("size", 0)
            }
        )

    @staticmethod
    @retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(3))
    def fetch_remote_metadata_with_retry(item_id: str, auth_references: Dict[str, str]) -> Dict[str, Any]:
        """Simulates/fetches item metadata from Graph API with backoff."""
        token = EnterpriseAuthManager.get_m365_access_token(auth_references)
        # HTTP client integration point (e.g. httpx.get(f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}", headers={"Authorization": f"Bearer {token}"}))
        return {
            "id": item_id,
            "name": f"remote_m365_file_{item_id}.pdf",
            "file": {"mimeType": "application/pdf"},
            "size": 102400,
            "webUrl": f"https://enterprise.sharepoint.com/docs/{item_id}"
        }

class GoogleDriveAdapter:
    """Ingests and normalizes Google Drive v3 API file representations."""

    @staticmethod
    def ingest_drive_file(gdrive_file_response: Dict[str, Any], internal_vault_uri: str) -> FileReference:
        return FileReference(
            file_id=str(gdrive_file_response.get("id", "")),
            source="google_drive",
            filename=gdrive_file_response.get("name", "unnamed_gdrive_file"),
            mime_type=gdrive_file_response.get("mimeType", "application/octet-stream"),
            uri=internal_vault_uri,
            external_url=gdrive_file_response.get("webViewLink"),
            metadata={
                "version": gdrive_file_response.get("version"),
                "owners": [owner.get("emailAddress") for owner in gdrive_file_response.get("owners", []) if "emailAddress" in owner]
            }
        )
