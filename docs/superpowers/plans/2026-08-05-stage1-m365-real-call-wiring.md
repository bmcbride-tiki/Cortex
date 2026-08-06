# Stage 1 — M365 Real-Call Wiring (Existing Functions) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every already-stubbed M365 Graph/Power BI function in `14_Adapters/m365_graph_bridge/m365_graph_bridge.py` gets real HTTP request-construction code behind `MOCK_MODE`, fully testable today via mocked HTTP responses, with zero real tenant access required.

**Architecture:** Two small shared helpers (`_graph_request` for JSON-returning calls, `_graph_request_binary` for raw-content calls) wrap `requests.request` with the same 30s-timeout / non-2xx-raises contract `workflow_engine.py`'s `function_http` node already uses. Every wired function keeps its existing mock branch and adds a real branch guarded by `if not MOCK_MODE:`, using `EnterpriseAuthManager` (already in `data_processing/auth.py`) for the bearer token and a new `target_upn` parameter (app-only auth has no `/me`) that defaults through `M365_TARGET_UPN` / `CORTEX_USER_UPN` env vars when not explicitly passed.

**Tech Stack:** Python, `requests` (already a dependency), `msal` (added this plan), `unittest.mock.patch` for tests.

**Scope note:** This plan covers roadmap groups 1–8 (existing stubbed functions). Group 9 (brand-new Planner/Forms/Dataverse/Word Online/Power BI-Execute-Query functions) is intentionally a separate plan, per the roadmap's own suggestion to split "existing-function wiring" from "new-function additions." `generate_pptx_from_word` is excluded — its own code comment confirms no real Copilot API exists to call, mock or otherwise, so it stays mock-only. Six existing bridge functions have no `12_Tasks/` wrapper today (`list_recent_onedrive_files`, `list_messages`, `list_teams`, `list_sharepoint_sites`, `list_onenote_notebooks`, `list_powerbi_reports`) — this plan wires their bridge-level code (so they're real once called, e.g. via the bridge's own CLI or a future workflow node) but does **not** create new wrapper files for them; adding new Task wrappers is a UI-surface decision closer to group 9's territory, not "wiring."

## Global Constraints

- `MOCK_MODE` (env var `M365_MOCK_MODE`, default on) stays the toggle. Real code lives behind `if not MOCK_MODE:`, never replaces the mock branch.
- Every real HTTP call: 30s timeout, non-2xx raises `RuntimeError` including status code + response body (first 1000 chars) — same contract as `function_http` in `workflow_engine.py:1014-1043`.
- Single shared app-identity (client-credentials/app-only), not per-user delegated auth — already-settled decision, do not re-litigate.
- Every function that hits `/me/...` in Graph docs takes it as `/users/{target_upn}/...` instead, with `target_upn: str = ""` as a new trailing optional parameter, resolved via `_resolve_target_upn()` (explicit arg → `M365_TARGET_UPN` env var → `CORTEX_USER_UPN` env var → literal `"user@enterprise.com"`, matching `user_identity.py`'s own default).
- Test pattern for every wired function: one test that flips `m365.MOCK_MODE = False`, patches `m365_graph_bridge.requests.request`, and asserts the exact URL/method/headers/body constructed. Always restore `m365.MOCK_MODE = True` in a `finally`.
- **Deliberate deviation from the roadmap's literal "one non-2xx test per function":** non-2xx handling lives entirely inside `_graph_request`/`_graph_request_binary` (Task 0), which every wired function routes through with no per-function branching on status code. Task 0 proves that behavior once (`test_graph_request_non_2xx_raises`); this plan then adds a per-function non-2xx test only where a function does its own extra work worth guarding (e.g. `upload_file`'s size guard runs before the HTTP call, `search_messages`'s required-field check, `create_sharepoint_list_item`'s field validation) rather than at every call site, to avoid ~25 tests that would all be re-asserting the same three lines of shared code. Flagging this here so it reads as a scoped decision, not a missed requirement.
- No new third-party dependency beyond `msal` (already decided in the roadmap).
- Endpoints not confidently known from training data were verified against Microsoft Learn during planning (OneNote pages-under-notebook, Excel Workbook range addressing, Power BI service-principal scope, SharePoint site search, mail `$search`+`$filter` consistency header) — noted inline where relevant. Nothing here is "proven" against a real tenant; that's Stage 7's job.

---

## Task 0: Shared HTTP/auth plumbing

**Files:**
- Modify: `requirements.txt`
- Modify: `00_System/data_processing/auth.py`
- Modify: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py:36-54`
- Modify: `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py:203-212`

**Interfaces:**
- Produces (used by every later task): `_resolve_target_upn(target_upn: str = "") -> str`, `_graph_request(method: str, url: str, token: str, json_body: Any = None, data: Any = None, params: Dict[str, str] = None, extra_headers: Dict[str, str] = None) -> Dict[str, Any]`, `_graph_request_binary(method: str, url: str, token: str, data: Any = None, extra_headers: Dict[str, str] = None) -> bytes`, module constants `GRAPH_BASE`, `POWERBI_BASE`, and `EnterpriseAuthManager` imported into `m365_graph_bridge.py`'s module namespace. Also `EnterpriseAuthManager.get_powerbi_access_token(auth_references: Dict[str, str]) -> str` in `auth.py`.

- [ ] **Step 1: Add `msal` to requirements.txt**

Add this line (alphabetically, after `mdurl==0.1.2` and before `nodeenv==1.10.0`):

```
msal==1.31.1
```

- [ ] **Step 2: Install it and confirm `import msal` succeeds**

Run: `pip install -r requirements.txt`
Then: `python -c "import msal; print(msal.__version__)"`
Expected: prints a version string, no `ModuleNotFoundError`. If `msal==1.31.1` fails to resolve, drop the pin (`msal`) and let pip pick the current release, then update `requirements.txt` with whatever version `pip freeze | grep msal` reports.

- [ ] **Step 3: Add `get_powerbi_access_token` to `auth.py`**

Add this method to `EnterpriseAuthManager` in `00_System/data_processing/auth.py`, right after `get_m365_access_token` (after line 66):

```python
    @staticmethod
    def get_powerbi_access_token(auth_references: Dict[str, str]) -> str:
        """
        Acquires a Power BI REST API access token via MSAL client-credentials.
        Power BI uses a different resource/scope than Graph even though it's the
        same Azure AD app registration -- https://analysis.windows.net/powerbi/api/.default,
        not https://graph.microsoft.com/.default.
        """
        token_ref = auth_references.get("powerbi_access")
        if token_ref and not token_ref.startswith("ref://"):
            return token_ref

        client_id = os.getenv("M365_CLIENT_ID")
        tenant_id = os.getenv("M365_TENANT_ID")

        if not client_id or not tenant_id:
            return "mock_sandbox_powerbi_bearer_token"

        try:
            import msal
            client_secret = os.getenv("M365_CLIENT_SECRET", "mock_secret")
            app = msal.ConfidentialClientApplication(
                client_id, authority=f"https://login.microsoftonline.com/{tenant_id}",
                client_credential=client_secret
            )
            result = app.acquire_token_for_client(scopes=["https://analysis.windows.net/powerbi/api/.default"])
            return result.get("access_token", "mock_sandbox_powerbi_bearer_token")
        except ImportError:
            return "mock_sandbox_powerbi_bearer_token"
```

- [ ] **Step 4: Write the failing test for the shared helpers**

Add to `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`, near the top after the existing imports (add `from unittest.mock import patch, MagicMock` to the imports too):

```python
def test_graph_request_get_success():
    mock_resp = MagicMock(status_code=200, content=b'{"value": []}')
    mock_resp.json.return_value = {"value": []}
    with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
        result = m365._graph_request("GET", "https://graph.microsoft.com/v1.0/me/drive", "tok123")
    mock_request.assert_called_once_with(
        "GET", "https://graph.microsoft.com/v1.0/me/drive",
        headers={"Authorization": "Bearer tok123", "Accept": "application/json"},
        json=None, data=None, params=None, timeout=30,
    )
    assert result == {"value": []}


def test_graph_request_non_2xx_raises():
    mock_resp = MagicMock(status_code=403, reason="Forbidden", text="insufficient scope", content=b"x")
    with patch("m365_graph_bridge.requests.request", return_value=mock_resp):
        try:
            m365._graph_request("GET", "https://graph.microsoft.com/v1.0/me/drive", "tok123")
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "403" in str(e)
            assert "insufficient scope" in str(e)


def test_graph_request_binary_success():
    mock_resp = MagicMock(status_code=200, content=b"raw file bytes")
    with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
        result = m365._graph_request_binary("GET", "https://graph.microsoft.com/v1.0/me/drive/root:/x:/content", "tok123")
    mock_request.assert_called_once_with(
        "GET", "https://graph.microsoft.com/v1.0/me/drive/root:/x:/content",
        headers={"Authorization": "Bearer tok123"}, data=None, timeout=30,
    )
    assert result == b"raw file bytes"


def test_resolve_target_upn_falls_back_through_env_vars():
    assert m365._resolve_target_upn("explicit@x.com") == "explicit@x.com"
    import os as _os
    _os.environ.pop("M365_TARGET_UPN", None)
    _os.environ.pop("CORTEX_USER_UPN", None)
    assert m365._resolve_target_upn() == "user@enterprise.com"
    _os.environ["CORTEX_USER_UPN"] = "fromenv@x.com"
    try:
        assert m365._resolve_target_upn() == "fromenv@x.com"
    finally:
        _os.environ.pop("CORTEX_USER_UPN", None)
```

- [ ] **Step 5: Run it to verify it fails**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Expected: `AttributeError: module 'm365_graph_bridge' has no attribute '_graph_request'`

- [ ] **Step 6: Implement the shared plumbing in `m365_graph_bridge.py`**

Replace lines 36-54 (from `import sys` through the `NOT_CONFIGURED_MESSAGE` closing `)`) with:

```python
# 14_Adapters/m365_graph_bridge/m365_graph_bridge.py
import sys
sys.dont_write_bytecode = True

import os
import json
import uuid
import argparse
import requests
from pathlib import Path
from typing import Any, Dict, List

_00_SYSTEM_DIR = Path(__file__).resolve().parents[2] / "00_System"
if str(_00_SYSTEM_DIR) not in sys.path:
    sys.path.append(str(_00_SYSTEM_DIR))

from data_processing.auth import EnterpriseAuthManager

MOCK_MODE = os.environ.get("M365_MOCK_MODE", "1") != "0"

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
POWERBI_BASE = "https://api.powerbi.com/v1.0/myorg"

NOT_CONFIGURED_MESSAGE = (
    "M365/Graph API access is not configured yet. Set M365_MOCK_MODE=1 (the default) "
    "to use simulated responses, or register an Azure AD app (tenant ID, client ID, "
    "client secret/certificate, Graph + Power BI API permissions) and wire up MSAL + "
    "the msgraph-sdk inside m365_graph_bridge.py."
)


def _resolve_target_upn(target_upn: str = "") -> str:
    return target_upn or os.getenv("M365_TARGET_UPN", "") or os.getenv("CORTEX_USER_UPN", "user@enterprise.com")


def _graph_request(method: str, url: str, token: str, json_body: Any = None, data: Any = None,
                    params: Dict[str, str] = None, extra_headers: Dict[str, str] = None) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    try:
        resp = requests.request(method, url, headers=headers, json=json_body, data=data, params=params, timeout=30)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Graph {method} {url} failed: {e}")
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph {method} {url} failed: {resp.status_code} {resp.reason}\n{resp.text[:1000]}")
    if not resp.content:
        return {}
    return resp.json()


def _graph_request_binary(method: str, url: str, token: str, data: Any = None,
                           extra_headers: Dict[str, str] = None) -> bytes:
    headers = {"Authorization": f"Bearer {token}"}
    if extra_headers:
        headers.update(extra_headers)
    try:
        resp = requests.request(method, url, headers=headers, data=data, timeout=30)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Graph {method} {url} failed: {e}")
    if resp.status_code >= 400:
        raise RuntimeError(f"Graph {method} {url} failed: {resp.status_code} {resp.reason}\n{resp.text[:1000]}")
    return resp.content
```

- [ ] **Step 7: Run it to verify it passes**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Expected: reaches `test_mock_mode_off_fails_clearly` and fails there (next step fixes that one) — the four new tests print no error before it.

- [ ] **Step 8: Fix `test_mock_mode_off_fails_clearly` — it now only applies to the one function that stays mock-only**

Replace (current lines ~203-212):

```python
def test_mock_mode_off_fails_clearly():
    m365.MOCK_MODE = False
    try:
        try:
            m365.list_files("/x")
            assert False, "expected RuntimeError when MOCK_MODE is off"
        except RuntimeError as e:
            assert "not configured" in str(e)
    finally:
        m365.MOCK_MODE = True
```

with:

```python
def test_mock_mode_off_still_fails_clearly_for_unwired_functions():
    # generate_pptx_from_word has no real API to call (see its own docstring) --
    # every other function in this module gets a real branch across this plan's
    # tasks, so this is the one remaining function that must still raise.
    m365.MOCK_MODE = False
    try:
        try:
            m365.generate_pptx_from_word("/x.docx", "/tmp")
            assert False, "expected RuntimeError when MOCK_MODE is off"
        except RuntimeError as e:
            assert "not configured" in str(e)
    finally:
        m365.MOCK_MODE = True
```

And update the `__main__` block's call from `test_mock_mode_off_fails_clearly()` to `test_mock_mode_off_still_fails_clearly_for_unwired_functions()`, and add the four new Step-4 tests to that same call list.

- [ ] **Step 9: Run the full test file and confirm everything passes**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Expected: `All m365_graph_bridge self-checks passed.`

- [ ] **Step 10: Commit**

```bash
git add requirements.txt 00_System/data_processing/auth.py 14_Adapters/m365_graph_bridge/m365_graph_bridge.py 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py
git commit -m "feat(m365): add msal dep and shared Graph HTTP/auth plumbing"
```

---

## Task 1: OneDrive/SharePoint files (list_files, download_file, upload_file, list_recent_onedrive_files, create_onedrive_sharing_link)

**Files:**
- Modify: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py:57-91` (the three core functions) and the OneDrive-extras block (`list_recent_onedrive_files`/`create_onedrive_sharing_link`) plus `main()`'s dispatch lines for these five actions.
- Modify: `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
- Modify: `12_Tasks/list_m365_files/list_m365_files.py`
- Modify: `12_Tasks/download_m365_file/download_m365_file.py`
- Modify: `12_Tasks/upload_m365_file/upload_m365_file.py`
- Modify: `12_Tasks/create_onedrive_sharing_link/create_onedrive_sharing_link.py`

**Interfaces:**
- Consumes: `_resolve_target_upn`, `_graph_request`, `_graph_request_binary`, `GRAPH_BASE`, `EnterpriseAuthManager` from Task 0.
- Produces: `list_files(folder_path, target_upn="")`, `download_file(file_path, local_output_dir, target_upn="")`, `upload_file(local_path, destination_path, target_upn="")`, `list_recent_onedrive_files(target_upn="")`, `create_onedrive_sharing_link(file_path, target_upn="")` all gain real branches. No wrapper exists for `list_recent_onedrive_files` — skip that file per this plan's scope note.

- [ ] **Step 1: Write the failing tests**

Add to `test_m365_graph_bridge.py`:

```python
def test_list_files_real_mode_constructs_request_and_maps_result():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "item_1", "name": "Budget.xlsx", "size": 100, "webUrl": "https://x/Budget.xlsx"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_files("/Reports", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/drive/root:/Reports:/children",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert result["files"][0]["item_id"] == "item_1"
    finally:
        m365.MOCK_MODE = True


def test_list_files_real_mode_non_2xx_raises():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=404, reason="Not Found", text="no such folder", content=b"x")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp):
            try:
                m365.list_files("/Missing", target_upn="user@contoso.com")
                assert False, "expected RuntimeError"
            except RuntimeError as e:
                assert "404" in str(e)
    finally:
        m365.MOCK_MODE = True


def test_download_file_real_mode_writes_content_to_disk():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"real file bytes")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            with tempfile.TemporaryDirectory() as tmp:
                result = m365.download_file("/Reports/Budget.xlsx", tmp, target_upn="user@contoso.com")
                assert Path(result["local_path"]).read_bytes() == b"real file bytes"
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/drive/root:/Reports/Budget.xlsx:/content",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token"}, data=None, timeout=30,
        )
    finally:
        m365.MOCK_MODE = True


def test_download_file_real_mode_non_2xx_raises():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=404, reason="Not Found", text="missing", content=b"x")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp):
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    m365.download_file("/Missing.docx", tmp)
                    assert False, "expected RuntimeError"
                except RuntimeError as e:
                    assert "404" in str(e)
    finally:
        m365.MOCK_MODE = True


def test_upload_file_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"id": "item_new", "webUrl": "https://x/report.docx"}
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "report.docx"
            src.write_bytes(b"hello")
            with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
                result = m365.upload_file(str(src), "/Reports/report.docx", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "PUT", "https://graph.microsoft.com/v1.0/users/user@contoso.com/drive/root:/Reports/report.docx:/content",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json", "Content-Type": "application/octet-stream"},
            json=None, data=b"hello", params=None, timeout=30,
        )
        assert result["item_id"] == "item_new"
    finally:
        m365.MOCK_MODE = True


def test_upload_file_real_mode_rejects_large_file():
    m365.MOCK_MODE = False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "big.bin"
            src.write_bytes(b"x" * (4 * 1024 * 1024 + 1))
            try:
                m365.upload_file(str(src), "/big.bin")
                assert False, "expected ValueError for >4MB file"
            except ValueError as e:
                assert "4MB" in str(e)
    finally:
        m365.MOCK_MODE = True


def test_list_recent_onedrive_files_real_mode():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "item_1", "name": "Recent.docx", "lastModifiedDateTime": "2026-01-01T00:00:00Z"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_recent_onedrive_files(target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/drive/recent",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert result["files"][0]["item_id"] == "item_1"
    finally:
        m365.MOCK_MODE = True


def test_create_onedrive_sharing_link_real_mode():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"link": {"webUrl": "https://x/share/abc", "type": "view"}}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.create_onedrive_sharing_link("/Reports/Budget.xlsx", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "POST", "https://graph.microsoft.com/v1.0/users/user@contoso.com/drive/root:/Reports/Budget.xlsx:/createLink",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json={"type": "view", "scope": "organization"}, data=None, params=None, timeout=30,
        )
        assert result["share_url"] == "https://x/share/abc"
    finally:
        m365.MOCK_MODE = True


def test_create_onedrive_sharing_link_real_mode_non_2xx_raises():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=403, reason="Forbidden", text="no access", content=b"x")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp):
            try:
                m365.create_onedrive_sharing_link("/x.docx")
                assert False, "expected RuntimeError"
            except RuntimeError as e:
                assert "403" in str(e)
    finally:
        m365.MOCK_MODE = True
```

- [ ] **Step 2: Run to verify failure**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Expected: `AssertionError` or `TypeError: list_files() got an unexpected keyword argument 'target_upn'`.

- [ ] **Step 3: Implement the real branches**

Replace `list_files`/`download_file`/`upload_file` (current lines 57-91) with:

```python
def list_files(folder_path: str, target_upn: str = "") -> Dict[str, Any]:
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        path = (folder_path or "").strip("/")
        url = f"{GRAPH_BASE}/users/{upn}/drive/root/children" if not path else f"{GRAPH_BASE}/users/{upn}/drive/root:/{path}:/children"
        data = _graph_request("GET", url, token)
        files = [{"name": f["name"], "item_id": f["id"], "size": f.get("size", 0), "web_url": f.get("webUrl", "")} for f in data.get("value", [])]
        return {"files": files}
    folder_path = folder_path or "/"
    files = [
        {"name": "Quarterly Report.docx", "item_id": f"item_{uuid.uuid4().hex[:10]}", "size": 48213, "web_url": f"https://example.sharepoint.com{folder_path}/Quarterly%20Report.docx"},
        {"name": "Budget.xlsx", "item_id": f"item_{uuid.uuid4().hex[:10]}", "size": 102934, "web_url": f"https://example.sharepoint.com{folder_path}/Budget.xlsx"},
    ]
    return {"files": files}


def download_file(file_path: str, local_output_dir: str, target_upn: str = "") -> Dict[str, Any]:
    if not file_path:
        raise ValueError("download_file requires a file_path.")

    out_dir = Path(local_output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    local_path = out_dir / Path(file_path).name

    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        path = file_path.strip("/")
        content = _graph_request_binary("GET", f"{GRAPH_BASE}/users/{upn}/drive/root:/{path}:/content", token)
        local_path.write_bytes(content)
        return {"local_path": str(local_path)}

    local_path.write_text(f"[MOCK M365 download] placeholder content for {file_path}", encoding="utf-8")
    return {"local_path": str(local_path)}


def upload_file(local_path: str, destination_path: str, target_upn: str = "") -> Dict[str, Any]:
    if not local_path:
        raise ValueError("upload_file requires a local_path.")

    src = Path(local_path)
    if not src.exists():
        raise FileNotFoundError(f"Local file not found: {src}")

    if not MOCK_MODE:
        file_bytes = src.read_bytes()
        if len(file_bytes) > 4 * 1024 * 1024:
            raise ValueError("upload_file only supports files up to 4MB via Graph's simple upload API; larger files need a Graph upload session (not implemented).")
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        dest = (destination_path or f"/{src.name}").strip("/")
        data = _graph_request("PUT", f"{GRAPH_BASE}/users/{upn}/drive/root:/{dest}:/content", token,
                               data=file_bytes, extra_headers={"Content-Type": "application/octet-stream"})
        return {"item_id": data["id"], "web_url": data.get("webUrl", "")}

    return {"item_id": f"item_{uuid.uuid4().hex[:10]}", "web_url": f"https://example.sharepoint.com{destination_path or '/' + src.name}"}
```

Replace the OneDrive-extras block (`list_recent_onedrive_files`/`create_onedrive_sharing_link`, near the end of the file) with:

```python
def list_recent_onedrive_files(target_upn: str = "") -> Dict[str, Any]:
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("GET", f"{GRAPH_BASE}/users/{upn}/drive/recent", token)
        return {"files": [{"name": f["name"], "item_id": f["id"], "last_modified": f.get("lastModifiedDateTime", "")} for f in data.get("value", [])]}
    files = [
        {"name": "Quarterly Report.docx", "item_id": f"item_{uuid.uuid4().hex[:10]}", "last_modified": "2026-07-21T10:05:00Z"},
        {"name": "Budget.xlsx", "item_id": f"item_{uuid.uuid4().hex[:10]}", "last_modified": "2026-07-20T15:40:00Z"},
    ]
    return {"files": files}


def create_onedrive_sharing_link(file_path: str, target_upn: str = "") -> Dict[str, Any]:
    if not file_path:
        raise ValueError("create_onedrive_sharing_link requires a file_path.")
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        path = file_path.strip("/")
        data = _graph_request("POST", f"{GRAPH_BASE}/users/{upn}/drive/root:/{path}:/createLink", token,
                               json_body={"type": "view", "scope": "organization"})
        link = data.get("link", {})
        return {"share_url": link.get("webUrl", ""), "link_type": link.get("type", "view")}
    return {"share_url": f"https://example.sharepoint.com/:x:/g/personal/mock/{uuid.uuid4().hex[:16]}", "link_type": "view"}
```

In `main()`, update the five dispatch lines for these actions to pass `target_upn`:

```python
        if action == "list_files":
            result = {"success": True, **list_files(params.get("folder_path", ""), params.get("target_upn", ""))}
        elif action == "download_file":
            result = {"success": True, **download_file(params.get("file_path", ""), params.get("local_output_dir", ""), params.get("target_upn", ""))}
        elif action == "upload_file":
            result = {"success": True, **upload_file(params.get("local_path", ""), params.get("destination_path", ""), params.get("target_upn", ""))}
```

and:

```python
        elif action == "list_recent_onedrive_files":
            result = {"success": True, **list_recent_onedrive_files(params.get("target_upn", ""))}
        elif action == "create_onedrive_sharing_link":
            result = {"success": True, **create_onedrive_sharing_link(params.get("file_path", ""), params.get("target_upn", ""))}
```

- [ ] **Step 4: Update the 12_Tasks wrappers**

`12_Tasks/list_m365_files/list_m365_files.py` — change `run()` and the `__main__` call:

```python
    def run(self, folder_path: str, target_upn: str = "") -> dict:
        try:
            return {"success": True, **list_files(folder_path, target_upn)}
        except Exception as e:
            return {"success": False, "response": f"list_m365_files error: {e}"}
```
```python
        result = ListM365Files().run(folder_path=params.get("folder_path", ""), target_upn=params.get("target_upn", ""))
```

`12_Tasks/download_m365_file/download_m365_file.py` — same shape, add `target_upn: str = ""` to `run()`, forward it as the third positional arg to `download_file(...)`, and add `target_upn=params.get("target_upn", "")` to the `__main__` call.

`12_Tasks/upload_m365_file/upload_m365_file.py` — same shape, add `target_upn: str = ""` to `run()`, forward it as the third positional arg to `upload_file(...)`, and add `target_upn=params.get("target_upn", "")` to the `__main__` call.

`12_Tasks/create_onedrive_sharing_link/create_onedrive_sharing_link.py` — same shape, add `target_upn: str = ""` to `run()`, forward it as the second positional arg to `create_onedrive_sharing_link(...)`, and add `target_upn=params.get("target_upn", "")` to the `__main__` call.

- [ ] **Step 5: Run all tests to verify they pass**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Run: `python 12_Tasks/list_m365_files/test_list_m365_files.py`
Run: `python 12_Tasks/download_m365_file/test_download_m365_file.py`
Run: `python 12_Tasks/upload_m365_file/test_upload_m365_file.py`
Run: `python 12_Tasks/create_onedrive_sharing_link/test_create_onedrive_sharing_link.py`
Expected: all print their "All ... self-checks passed." line — the existing wrapper tests call `run()` without `target_upn`, which still works because it defaults to `""`.

- [ ] **Step 6: Commit**

```bash
git add 14_Adapters/m365_graph_bridge/m365_graph_bridge.py 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py 12_Tasks/list_m365_files/list_m365_files.py 12_Tasks/download_m365_file/download_m365_file.py 12_Tasks/upload_m365_file/upload_m365_file.py 12_Tasks/create_onedrive_sharing_link/create_onedrive_sharing_link.py
git commit -m "feat(m365): wire OneDrive/SharePoint file functions to real Graph calls"
```

---

## Task 2: Outlook (send_mail, list_messages, search_messages)

**Files:**
- Modify: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py:130-162` and `main()`'s dispatch for these three actions.
- Modify: `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
- Modify: `12_Tasks/send_outlook_mail/send_outlook_mail.py`
- Modify: `12_Tasks/search_outlook_email/search_outlook_email.py`

**Interfaces:**
- Consumes: Task 0's helpers.
- Produces: `send_mail(to, subject, body, target_upn="")`, `list_messages(folder="inbox", top=10, target_upn="")`, `search_messages(query="", sender="", folder="inbox", top=10, target_upn="")`. `list_messages` has no `12_Tasks` wrapper — skip that file.

- [ ] **Step 1: Write the failing tests**

```python
def test_send_mail_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=202, content=b"")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.send_mail("a@example.com, b@example.com", "Subject", "Body", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "POST", "https://graph.microsoft.com/v1.0/users/user@contoso.com/sendMail",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json={"message": {"subject": "Subject", "body": {"contentType": "Text", "content": "Body"},
                              "toRecipients": [{"emailAddress": {"address": "a@example.com"}}, {"emailAddress": {"address": "b@example.com"}}]}},
            data=None, params=None, timeout=30,
        )
        assert result["to"] == ["a@example.com", "b@example.com"]
        assert result["status"] == "sent"
    finally:
        m365.MOCK_MODE = True


def test_send_mail_real_mode_non_2xx_raises():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=400, reason="Bad Request", text="invalid recipient", content=b"x")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp):
            try:
                m365.send_mail("bad", "S", "B")
                assert False, "expected RuntimeError"
            except RuntimeError as e:
                assert "400" in str(e)
    finally:
        m365.MOCK_MODE = True


def test_list_messages_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "m1", "from": {"emailAddress": {"address": "a@x.com"}}, "subject": "S", "receivedDateTime": "2026-01-01T00:00:00Z", "bodyPreview": "preview"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_messages("inbox", top=5, target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/mailFolders/inbox/messages",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params={"$top": "5"}, timeout=30,
        )
        assert result["messages"][0]["from"] == "a@x.com"
    finally:
        m365.MOCK_MODE = True


def test_search_messages_real_mode_constructs_request_with_query_and_sender():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "m1", "from": {"emailAddress": {"address": "registrar@x.com"}}, "subject": "S", "receivedDateTime": "2026-01-01T00:00:00Z", "bodyPreview": "p"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.search_messages(query="curriculum", sender="registrar", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/messages",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json", "ConsistencyLevel": "eventual"},
            json=None, data=None,
            params={"$top": "10", "$search": '"curriculum"', "$filter": "from/emailAddress/address eq 'registrar'"},
            timeout=30,
        )
        assert result["messages"][0]["from"] == "registrar@x.com"
    finally:
        m365.MOCK_MODE = True


def test_search_messages_real_mode_requires_query_or_sender():
    m365.MOCK_MODE = False
    try:
        try:
            m365.search_messages()
            assert False, "expected ValueError"
        except ValueError:
            pass
    finally:
        m365.MOCK_MODE = True
```

- [ ] **Step 2: Run to verify failure**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Expected: `TypeError` on the new `target_upn` kwarg.

- [ ] **Step 3: Implement the real branches**

Replace the Outlook block (current lines 130-162) with:

```python
def send_mail(to: str, subject: str, body: str, target_upn: str = "") -> Dict[str, Any]:
    if not to:
        raise ValueError("send_mail requires a to address (comma-separated for multiple).")
    recipients = [a.strip() for a in to.split(",") if a.strip()]
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        mail_body = {"message": {"subject": subject, "body": {"contentType": "Text", "content": body},
                                  "toRecipients": [{"emailAddress": {"address": a}} for a in recipients]}}
        _graph_request("POST", f"{GRAPH_BASE}/users/{upn}/sendMail", token, json_body=mail_body)
        # Graph's sendMail returns 202 with no body -- no real message id to report back.
        return {"message_id": f"msg_{uuid.uuid4().hex[:10]}", "to": recipients, "status": "sent"}
    return {"message_id": f"msg_{uuid.uuid4().hex[:10]}", "to": recipients, "status": "sent (mock)"}


def list_messages(folder: str = "inbox", top: int = 10, target_upn: str = "") -> Dict[str, Any]:
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        folder = folder or "inbox"
        data = _graph_request("GET", f"{GRAPH_BASE}/users/{upn}/mailFolders/{folder}/messages", token,
                               params={"$top": str(max(top, 0) or 10)})
        messages = [
            {"id": m["id"], "from": m.get("from", {}).get("emailAddress", {}).get("address", ""),
             "subject": m.get("subject", ""), "received": m.get("receivedDateTime", ""), "preview": m.get("bodyPreview", "")}
            for m in data.get("value", [])
        ]
        return {"folder": folder, "messages": messages}
    messages = [
        {"id": f"msg_{uuid.uuid4().hex[:10]}", "from": "sme.lead@example.com", "subject": "Curriculum review sign-off", "received": "2026-07-20T09:15:00Z", "preview": "Please review the attached section before Friday..."},
        {"id": f"msg_{uuid.uuid4().hex[:10]}", "from": "registrar@example.com", "subject": "Exam schedule confirmed", "received": "2026-07-19T14:02:00Z", "preview": "The Q3 exam schedule has been finalized..."},
    ]
    return {"folder": folder or "inbox", "messages": messages[: max(top, 0) or len(messages)]}


def search_messages(query: str = "", sender: str = "", folder: str = "inbox", top: int = 10, target_upn: str = "") -> Dict[str, Any]:
    if not query and not sender:
        raise ValueError("search_messages requires a query and/or a sender to filter by.")
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        params = {"$top": str(max(top, 0) or 10)}
        if query:
            params["$search"] = f'"{query}"'
        if sender:
            params["$filter"] = f"from/emailAddress/address eq '{sender}'"
        # Graph's /messages search is mailbox-wide, not folder-scoped by well-known
        # name -- 'folder' is echoed below for API-shape parity with list_messages only.
        data = _graph_request("GET", f"{GRAPH_BASE}/users/{upn}/messages", token, params=params,
                               extra_headers={"ConsistencyLevel": "eventual"})
        messages = [
            {"id": m["id"], "from": m.get("from", {}).get("emailAddress", {}).get("address", ""),
             "subject": m.get("subject", ""), "received": m.get("receivedDateTime", ""), "preview": m.get("bodyPreview", "")}
            for m in data.get("value", [])
        ]
        return {"folder": folder or "inbox", "query": query, "sender": sender, "messages": messages}
    candidate_messages = [
        {"id": f"msg_{uuid.uuid4().hex[:10]}", "from": "sme.lead@example.com", "subject": "Curriculum review sign-off", "received": "2026-07-20T09:15:00Z", "preview": f"[MOCK match for query={query!r}] Please review the attached section before Friday..."},
        {"id": f"msg_{uuid.uuid4().hex[:10]}", "from": "registrar@example.com", "subject": "Exam schedule confirmed", "received": "2026-07-19T14:02:00Z", "preview": f"[MOCK match for query={query!r}] The Q3 exam schedule has been finalized..."},
    ]
    if sender:
        candidate_messages = [m for m in candidate_messages if sender.lower() in m["from"].lower()]
    return {"folder": folder or "inbox", "query": query, "sender": sender, "messages": candidate_messages[: max(top, 0) or len(candidate_messages)]}
```

In `main()`, update the three dispatch lines:

```python
        elif action == "send_mail":
            result = {"success": True, **send_mail(params.get("to", ""), params.get("subject", ""), params.get("body", ""), params.get("target_upn", ""))}
        elif action == "list_messages":
            result = {"success": True, **list_messages(params.get("folder", "inbox"), int(params.get("top") or 10), params.get("target_upn", ""))}
        elif action == "search_messages":
            result = {"success": True, **search_messages(params.get("query", ""), params.get("sender", ""), params.get("folder", "inbox"), int(params.get("top") or 10), params.get("target_upn", ""))}
```

- [ ] **Step 4: Update the 12_Tasks wrappers**

`12_Tasks/send_outlook_mail/send_outlook_mail.py`:

```python
    def run(self, to: str, subject: str, body: str, target_upn: str = "") -> dict:
        try:
            return {"success": True, **send_mail(to, subject, body, target_upn)}
        except Exception as e:
            return {"success": False, "response": f"send_outlook_mail error: {e}"}
```
```python
        result = SendOutlookMail().run(to=params.get("to", ""), subject=params.get("subject", ""), body=params.get("body", ""), target_upn=params.get("target_upn", ""))
```

`12_Tasks/search_outlook_email/search_outlook_email.py` — same shape: add `target_upn: str = ""` as the last `run()` parameter, forward it as `search_messages(...)`'s last positional arg, add `target_upn=params.get("target_upn", "")` to the `__main__` call.

- [ ] **Step 5: Run tests**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Run: `python 12_Tasks/send_outlook_mail/test_send_outlook_mail.py`
Run: `python 12_Tasks/search_outlook_email/test_search_outlook_email.py` (if it doesn't exist yet, skip — this Task doesn't add one; only wires the existing wrapper)
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add 14_Adapters/m365_graph_bridge/m365_graph_bridge.py 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py 12_Tasks/send_outlook_mail/send_outlook_mail.py 12_Tasks/search_outlook_email/search_outlook_email.py
git commit -m "feat(m365): wire Outlook mail functions to real Graph calls"
```

---

## Task 3: Calendar (list_calendar_events, create_calendar_event)

**Files:**
- Modify: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py:165-185` and `main()`'s dispatch for these two actions.
- Modify: `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
- Modify: `12_Tasks/list_outlook_calendar_events/list_outlook_calendar_events.py`
- Modify: `12_Tasks/create_outlook_calendar_event/create_outlook_calendar_event.py`

**Interfaces:**
- Consumes: Task 0's helpers.
- Produces: `list_calendar_events(start_date="", end_date="", target_upn="")`, `create_calendar_event(subject, start, end, attendees="", target_upn="")`.

- [ ] **Step 1: Write the failing tests**

```python
def test_list_calendar_events_real_mode_uses_calendarview_with_date_range():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "evt_1", "subject": "Sync", "start": {"dateTime": "2026-07-23T10:00:00"}, "end": {"dateTime": "2026-07-23T11:00:00"}}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_calendar_events("2026-07-01T00:00:00Z", "2026-07-31T00:00:00Z", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/calendarView",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params={"startDateTime": "2026-07-01T00:00:00Z", "endDateTime": "2026-07-31T00:00:00Z"}, timeout=30,
        )
        assert result["events"][0]["id"] == "evt_1"
    finally:
        m365.MOCK_MODE = True


def test_list_calendar_events_real_mode_without_range_lists_events():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": []}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            m365.list_calendar_events(target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/events",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
    finally:
        m365.MOCK_MODE = True


def test_create_calendar_event_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=201, content=b"x")
        mock_resp.json.return_value = {"id": "evt_new", "subject": "Sync", "start": {"dateTime": "2026-08-01T10:00:00Z"}, "end": {"dateTime": "2026-08-01T11:00:00Z"}}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.create_calendar_event("Sync", "2026-08-01T10:00:00Z", "2026-08-01T11:00:00Z", "a@example.com,b@example.com", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "POST", "https://graph.microsoft.com/v1.0/users/user@contoso.com/events",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json={"subject": "Sync", "start": {"dateTime": "2026-08-01T10:00:00Z", "timeZone": "UTC"},
                  "end": {"dateTime": "2026-08-01T11:00:00Z", "timeZone": "UTC"},
                  "attendees": [{"emailAddress": {"address": "a@example.com"}, "type": "required"},
                                {"emailAddress": {"address": "b@example.com"}, "type": "required"}]},
            data=None, params=None, timeout=30,
        )
        assert result["event_id"] == "evt_new"
    finally:
        m365.MOCK_MODE = True


def test_create_calendar_event_real_mode_requires_fields():
    m365.MOCK_MODE = False
    try:
        try:
            m365.create_calendar_event("", "", "")
            assert False, "expected ValueError"
        except ValueError:
            pass
    finally:
        m365.MOCK_MODE = True
```

- [ ] **Step 2: Run to verify failure**, then:

- [ ] **Step 3: Implement the real branches**

Replace the Calendar block (current lines 165-185) with:

```python
def list_calendar_events(start_date: str = "", end_date: str = "", target_upn: str = "") -> Dict[str, Any]:
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        if start_date and end_date:
            url = f"{GRAPH_BASE}/users/{upn}/calendarView"
            params = {"startDateTime": start_date, "endDateTime": end_date}
        else:
            url = f"{GRAPH_BASE}/users/{upn}/events"
            params = None
        data = _graph_request("GET", url, token, params=params)
        events = [{"id": e["id"], "subject": e.get("subject", ""), "start": e.get("start", {}).get("dateTime", ""), "end": e.get("end", {}).get("dateTime", "")} for e in data.get("value", [])]
        return {"events": events}
    events = [
        {"id": f"evt_{uuid.uuid4().hex[:10]}", "subject": "Curriculum Committee Sync", "start": start_date or "2026-07-23T10:00:00Z", "end": end_date or "2026-07-23T11:00:00Z"},
    ]
    return {"events": events}


def create_calendar_event(subject: str, start: str, end: str, attendees: str = "", target_upn: str = "") -> Dict[str, Any]:
    if not subject or not start or not end:
        raise ValueError("create_calendar_event requires subject, start, and end.")
    attendee_list = [a.strip() for a in attendees.split(",") if a.strip()]
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        body = {
            "subject": subject,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
            "attendees": [{"emailAddress": {"address": a}, "type": "required"} for a in attendee_list],
        }
        data = _graph_request("POST", f"{GRAPH_BASE}/users/{upn}/events", token, json_body=body)
        return {
            "event_id": data["id"],
            "subject": data.get("subject", subject),
            "start": data.get("start", {}).get("dateTime", start),
            "end": data.get("end", {}).get("dateTime", end),
            "attendees": attendee_list,
        }
    return {
        "event_id": f"evt_{uuid.uuid4().hex[:10]}",
        "subject": subject,
        "start": start,
        "end": end,
        "attendees": attendee_list,
    }
```

In `main()`:

```python
        elif action == "list_calendar_events":
            result = {"success": True, **list_calendar_events(params.get("start_date", ""), params.get("end_date", ""), params.get("target_upn", ""))}
        elif action == "create_calendar_event":
            result = {"success": True, **create_calendar_event(params.get("subject", ""), params.get("start", ""), params.get("end", ""), params.get("attendees", ""), params.get("target_upn", ""))}
```

- [ ] **Step 4: Update the 12_Tasks wrappers**

`12_Tasks/list_outlook_calendar_events/list_outlook_calendar_events.py` — add `target_upn: str = ""` to `run()`, forward as `list_calendar_events(...)`'s third positional arg, add to `__main__` call.

`12_Tasks/create_outlook_calendar_event/create_outlook_calendar_event.py` — add `target_upn: str = ""` to `run()`, forward as `create_calendar_event(...)`'s fifth positional arg, add to `__main__` call.

- [ ] **Step 5: Run tests**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Run: `python 12_Tasks/list_outlook_calendar_events/test_list_outlook_calendar_events.py`
Run: `python 12_Tasks/create_outlook_calendar_event/test_create_outlook_calendar_event.py`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add 14_Adapters/m365_graph_bridge/m365_graph_bridge.py 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py 12_Tasks/list_outlook_calendar_events/list_outlook_calendar_events.py 12_Tasks/create_outlook_calendar_event/create_outlook_calendar_event.py
git commit -m "feat(m365): wire Outlook calendar functions to real Graph calls"
```

---

## Task 4: Teams (list_teams, list_channels, post_channel_message, list_chat_messages, send_chat_message)

**Files:**
- Modify: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py:190-236` and `main()`'s dispatch for these five actions.
- Modify: `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
- Modify: `12_Tasks/list_teams_channels/list_teams_channels.py`
- Modify: `12_Tasks/post_teams_channel_message/post_teams_channel_message.py`
- Modify: `12_Tasks/list_teams_chat_messages/list_teams_chat_messages.py`
- Modify: `12_Tasks/send_teams_chat_message/send_teams_chat_message.py`

**Interfaces:**
- Consumes: Task 0's helpers.
- Produces: `list_teams(target_upn="")`, `list_channels(team_id)` (team-scoped, no UPN needed), `post_channel_message(team_id, channel_id, message)`, `list_chat_messages(chat_id)`, `send_chat_message(chat_id, message)`. `list_teams` has no wrapper — skip that file.

- [ ] **Step 1: Write the failing tests**

```python
def test_list_teams_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "team_1", "displayName": "Curriculum"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_teams(target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/joinedTeams",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert result["teams"][0]["name"] == "Curriculum"
    finally:
        m365.MOCK_MODE = True


def test_list_channels_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "chan_1", "displayName": "General"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_channels("team_1")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/teams/team_1/channels",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert result["channels"][0]["name"] == "General"
    finally:
        m365.MOCK_MODE = True


def test_post_channel_message_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=201, content=b"x")
        mock_resp.json.return_value = {"id": "chanmsg_1"}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.post_channel_message("team_1", "chan_1", "hello")
        mock_request.assert_called_once_with(
            "POST", "https://graph.microsoft.com/v1.0/teams/team_1/channels/chan_1/messages",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json={"body": {"content": "hello"}}, data=None, params=None, timeout=30,
        )
        assert result["message_id"] == "chanmsg_1"
        assert result["status"] == "posted"
    finally:
        m365.MOCK_MODE = True


def test_list_chat_messages_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "chatmsg_1", "from": {"user": {"displayName": "Colleague"}}, "createdDateTime": "2026-07-21T16:40:00Z", "body": {"content": "hi"}}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_chat_messages("chat_1")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/chats/chat_1/messages",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert result["messages"][0]["text"] == "hi"
    finally:
        m365.MOCK_MODE = True


def test_send_chat_message_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=201, content=b"x")
        mock_resp.json.return_value = {"id": "chatmsg_new"}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.send_chat_message("chat_1", "hi")
        mock_request.assert_called_once_with(
            "POST", "https://graph.microsoft.com/v1.0/chats/chat_1/messages",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json={"body": {"content": "hi"}}, data=None, params=None, timeout=30,
        )
        assert result["status"] == "sent"
    finally:
        m365.MOCK_MODE = True
```

- [ ] **Step 2: Run to verify failure**, then:

- [ ] **Step 3: Implement the real branches**

Replace the Teams block (current lines 190-236) with:

```python
def list_teams(target_upn: str = "") -> Dict[str, Any]:
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("GET", f"{GRAPH_BASE}/users/{upn}/joinedTeams", token)
        return {"teams": [{"id": t["id"], "name": t.get("displayName", "")} for t in data.get("value", [])]}
    teams = [
        {"id": f"team_{uuid.uuid4().hex[:10]}", "name": "Apprenticeship Curriculum"},
        {"id": f"team_{uuid.uuid4().hex[:10]}", "name": "Exam Standards Board"},
    ]
    return {"teams": teams}


def list_channels(team_id: str) -> Dict[str, Any]:
    if not team_id:
        raise ValueError("list_channels requires a team_id.")
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("GET", f"{GRAPH_BASE}/teams/{team_id}/channels", token)
        return {"team_id": team_id, "channels": [{"id": c["id"], "name": c.get("displayName", "")} for c in data.get("value", [])]}
    channels = [
        {"id": f"channel_{uuid.uuid4().hex[:10]}", "name": "General"},
        {"id": f"channel_{uuid.uuid4().hex[:10]}", "name": "Curriculum Reviews"},
    ]
    return {"team_id": team_id, "channels": channels}


def post_channel_message(team_id: str, channel_id: str, message: str) -> Dict[str, Any]:
    if not team_id or not channel_id or not message:
        raise ValueError("post_channel_message requires team_id, channel_id, and message.")
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("POST", f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages", token,
                               json_body={"body": {"content": message}})
        return {"message_id": data["id"], "status": "posted"}
    return {"message_id": f"chanmsg_{uuid.uuid4().hex[:10]}", "status": "posted (mock)"}


def list_chat_messages(chat_id: str) -> Dict[str, Any]:
    if not chat_id:
        raise ValueError("list_chat_messages requires a chat_id.")
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("GET", f"{GRAPH_BASE}/chats/{chat_id}/messages", token)
        messages = [
            {"id": m["id"], "from": (m.get("from") or {}).get("user", {}).get("displayName", ""),
             "sent": m.get("createdDateTime", ""), "text": (m.get("body") or {}).get("content", "")}
            for m in data.get("value", [])
        ]
        return {"chat_id": chat_id, "messages": messages}
    messages = [
        {"id": f"chatmsg_{uuid.uuid4().hex[:10]}", "from": "colleague@example.com", "sent": "2026-07-21T16:40:00Z", "text": "Draft looks good, one edit on section 3."},
    ]
    return {"chat_id": chat_id, "messages": messages}


def send_chat_message(chat_id: str, message: str) -> Dict[str, Any]:
    if not chat_id or not message:
        raise ValueError("send_chat_message requires chat_id and message.")
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("POST", f"{GRAPH_BASE}/chats/{chat_id}/messages", token, json_body={"body": {"content": message}})
        return {"message_id": data["id"], "status": "sent"}
    return {"message_id": f"chatmsg_{uuid.uuid4().hex[:10]}", "status": "sent (mock)"}
```

In `main()`:

```python
        elif action == "list_teams":
            result = {"success": True, **list_teams(params.get("target_upn", ""))}
        elif action == "list_channels":
            result = {"success": True, **list_channels(params.get("team_id", ""))}
        elif action == "post_channel_message":
            result = {"success": True, **post_channel_message(params.get("team_id", ""), params.get("channel_id", ""), params.get("message", ""))}
        elif action == "list_chat_messages":
            result = {"success": True, **list_chat_messages(params.get("chat_id", ""))}
        elif action == "send_chat_message":
            result = {"success": True, **send_chat_message(params.get("chat_id", ""), params.get("message", ""))}
```

(`list_channels`/`post_channel_message`/`list_chat_messages`/`send_chat_message` are team/chat-scoped, not user-scoped — no `target_upn` needed, dispatch lines unchanged from today.)

- [ ] **Step 4: Update the 12_Tasks wrappers**

`12_Tasks/list_teams_channels/list_teams_channels.py` — unchanged signature (`list_channels` took no `target_upn`); no edit needed beyond confirming it still imports/calls correctly.

`12_Tasks/post_teams_channel_message/post_teams_channel_message.py` — no signature change needed.

`12_Tasks/list_teams_chat_messages/list_teams_chat_messages.py` — no signature change needed.

`12_Tasks/send_teams_chat_message/send_teams_chat_message.py` — no signature change needed.

(These four wrappers need no edits this task — only `list_teams`, which has no wrapper, gained a `target_upn` parameter.)

- [ ] **Step 5: Run tests**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Run: `python 12_Tasks/list_teams_channels/test_list_teams_channels.py`
Run: `python 12_Tasks/post_teams_channel_message/test_post_teams_channel_message.py`
Run: `python 12_Tasks/list_teams_chat_messages/test_list_teams_chat_messages.py`
Run: `python 12_Tasks/send_teams_chat_message/test_send_teams_chat_message.py`
Expected: all pass unchanged.

- [ ] **Step 6: Commit**

```bash
git add 14_Adapters/m365_graph_bridge/m365_graph_bridge.py 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py
git commit -m "feat(m365): wire Teams functions to real Graph calls"
```

---

## Task 5: SharePoint sites/lists (list_sharepoint_sites, get_sharepoint_site, list_sharepoint_lists, list_sharepoint_list_items, create_sharepoint_list_item)

**Files:**
- Modify: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py:294-351` and `main()`'s dispatch for these five actions.
- Modify: `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
- Modify: `12_Tasks/get_sharepoint_site/get_sharepoint_site.py`
- Modify: `12_Tasks/list_sharepoint_lists/list_sharepoint_lists.py`
- Modify: `12_Tasks/list_sharepoint_list_items/list_sharepoint_list_items.py`
- Modify: `12_Tasks/create_sharepoint_list_item/create_sharepoint_list_item.py`

**Interfaces:**
- Consumes: Task 0's helpers.
- Produces: `list_sharepoint_sites(query="")`, `get_sharepoint_site(site_path)`, `list_sharepoint_lists(site_id)`, `list_sharepoint_list_items(site_id, list_id)`, `create_sharepoint_list_item(site_id, list_id, fields)`. None of these are user-scoped (`/sites/...`, not `/users/{upn}/...`) — no `target_upn` needed anywhere in this group. `list_sharepoint_sites` has no wrapper — skip that file.

- [ ] **Step 1: Write the failing tests**

```python
def test_list_sharepoint_sites_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "site_1", "displayName": "Apprenticeship Program", "webUrl": "https://x/sites/apprenticeship"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_sharepoint_sites("Exam")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/sites",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params={"search": "Exam"}, timeout=30,
        )
        assert result["sites"][0]["id"] == "site_1"
    finally:
        m365.MOCK_MODE = True


def test_get_sharepoint_site_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"id": "site_1", "displayName": "Apprenticeship", "webUrl": "https://x/sites/apprenticeship"}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.get_sharepoint_site("example.sharepoint.com:/sites/apprenticeship")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/sites/example.sharepoint.com:/sites/apprenticeship",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert result["id"] == "site_1"
    finally:
        m365.MOCK_MODE = True


def test_list_sharepoint_lists_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "list_1", "displayName": "Apprentice Intake Tracker"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_sharepoint_lists("site_1")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/sites/site_1/lists",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert result["lists"][0]["id"] == "list_1"
    finally:
        m365.MOCK_MODE = True


def test_list_sharepoint_list_items_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "item_1", "fields": {"Title": "Electrician - Period 3"}}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_sharepoint_list_items("site_1", "list_1")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/sites/site_1/lists/list_1/items",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params={"expand": "fields"}, timeout=30,
        )
        assert result["items"][0]["id"] == "item_1"
    finally:
        m365.MOCK_MODE = True


def test_create_sharepoint_list_item_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=201, content=b"x")
        mock_resp.json.return_value = {"id": "item_new", "fields": {"Title": "New Item"}}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.create_sharepoint_list_item("site_1", "list_1", {"Title": "New Item"})
        mock_request.assert_called_once_with(
            "POST", "https://graph.microsoft.com/v1.0/sites/site_1/lists/list_1/items",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json={"fields": {"Title": "New Item"}}, data=None, params=None, timeout=30,
        )
        assert result["item_id"] == "item_new"
    finally:
        m365.MOCK_MODE = True


def test_create_sharepoint_list_item_real_mode_non_2xx_raises():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=400, reason="Bad Request", text="invalid field", content=b"x")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp):
            try:
                m365.create_sharepoint_list_item("site_1", "list_1", {"Bad": "x"})
                assert False, "expected RuntimeError"
            except RuntimeError as e:
                assert "400" in str(e)
    finally:
        m365.MOCK_MODE = True
```

- [ ] **Step 2: Run to verify failure**, then:

- [ ] **Step 3: Implement the real branches**

Replace the SharePoint sites/lists block (current lines 294-351) with:

```python
def list_sharepoint_sites(query: str = "") -> Dict[str, Any]:
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("GET", f"{GRAPH_BASE}/sites", token, params={"search": query or "*"})
        sites = [{"id": s["id"], "name": s.get("displayName", s.get("name", "")), "web_url": s.get("webUrl", "")} for s in data.get("value", [])]
        return {"query": query, "sites": sites}
    sites = [
        {"id": f"site_{uuid.uuid4().hex[:10]}", "name": "Apprenticeship Program", "web_url": "https://example.sharepoint.com/sites/apprenticeship"},
        {"id": f"site_{uuid.uuid4().hex[:10]}", "name": "Exam Standards", "web_url": "https://example.sharepoint.com/sites/examstandards"},
    ]
    if query:
        sites = [s for s in sites if query.lower() in s["name"].lower()]
    return {"query": query, "sites": sites}


def get_sharepoint_site(site_path: str) -> Dict[str, Any]:
    if not site_path:
        raise ValueError("get_sharepoint_site requires a site_path (e.g. 'example.sharepoint.com:/sites/apprenticeship').")
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("GET", f"{GRAPH_BASE}/sites/{site_path}", token)
        return {"id": data["id"], "name": data.get("displayName", data.get("name", "")), "web_url": data.get("webUrl", "")}
    return {
        "id": f"site_{uuid.uuid4().hex[:10]}",
        "name": Path(site_path.rstrip("/")).name or site_path,
        "web_url": f"https://{site_path.lstrip('/')}" if not site_path.startswith("http") else site_path,
    }


def list_sharepoint_lists(site_id: str) -> Dict[str, Any]:
    if not site_id:
        raise ValueError("list_sharepoint_lists requires a site_id.")
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("GET", f"{GRAPH_BASE}/sites/{site_id}/lists", token)
        return {"site_id": site_id, "lists": [{"id": l["id"], "name": l.get("displayName", l.get("name", ""))} for l in data.get("value", [])]}
    lists = [
        {"id": f"list_{uuid.uuid4().hex[:10]}", "name": "Apprentice Intake Tracker"},
        {"id": f"list_{uuid.uuid4().hex[:10]}", "name": "Curriculum Review Status"},
    ]
    return {"site_id": site_id, "lists": lists}


def list_sharepoint_list_items(site_id: str, list_id: str) -> Dict[str, Any]:
    if not site_id or not list_id:
        raise ValueError("list_sharepoint_list_items requires site_id and list_id.")
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("GET", f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items", token, params={"expand": "fields"})
        return {"site_id": site_id, "list_id": list_id, "items": [{"id": i["id"], "fields": i.get("fields", {})} for i in data.get("value", [])]}
    items = [
        {"id": f"item_{uuid.uuid4().hex[:10]}", "fields": {"Title": "Electrician - Period 3", "Status": "In Review"}},
        {"id": f"item_{uuid.uuid4().hex[:10]}", "fields": {"Title": "Plumber - Period 2", "Status": "Approved"}},
    ]
    return {"site_id": site_id, "list_id": list_id, "items": items}


def create_sharepoint_list_item(site_id: str, list_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    if not site_id or not list_id:
        raise ValueError("create_sharepoint_list_item requires site_id and list_id.")
    if not isinstance(fields, dict) or not fields:
        raise ValueError("create_sharepoint_list_item requires a non-empty fields object.")
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("POST", f"{GRAPH_BASE}/sites/{site_id}/lists/{list_id}/items", token, json_body={"fields": fields})
        return {"item_id": data["id"], "fields": data.get("fields", fields)}
    return {"item_id": f"item_{uuid.uuid4().hex[:10]}", "fields": fields}
```

`main()` dispatch lines for these five actions are unchanged (no `target_upn` involved).

- [ ] **Step 4: No 12_Tasks wrapper signature changes needed**

None of these five functions gained a `target_upn` parameter (all site/list-scoped, not user-scoped), so `get_sharepoint_site.py`, `list_sharepoint_lists.py`, `list_sharepoint_list_items.py`, and `create_sharepoint_list_item.py` need no edits — just confirm their existing tests still pass against the new real-branch code (they exercise `MOCK_MODE=True`, unaffected).

- [ ] **Step 5: Run tests**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Run: `python 12_Tasks/get_sharepoint_site/test_get_sharepoint_site.py`
Run: `python 12_Tasks/list_sharepoint_lists/test_list_sharepoint_lists.py`
Run: `python 12_Tasks/list_sharepoint_list_items/test_list_sharepoint_list_items.py`
Run: `python 12_Tasks/create_sharepoint_list_item/test_create_sharepoint_list_item.py`
Expected: all pass unchanged.

- [ ] **Step 6: Commit**

```bash
git add 14_Adapters/m365_graph_bridge/m365_graph_bridge.py 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py
git commit -m "feat(m365): wire SharePoint sites/lists functions to real Graph calls"
```

---

## Task 6: OneNote (list_onenote_notebooks, list_onenote_pages, get_onenote_page_content, create_onenote_page)

**Files:**
- Modify: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py:356-392` and `main()`'s dispatch for these four actions.
- Modify: `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
- Modify: `12_Tasks/list_onenote_pages/list_onenote_pages.py`
- Modify: `12_Tasks/get_onenote_page_content/get_onenote_page_content.py`
- Modify: `12_Tasks/create_onenote_page/create_onenote_page.py`

**Interfaces:**
- Consumes: Task 0's helpers.
- Produces: `list_onenote_notebooks(target_upn="")`, `list_onenote_pages(notebook_id, target_upn="")`, `get_onenote_page_content(page_id, target_upn="")`, `create_onenote_page(section_id, title, content, target_upn="")`. `list_onenote_notebooks` has no wrapper — skip that file.
- **Verified against Microsoft Learn during planning:** there is no `/notebooks/{id}/pages` endpoint. Pages are queried mailbox-wide (`GET /users/{upn}/onenote/pages`) filtered by `$filter=parentNotebook/id eq '{id}'`.

- [ ] **Step 1: Write the failing tests**

```python
def test_list_onenote_notebooks_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "nb_1", "displayName": "Curriculum Committee Notes"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_onenote_notebooks(target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/onenote/notebooks",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert result["notebooks"][0]["id"] == "nb_1"
    finally:
        m365.MOCK_MODE = True


def test_list_onenote_pages_real_mode_filters_by_parent_notebook():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "page_1", "title": "Meeting Notes"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_onenote_pages("nb_1", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/onenote/pages",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params={"$filter": "parentNotebook/id eq 'nb_1'"}, timeout=30,
        )
        assert result["pages"][0]["id"] == "page_1"
    finally:
        m365.MOCK_MODE = True


def test_get_onenote_page_content_real_mode_returns_html():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"<html><body>Real content</body></html>")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.get_onenote_page_content("page_1", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/onenote/pages/page_1/content",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token"}, data=None, timeout=30,
        )
        assert "Real content" in result["content_html"]
    finally:
        m365.MOCK_MODE = True


def test_create_onenote_page_real_mode_posts_html_body():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=201, content=b"x")
        mock_resp.json.return_value = {"id": "page_new"}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.create_onenote_page("section_1", "New Page", "<p>Body</p>", target_upn="user@contoso.com")
        called_kwargs = mock_request.call_args.kwargs
        assert called_kwargs["headers"]["Content-Type"] == "text/html"
        assert b"<title>New Page</title>" in called_kwargs["data"]
        assert b"<p>Body</p>" in called_kwargs["data"]
        assert result["page_id"] == "page_new"
    finally:
        m365.MOCK_MODE = True
```

- [ ] **Step 2: Run to verify failure**, then:

- [ ] **Step 3: Implement the real branches**

Replace the OneNote block (current lines 356-392) with:

```python
def list_onenote_notebooks(target_upn: str = "") -> Dict[str, Any]:
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        data = _graph_request("GET", f"{GRAPH_BASE}/users/{upn}/onenote/notebooks", token)
        return {"notebooks": [{"id": n["id"], "name": n.get("displayName", "")} for n in data.get("value", [])]}
    notebooks = [
        {"id": f"notebook_{uuid.uuid4().hex[:10]}", "name": "Curriculum Committee Notes"},
        {"id": f"notebook_{uuid.uuid4().hex[:10]}", "name": "Exam Standards Board"},
    ]
    return {"notebooks": notebooks}


def list_onenote_pages(notebook_id: str, target_upn: str = "") -> Dict[str, Any]:
    if not notebook_id:
        raise ValueError("list_onenote_pages requires a notebook_id.")
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        # No direct /notebooks/{id}/pages endpoint exists in Graph -- pages are
        # queried mailbox-wide and filtered by parentNotebook/id (confirmed
        # against Microsoft Learn's "List onenotePages" reference).
        data = _graph_request("GET", f"{GRAPH_BASE}/users/{upn}/onenote/pages", token,
                               params={"$filter": f"parentNotebook/id eq '{notebook_id}'"})
        return {"notebook_id": notebook_id, "pages": [{"id": p["id"], "title": p.get("title", "")} for p in data.get("value", [])]}
    pages = [
        {"id": f"page_{uuid.uuid4().hex[:10]}", "title": "2026-07-20 Meeting Notes"},
        {"id": f"page_{uuid.uuid4().hex[:10]}", "title": "Action Items"},
    ]
    return {"notebook_id": notebook_id, "pages": pages}


def get_onenote_page_content(page_id: str, target_upn: str = "") -> Dict[str, Any]:
    if not page_id:
        raise ValueError("get_onenote_page_content requires a page_id.")
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        content_bytes = _graph_request_binary("GET", f"{GRAPH_BASE}/users/{upn}/onenote/pages/{page_id}/content", token)
        return {"page_id": page_id, "content_html": content_bytes.decode("utf-8", errors="replace")}
    return {"page_id": page_id, "content_html": f"<html><body><p>[MOCK OneNote content for page {page_id}]</p></body></html>"}


def create_onenote_page(section_id: str, title: str, content: str, target_upn: str = "") -> Dict[str, Any]:
    if not section_id or not title:
        raise ValueError("create_onenote_page requires section_id and title.")
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        html = f"<html><head><title>{title}</title></head><body>{content or ''}</body></html>"
        data = _graph_request("POST", f"{GRAPH_BASE}/users/{upn}/onenote/sections/{section_id}/pages", token,
                               data=html.encode("utf-8"), extra_headers={"Content-Type": "text/html"})
        return {"page_id": data["id"], "title": title, "status": "created"}
    return {"page_id": f"page_{uuid.uuid4().hex[:10]}", "title": title, "status": "created (mock)"}
```

In `main()`:

```python
        elif action == "list_onenote_notebooks":
            result = {"success": True, **list_onenote_notebooks(params.get("target_upn", ""))}
        elif action == "list_onenote_pages":
            result = {"success": True, **list_onenote_pages(params.get("notebook_id", ""), params.get("target_upn", ""))}
        elif action == "get_onenote_page_content":
            result = {"success": True, **get_onenote_page_content(params.get("page_id", ""), params.get("target_upn", ""))}
        elif action == "create_onenote_page":
            result = {"success": True, **create_onenote_page(params.get("section_id", ""), params.get("title", ""), params.get("content", ""), params.get("target_upn", ""))}
```

- [ ] **Step 4: Update the 12_Tasks wrappers**

`12_Tasks/list_onenote_pages/list_onenote_pages.py` — add `target_upn: str = ""` to `run()`, forward as `list_onenote_pages(...)`'s second positional arg, add to `__main__` call.

`12_Tasks/get_onenote_page_content/get_onenote_page_content.py` — add `target_upn: str = ""` to `run()`, forward as `get_onenote_page_content(...)`'s second positional arg, add to `__main__` call.

`12_Tasks/create_onenote_page/create_onenote_page.py` — add `target_upn: str = ""` to `run()`, forward as `create_onenote_page(...)`'s fourth positional arg, add to `__main__` call.

- [ ] **Step 5: Run tests**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Run: `python 12_Tasks/list_onenote_pages/test_list_onenote_pages.py`
Run: `python 12_Tasks/get_onenote_page_content/test_get_onenote_page_content.py`
Run: `python 12_Tasks/create_onenote_page/test_create_onenote_page.py`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add 14_Adapters/m365_graph_bridge/m365_graph_bridge.py 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py 12_Tasks/list_onenote_pages/list_onenote_pages.py 12_Tasks/get_onenote_page_content/get_onenote_page_content.py 12_Tasks/create_onenote_page/create_onenote_page.py
git commit -m "feat(m365): wire OneNote functions to real Graph calls"
```

---

## Task 7: Excel (get_excel_range, set_excel_range)

**Files:**
- Modify: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py:94-108` and `main()`'s dispatch for these two actions.
- Modify: `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
- Modify: `12_Tasks/get_excel_range/get_excel_range.py`
- Modify: `12_Tasks/set_excel_range/set_excel_range.py`

**Interfaces:**
- Consumes: Task 0's helpers.
- Produces: `get_excel_range(file_path, worksheet, range_address, target_upn="")`, `set_excel_range(file_path, worksheet, range_address, values, target_upn="")`.
- **Verified against Microsoft Learn during planning:** path-based worksheet range addressing is `GET/PATCH /drive/root:/{item-path}:/workbook/worksheets/{id|name}/range(address='{address}')`, PATCH body `{"values": [[...]]}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_get_excel_range_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"values": [["Header A", "Header B"], ["Row1 A", "Row1 B"]]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.get_excel_range("Budget.xlsx", "Sheet1", "A1:B2", target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "GET", "https://graph.microsoft.com/v1.0/users/user@contoso.com/drive/root:/Budget.xlsx:/workbook/worksheets/Sheet1/range(address='A1:B2')",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert len(result["values"]) == 2
    finally:
        m365.MOCK_MODE = True


def test_set_excel_range_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"address": "Sheet1!A1:B1", "values": [["x", "y"]]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.set_excel_range("Budget.xlsx", "Sheet1", "A1:B1", [["x", "y"]], target_upn="user@contoso.com")
        mock_request.assert_called_once_with(
            "PATCH", "https://graph.microsoft.com/v1.0/users/user@contoso.com/drive/root:/Budget.xlsx:/workbook/worksheets/Sheet1/range(address='A1:B1')",
            headers={"Authorization": "Bearer mock_sandbox_m365_bearer_token", "Accept": "application/json"},
            json={"values": [["x", "y"]]}, data=None, params=None, timeout=30,
        )
        assert result["row_count"] == 1
    finally:
        m365.MOCK_MODE = True


def test_set_excel_range_real_mode_non_2xx_raises():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=400, reason="Bad Request", text="invalid range", content=b"x")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp):
            try:
                m365.set_excel_range("Budget.xlsx", "Sheet1", "ZZ", [["x"]])
                assert False, "expected RuntimeError"
            except RuntimeError as e:
                assert "400" in str(e)
    finally:
        m365.MOCK_MODE = True
```

- [ ] **Step 2: Run to verify failure**, then:

- [ ] **Step 3: Implement the real branches**

Replace the Excel functions (current lines 94-108) with:

```python
def get_excel_range(file_path: str, worksheet: str, range_address: str, target_upn: str = "") -> Dict[str, Any]:
    if not file_path or not worksheet or not range_address:
        raise ValueError("get_excel_range requires file_path, worksheet, and range_address.")
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        path = file_path.strip("/")
        url = f"{GRAPH_BASE}/users/{upn}/drive/root:/{path}:/workbook/worksheets/{worksheet}/range(address='{range_address}')"
        data = _graph_request("GET", url, token)
        return {"values": data.get("values", [])}
    # Realistic-shaped placeholder: Graph's Workbook API returns a 2D array of cell values.
    return {"values": [["Header A", "Header B"], ["Row1 A", "Row1 B"]]}


def set_excel_range(file_path: str, worksheet: str, range_address: str, values: List[List[Any]], target_upn: str = "") -> Dict[str, Any]:
    if not file_path or not worksheet or not range_address:
        raise ValueError("set_excel_range requires file_path, worksheet, and range_address.")
    if not MOCK_MODE:
        upn = _resolve_target_upn(target_upn)
        token = EnterpriseAuthManager.get_m365_access_token({})
        path = file_path.strip("/")
        url = f"{GRAPH_BASE}/users/{upn}/drive/root:/{path}:/workbook/worksheets/{worksheet}/range(address='{range_address}')"
        data = _graph_request("PATCH", url, token, json_body={"values": values})
        return {"updated_range": data.get("address", range_address), "row_count": len(data.get("values", values or []))}
    return {"updated_range": range_address, "row_count": len(values or [])}
```

In `main()`:

```python
        elif action == "get_excel_range":
            result = {"success": True, **get_excel_range(params.get("file_path", ""), params.get("worksheet", ""), params.get("range_address", ""), params.get("target_upn", ""))}
        elif action == "set_excel_range":
            result = {"success": True, **set_excel_range(params.get("file_path", ""), params.get("worksheet", ""), params.get("range_address", ""), params.get("values", []), params.get("target_upn", ""))}
```

- [ ] **Step 4: Update the 12_Tasks wrappers**

`12_Tasks/get_excel_range/get_excel_range.py` — add `target_upn: str = ""` to `run()`, forward as `get_excel_range(...)`'s fourth positional arg, add to `__main__` call.

`12_Tasks/set_excel_range/set_excel_range.py` — add `target_upn: str = ""` to `run()`, forward as `set_excel_range(...)`'s fifth positional arg, add to `__main__` call.

- [ ] **Step 5: Run tests**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Run: `python 12_Tasks/get_excel_range/test_get_excel_range.py`
Run: `python 12_Tasks/set_excel_range/test_set_excel_range.py`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add 14_Adapters/m365_graph_bridge/m365_graph_bridge.py 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py 12_Tasks/get_excel_range/get_excel_range.py 12_Tasks/set_excel_range/set_excel_range.py
git commit -m "feat(m365): wire Excel Workbook range functions to real Graph calls"
```

---

## Task 8: Power BI (refresh_powerbi_dataset, list_powerbi_reports)

**Files:**
- Modify: `14_Adapters/m365_graph_bridge/m365_graph_bridge.py:111-125` and `main()`'s dispatch for these two actions.
- Modify: `14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
- Modify: `12_Tasks/refresh_powerbi_dataset/refresh_powerbi_dataset.py`

**Interfaces:**
- Consumes: Task 0's helpers, plus `EnterpriseAuthManager.get_powerbi_access_token` (added in Task 0).
- Produces: `refresh_powerbi_dataset(dataset_id, workspace_id="")` (new optional `workspace_id` param — most real datasets live in a named workspace, not "My Workspace"), `list_powerbi_reports(workspace_id="")`. `list_powerbi_reports` has no wrapper — skip that file. Neither function is user-scoped in the Graph `/users/{upn}` sense (Power BI's own workspace/group model), so no `target_upn` here.
- **Verified during planning:** Power BI REST API base is `https://api.powerbi.com/v1.0/myorg`, app-only auth needs the `https://analysis.windows.net/powerbi/api/.default` scope (different resource than Graph), and the Fabric admin portal must have "Allow service principals to use Power BI APIs" enabled — a tenant-side prerequisite Stage 7 will need to confirm, not something this stage can verify.

- [ ] **Step 1: Write the failing tests**

```python
def test_refresh_powerbi_dataset_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=202, content=b"")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.refresh_powerbi_dataset("dataset_123", workspace_id="ws_1")
        mock_request.assert_called_once_with(
            "POST", "https://api.powerbi.com/v1.0/myorg/groups/ws_1/datasets/dataset_123/refreshes",
            headers={"Authorization": "Bearer mock_sandbox_powerbi_bearer_token", "Accept": "application/json"},
            json={}, data=None, params=None, timeout=30,
        )
        assert result["status"] == "InProgress"
    finally:
        m365.MOCK_MODE = True


def test_refresh_powerbi_dataset_real_mode_defaults_to_my_workspace():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=202, content=b"")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            m365.refresh_powerbi_dataset("dataset_123")
        mock_request.assert_called_once_with(
            "POST", "https://api.powerbi.com/v1.0/myorg/datasets/dataset_123/refreshes",
            headers={"Authorization": "Bearer mock_sandbox_powerbi_bearer_token", "Accept": "application/json"},
            json={}, data=None, params=None, timeout=30,
        )
    finally:
        m365.MOCK_MODE = True


def test_refresh_powerbi_dataset_real_mode_non_2xx_raises():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=403, reason="Forbidden", text="no access", content=b"x")
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp):
            try:
                m365.refresh_powerbi_dataset("dataset_123")
                assert False, "expected RuntimeError"
            except RuntimeError as e:
                assert "403" in str(e)
    finally:
        m365.MOCK_MODE = True


def test_list_powerbi_reports_real_mode_constructs_request():
    m365.MOCK_MODE = False
    try:
        mock_resp = MagicMock(status_code=200, content=b"x")
        mock_resp.json.return_value = {"value": [{"id": "report_1", "name": "Regional Enrollment Trends", "datasetId": "dataset_1"}]}
        with patch("m365_graph_bridge.requests.request", return_value=mock_resp) as mock_request:
            result = m365.list_powerbi_reports("ws_1")
        mock_request.assert_called_once_with(
            "GET", "https://api.powerbi.com/v1.0/myorg/groups/ws_1/reports",
            headers={"Authorization": "Bearer mock_sandbox_powerbi_bearer_token", "Accept": "application/json"},
            json=None, data=None, params=None, timeout=30,
        )
        assert result["reports"][0]["id"] == "report_1"
    finally:
        m365.MOCK_MODE = True
```

- [ ] **Step 2: Run to verify failure**, then:

- [ ] **Step 3: Implement the real branches**

Replace the Power BI functions (current lines 111-125) with:

```python
def refresh_powerbi_dataset(dataset_id: str, workspace_id: str = "") -> Dict[str, Any]:
    if not dataset_id:
        raise ValueError("refresh_powerbi_dataset requires a dataset_id.")
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_powerbi_access_token({})
        base = f"{POWERBI_BASE}/groups/{workspace_id}" if workspace_id else POWERBI_BASE
        _graph_request("POST", f"{base}/datasets/{dataset_id}/refreshes", token, json_body={})
        # Power BI's refresh trigger returns 202 with no body -- no real refresh id
        # to report back until a follow-up GET .../refreshes lists it.
        return {"refresh_request_id": f"refresh_{uuid.uuid4().hex[:10]}", "status": "InProgress"}
    return {"refresh_request_id": f"refresh_{uuid.uuid4().hex[:10]}", "status": "Unknown (mock -- would be 'InProgress' immediately after a real trigger)"}


def list_powerbi_reports(workspace_id: str = "") -> Dict[str, Any]:
    if not MOCK_MODE:
        token = EnterpriseAuthManager.get_powerbi_access_token({})
        base = f"{POWERBI_BASE}/groups/{workspace_id}" if workspace_id else POWERBI_BASE
        data = _graph_request("GET", f"{base}/reports", token)
        return {"reports": [{"id": r["id"], "name": r.get("name", ""), "dataset_id": r.get("datasetId", "")} for r in data.get("value", [])]}
    reports = [
        {"id": f"report_{uuid.uuid4().hex[:10]}", "name": "Regional Enrollment Trends", "dataset_id": f"dataset_{uuid.uuid4().hex[:10]}"},
    ]
    return {"reports": reports}
```

In `main()`:

```python
        elif action == "refresh_powerbi_dataset":
            result = {"success": True, **refresh_powerbi_dataset(params.get("dataset_id", ""), params.get("workspace_id", ""))}
        elif action == "list_powerbi_reports":
            result = {"success": True, **list_powerbi_reports(params.get("workspace_id", ""))}
```

- [ ] **Step 4: Update the 12_Tasks wrapper**

`12_Tasks/refresh_powerbi_dataset/refresh_powerbi_dataset.py` — add `workspace_id: str = ""` to `run()`, forward as `refresh_powerbi_dataset(...)`'s second positional arg, add `workspace_id=params.get("workspace_id", "")` to the `__main__` call.

- [ ] **Step 5: Run tests**

Run: `python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py`
Run: `python 12_Tasks/refresh_powerbi_dataset/test_refresh_powerbi_dataset.py`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add 14_Adapters/m365_graph_bridge/m365_graph_bridge.py 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py 12_Tasks/refresh_powerbi_dataset/refresh_powerbi_dataset.py
git commit -m "feat(m365): wire Power BI functions to real REST API calls"
```

---

## Final Verification (after Task 8)

- [ ] Run every test file touched by this plan one more time in sequence:

```bash
python 14_Adapters/m365_graph_bridge/test_m365_graph_bridge.py
python 12_Tasks/list_m365_files/test_list_m365_files.py
python 12_Tasks/download_m365_file/test_download_m365_file.py
python 12_Tasks/upload_m365_file/test_upload_m365_file.py
python 12_Tasks/create_onedrive_sharing_link/test_create_onedrive_sharing_link.py
python 12_Tasks/send_outlook_mail/test_send_outlook_mail.py
python 12_Tasks/list_outlook_calendar_events/test_list_outlook_calendar_events.py
python 12_Tasks/create_outlook_calendar_event/test_create_outlook_calendar_event.py
python 12_Tasks/list_teams_channels/test_list_teams_channels.py
python 12_Tasks/post_teams_channel_message/test_post_teams_channel_message.py
python 12_Tasks/list_teams_chat_messages/test_list_teams_chat_messages.py
python 12_Tasks/send_teams_chat_message/test_send_teams_chat_message.py
python 12_Tasks/get_sharepoint_site/test_get_sharepoint_site.py
python 12_Tasks/list_sharepoint_lists/test_list_sharepoint_lists.py
python 12_Tasks/list_sharepoint_list_items/test_list_sharepoint_list_items.py
python 12_Tasks/create_sharepoint_list_item/test_create_sharepoint_list_item.py
python 12_Tasks/list_onenote_pages/test_list_onenote_pages.py
python 12_Tasks/get_onenote_page_content/test_get_onenote_page_content.py
python 12_Tasks/create_onenote_page/test_create_onenote_page.py
python 12_Tasks/get_excel_range/test_get_excel_range.py
python 12_Tasks/set_excel_range/test_set_excel_range.py
python 12_Tasks/refresh_powerbi_dataset/test_refresh_powerbi_dataset.py
python 00_System/tests/sandbox_smoke_test.py
```

- [ ] Confirm `M365_MOCK_MODE` is unset (or `=1`) in the dev environment and re-run the same list — everything must still pass with identical mock output, proving the mock path is untouched.
- [ ] Grep the repo for any remaining `NOT_CONFIGURED_MESSAGE` raise inside a function this plan claims to have wired, to catch a missed branch: `grep -n "NOT_CONFIGURED_MESSAGE" 14_Adapters/m365_graph_bridge/m365_graph_bridge.py` should show it only inside `generate_pptx_from_word`.
