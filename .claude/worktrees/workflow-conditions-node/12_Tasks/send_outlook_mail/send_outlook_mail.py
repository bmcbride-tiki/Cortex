# =============================================================================
# send_outlook_mail.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: sends an email via Outlook.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/m365_graph_bridge/m365_graph_bridge.py`'s `send_mail()`,
#     called directly in-process (no subprocess). Mock-mode until a real
#     Azure AD app registration exists.
#   - `test_send_outlook_mail.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `to`/`subject`/`body` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "m365_graph_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from m365_graph_bridge import send_mail


class SendOutlookMail:
    """Sends an email via Outlook. Reuses m365_graph_bridge's mock logic directly (no
    subprocess). Mock-mode until an Azure AD app registration exists."""

    def run(self, to: str, subject: str, body: str) -> dict:
        try:
            return {"success": True, **send_mail(to, subject, body)}
        except Exception as e:
            return {"success": False, "response": f"send_outlook_mail error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"to": "...", "subject": "...", "body": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = SendOutlookMail().run(to=params.get("to", ""), subject=params.get("subject", ""), body=params.get("body", ""))
    except Exception as e:
        result = {"success": False, "response": f"send_outlook_mail error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
