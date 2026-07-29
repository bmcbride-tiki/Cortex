# =============================================================================
# abc_uploader.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   The "Agentic Workflow Uploader": manages a library of JSON workflow
#   template files (stored as text directly in the database, not as
#   separate files on disk) and can push one of them into an external
#   tool called the "Agenty Builder Console" via real browser automation
#   (Playwright), the same general approach as the Gemini/Copilot adapters.
#   Supports both a CLI (`list`/`add`/`remove`/`set-url`/`upload`) and a
#   single-JSON-payload mode for CoreRouter dispatch.
#
# WHAT IT INTERACTS WITH
#   - `00_System/database.py`'s `get_db_connection()`, reading/writing the
#     `abc_templates` (template registry) and `abc_uploader_settings`
#     (configured service URL) tables.
#   - The Agenty Builder Console web page (URL configurable via
#     `set_url`/`abc_uploader_settings`), driven with Playwright
#     (persistent Edge/Chromium profile stored outside the watched code
#     tree at `abc_uploader_browser_profile/`, same rationale as
#     `copilot_bridge`'s browser profile).
#   - `server.py`/`core_router.py`, which call this file's functions
#     directly (list/add/remove/set-url, DB-only) or dispatch `upload` as
#     an isolated subprocess (real browser automation).
# =============================================================================

import sys
sys.dont_write_bytecode = True

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parents[1]  # project root
CORE_DIR = ROOT_DIR / "00_System"

# Profile lives outside the watched code tree, same rationale as copilot_bridge's
# browser profile: keeps Playwright's constant cache/lock writes from tripping the
# Uvicorn --reload watcher if this is ever wired into the Cortex console.
USER_DATA_DIR = ROOT_DIR / "abc_uploader_browser_profile"

if str(CORE_DIR) not in sys.path:
    sys.path.append(str(CORE_DIR))

from database import get_db_connection  # type: ignore

DEFAULT_LOAD_SELECTORS = [
    "button:has-text(\"Load\")",
    "button:has-text(\"Upload\")",
    "button:has-text(\"Choose File\")",
    "button:has-text(\"Select File\")",
]
DEFAULT_FILE_INPUT_SELECTORS = [
    "input[type=\"file\"]",
]
DEFAULT_SUBMIT_SELECTORS = [
    "button:has-text(\"OK\")",
    "button:has-text(\"Submit\")",
    "button:has-text(\"Upload\")",
    "button:has-text(\"Load\")",
]

DEFAULT_SERVICE_URL = "https://agentbuilderconsole.com"


# --- Settings + template registry (brain_state.db) ---

def _ensure_settings_row(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        "INSERT OR IGNORE INTO abc_uploader_settings (id, service_url) VALUES (1, ?);",
        (DEFAULT_SERVICE_URL,),
    )


def get_service_url() -> str:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        _ensure_settings_row(cursor)
        conn.commit()
        cursor.execute("SELECT service_url FROM abc_uploader_settings WHERE id = 1;")
        row = cursor.fetchone()
        return row["service_url"] if row and row["service_url"] else ""
    finally:
        conn.close()


def set_service_url(url: str) -> None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        _ensure_settings_row(cursor)
        cursor.execute("UPDATE abc_uploader_settings SET service_url = ? WHERE id = 1;", (url.strip(),))
        conn.commit()
    finally:
        conn.close()


def list_templates() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, filename, created, updated FROM abc_templates ORDER BY name ASC;")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def add_template(content: str, filename: str, name: str, description: str = "") -> Dict[str, Any]:
    """Stores a template's raw JSON text directly in brain_state.db (no on-disk copy)."""
    name = name.strip()
    if not name:
        return {"success": False, "message": "A template name is required."}
    if not filename.lower().endswith(".json"):
        return {"success": False, "message": "Only .json template files are supported."}

    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        return {"success": False, "message": f"Template content is not valid JSON: {e}"}

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO abc_templates (name, description, filename, content)
                VALUES (?, ?, ?, ?);
            """, (name, description.strip(), filename, content))
        except sqlite3.IntegrityError:
            return {"success": False, "message": f"A template named '{name}' already exists."}
        conn.commit()
        return {"success": True, "message": f"Template '{name}' added.", "filename": filename}
    finally:
        conn.close()


def add_template_from_path(source_path: str, name: str, description: str = "") -> Dict[str, Any]:
    """CLI/router convenience wrapper: reads a local file's text then delegates to add_template."""
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        return {"success": False, "message": f"Source file not found: {source}"}
    try:
        content = source.read_text(encoding="utf-8")
    except OSError as e:
        return {"success": False, "message": f"Could not read source file: {e}"}
    return add_template(content, source.name, name, description)


def remove_template(name: str) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM abc_templates WHERE name = ?;", (name,))
        conn.commit()
        if cursor.rowcount == 0:
            return {"success": False, "message": f"No template named '{name}' found."}
        return {"success": True, "message": f"Template '{name}' removed."}
    finally:
        conn.close()


# --- Playwright upload automation ---

def _find_selector(page, selectors: List[str]):
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                return locator.first
        except Exception:
            continue
    return None


def upload_template(name: str, headless: bool = False) -> Dict[str, Any]:
    service_url = get_service_url()
    if not service_url:
        return {"success": False, "message": "No service URL configured. Run 'set-url <url>' first."}

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT filename, content FROM abc_templates WHERE name = ?;", (name,))
        row = cursor.fetchone()
    finally:
        conn.close()

    if not row:
        return {"success": False, "message": f"No template named '{name}' found."}

    filename = row["filename"]
    content_bytes = row["content"].encode("utf-8")

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(USER_DATA_DIR),
                channel="msedge",
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(USER_DATA_DIR),
                headless=headless,
            )

        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(service_url)

            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass

            load_button = _find_selector(page, DEFAULT_LOAD_SELECTORS)
            if load_button:
                try:
                    load_button.click()
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            file_input = _find_selector(page, DEFAULT_FILE_INPUT_SELECTORS)
            if not file_input:
                try:
                    page.wait_for_selector('input[type="file"]', timeout=5000)
                except Exception:
                    pass
                file_input = _find_selector(page, DEFAULT_FILE_INPUT_SELECTORS)

            if not file_input:
                return {
                    "success": False,
                    "message": (
                        "Could not locate a file input on the target page. The Agenty Builder "
                        "Console's real selectors haven't been verified yet -- update "
                        "DEFAULT_LOAD_SELECTORS / DEFAULT_FILE_INPUT_SELECTORS / DEFAULT_SUBMIT_SELECTORS "
                        "once you can inspect the live page."
                    ),
                }

            file_input.set_input_files({
                "name": filename,
                "mimeType": "application/json",
                "buffer": content_bytes,
            })
            page.wait_for_timeout(1000)

            submit_button = _find_selector(page, DEFAULT_SUBMIT_SELECTORS)
            if submit_button:
                try:
                    submit_button.click()
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            return {"success": True, "message": f"Uploaded '{name}' ({filename}) to {service_url}."}
        finally:
            context.close()


# --- CLI / CoreRouter dispatch ---

def _print_templates(templates: List[Dict[str, Any]]) -> None:
    if not templates:
        print("No templates registered yet. Use 'add <path> --name NAME' to add one.")
        return
    for t in templates:
        print(f"- {t['name']}: {t['description'] or '(no description)'} [{t['filename']}]")


def _dispatch(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if action == "list":
        return {"success": True, "templates": list_templates()}
    if action == "add":
        return add_template_from_path(params.get("path", ""), params.get("name", ""), params.get("description", ""))
    if action == "remove":
        return remove_template(params.get("name", ""))
    if action == "set_url":
        set_service_url(params.get("url", ""))
        return {"success": True, "message": "Service URL updated."}
    if action == "upload":
        return upload_template(
            params.get("name", ""),
            headless=bool(params.get("headless", False)),
        )
    return {"success": False, "message": f"Unknown action: {action}"}


def main() -> None:
    argv = sys.argv[1:]
    known_commands = {"list", "add", "remove", "set-url", "upload"}

    if not argv:
        _print_usage()
        return

    # CoreRouter-style dispatch: a single JSON payload arg, e.g. '{"action": "list"}'
    if argv[0] not in known_commands:
        try:
            params = json.loads(argv[0])
        except json.JSONDecodeError:
            _print_usage()
            return
        result = _dispatch(params.get("action", ""), params)
        print(json.dumps(result))
        return

    command = argv[0]
    rest = argv[1:]

    if command == "list":
        _print_templates(list_templates())
        return

    if command == "add":
        parser = argparse.ArgumentParser(prog="abc_uploader.py add")
        parser.add_argument("path", help="Path to the JSON template file.")
        parser.add_argument("--name", required=True, help="Short name for the template.")
        parser.add_argument("--description", default="", help="Description of the template.")
        args = parser.parse_args(rest)
        result = add_template_from_path(args.path, args.name, args.description)
        print(result["message"])
        return

    if command == "remove":
        parser = argparse.ArgumentParser(prog="abc_uploader.py remove")
        parser.add_argument("name", help="Name of the template to remove.")
        args = parser.parse_args(rest)
        result = remove_template(args.name)
        print(result["message"])
        return

    if command == "set-url":
        parser = argparse.ArgumentParser(prog="abc_uploader.py set-url")
        parser.add_argument("url", help="Agenty Builder Console URL.")
        args = parser.parse_args(rest)
        set_service_url(args.url)
        print(f"Service URL set to: {args.url}")
        return

    if command == "upload":
        parser = argparse.ArgumentParser(prog="abc_uploader.py upload")
        parser.add_argument("name", help="Name of the template to upload.")
        parser.add_argument("--headless", action="store_true", help="Run without a visible browser window.")
        args = parser.parse_args(rest)
        result = upload_template(args.name, headless=args.headless)
        print(result["message"])
        return


def _print_usage() -> None:
    print("Agentic Workflow Uploader (Agenty Builder Console)")
    print("Usage:")
    print("  python abc_uploader.py list")
    print("  python abc_uploader.py add <path> --name NAME [--description DESC]")
    print("  python abc_uploader.py remove <name>")
    print("  python abc_uploader.py set-url <url>")
    print("  python abc_uploader.py upload <name> [--headless]")
    print('  python abc_uploader.py \'{"action": "list"}\'   (CoreRouter payload mode)')


if __name__ == "__main__":
    main()
