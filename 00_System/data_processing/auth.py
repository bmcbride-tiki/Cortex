# =============================================================================
# auth.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Gets the access token needed to actually call Microsoft 365 Graph or
#   Google Workspace APIs on the signed-in user's behalf. Real enterprise
#   authentication (MSAL for Microsoft, a service-account key for Google)
#   isn't fully wired up yet -- see CLAUDE.md's mock-mode principle -- so
#   until the right environment variables/credentials exist, both methods
#   fall back to a clearly-labeled mock token so the rest of the app can be
#   built and tested without needing real enterprise credentials.
#
# WHAT IT INTERACTS WITH
#   - `enterprise_adapters.py`, the main consumer -- `fetch_remote_metadata_with_retry`
#     calls `get_m365_access_token()` before making its (currently simulated)
#     Graph API request.
#   - The `msal` package (Microsoft's official auth library) and
#     `google.oauth2`/`google.auth`, only if they're installed and the
#     matching environment variables are set -- both imports are wrapped in
#     `try/except ImportError` so their absence never breaks anything.
#   - Environment variables: `M365_CLIENT_ID`, `M365_TENANT_ID`,
#     `M365_CLIENT_SECRET` for Microsoft; `GOOGLE_SERVICE_ACCOUNT_JSON`
#     (a path to a service-account key file) for Google.
#
# KEY FUNCTIONALITY NOTES
#   - Both methods accept an `auth_references` dict first -- if it already
#     has a real (non-`ref://`) token cached for that service, that's
#     returned immediately with no network call at all.
#   - Falling back to a mock token isn't a silent failure -- every mock
#     value is prefixed `mock_sandbox_...` so it's obvious in logs/output
#     that no real API call happened.
# =============================================================================

import os
from typing import Dict

class EnterpriseAuthManager:
    """Handles token resolution for Microsoft 365 Graph API and Google Workspace API."""

    @staticmethod
    def get_m365_access_token(auth_references: Dict[str, str]) -> str:
        """
        Acquires Microsoft Graph API access token via MSAL or vault pointer.
        """
        token_ref = auth_references.get("m365_access")
        if token_ref and not token_ref.startswith("ref://"):
            return token_ref

        client_id = os.getenv("M365_CLIENT_ID")
        tenant_id = os.getenv("M365_TENANT_ID")

        if not client_id or not tenant_id:
            return "mock_sandbox_m365_bearer_token"

        try:
            import msal
            client_secret = os.getenv("M365_CLIENT_SECRET", "mock_secret")
            app = msal.ConfidentialClientApplication(
                client_id, authority=f"https://login.microsoftonline.com/{tenant_id}",
                client_credential=client_secret
            )
            result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            return result.get("access_token", "mock_sandbox_m365_bearer_token")
        except ImportError:
            return "mock_sandbox_m365_bearer_token"

    @staticmethod
    def get_google_access_token(auth_references: Dict[str, str]) -> str:
        """
        Acquires Google Workspace API access token.
        """
        token_ref = auth_references.get("google_access")
        if token_ref and not token_ref.startswith("ref://"):
            return token_ref

        sa_key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not sa_key_path or not os.path.exists(sa_key_path):
            return "mock_sandbox_google_bearer_token"

        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests
            creds = service_account.Credentials.from_service_account_file(
                sa_key_path, scopes=["https://www.googleapis.com/auth/drive.readonly"]
            )
            request = google.auth.transport.requests.Request()
            creds.refresh(request)
            return creds.token
        except ImportError:
            return "mock_sandbox_google_bearer_token"
