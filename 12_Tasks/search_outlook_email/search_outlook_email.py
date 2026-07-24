# =============================================================================
# search_outlook_email.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: searches Outlook for emails by keyword and/or sender -- unlike
#   a plain folder listing, this filters.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s
#     `search_messages()`, called directly in-process (no subprocess).
#     Mock-mode until a real Azure AD app registration exists.
#   - `test_search_outlook_email.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `query`/`sender`/`folder`/`top` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import search_messages


class SearchOutlookEmail:
    """Searches Outlook for emails by topic (keyword) and/or sender -- unlike a plain
    folder listing, this filters. Reuses m365_graph_bridge's mock logic directly (no
    subprocess). Mock-mode until an Azure AD app registration exists."""

    def run(self, query: str, sender: str, folder: str, top: int) -> dict:
        try:
            return {"success": True, **search_messages(query, sender, folder, top)}
        except Exception as e:
            return {"success": False, "response": f"search_outlook_email error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"query": "...", "sender": "...", "folder": "inbox", "top": 10}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = SearchOutlookEmail().run(
            query=params.get("query", ""),
            sender=params.get("sender", ""),
            folder=params.get("folder", "") or "inbox",
            top=int(params.get("top") or 10),
        )
    except Exception as e:
        result = {"success": False, "response": f"search_outlook_email error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
