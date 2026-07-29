---
tool_id: 'auth'
title: 'Enterprise Auth Manager'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/authentication, scope/enterprise-adapters, connects/enterprise-adapters]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# auth

> **Status:** Active, mock-mode. No `__main__` block. Imported by [[enterprise_adapters]].

## Purpose

Gets the access token needed to call Microsoft 365 Graph or Google Workspace APIs on the signed-in user's behalf. Real enterprise auth (MSAL, a Google service-account key) isn't fully wired up yet -- per CLAUDE.md's mock-mode principle, both methods fall back to a clearly-labeled mock token (`mock_sandbox_...`) until the right credentials/environment variables exist.

## Processing Logic

### `EnterpriseAuthManager.get_m365_access_token(auth_references) -> str`

Returns a cached token from `auth_references` if present and not a `ref://` placeholder. Otherwise reads `M365_CLIENT_ID`/`M365_TENANT_ID`/`M365_CLIENT_SECRET`; if `msal` is installed and those are set, calls `ConfidentialClientApplication.acquire_token_for_client(...)` for a real token. Falls back to a mock token on missing config or missing `msal`.

### `EnterpriseAuthManager.get_google_access_token(auth_references) -> str`

Same pattern for Google: reads `GOOGLE_SERVICE_ACCOUNT_JSON` (a path to a service-account key file); if it exists and `google.oauth2`/`google.auth` are installed, refreshes a real token via `service_account.Credentials`. Falls back to a mock token otherwise.

## Output

A bearer-token string, real or mock, consumed by [[enterprise_adapters]]'s `fetch_remote_metadata_with_retry`.

## Notes for AI reuse

Both methods are already structured so a real credential just needs to exist (the right env vars set, `msal`/`google-auth` installed) -- no calling code elsewhere needs to change when real enterprise auth is turned on.
