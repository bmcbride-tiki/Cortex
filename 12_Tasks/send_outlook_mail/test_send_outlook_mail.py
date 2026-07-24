# =============================================================================
# test_send_outlook_mail.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Checks that send_outlook_mail.py's `run()` returns a successful result
#   with a real-looking message ID, using m365_graph_bridge's existing
#   mock data.
#
# WHAT IT INTERACTS WITH
#   - `send_outlook_mail.py`, the file under test.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from send_outlook_mail import SendOutlookMail


def test_run_sends_mail():
    result = SendOutlookMail().run("a@example.com", "Subject", "Body")
    assert result["success"] is True
    assert result["message_id"].startswith("msg_")


if __name__ == "__main__":
    test_run_sends_mail()
    print("All send_outlook_mail self-checks passed.")
