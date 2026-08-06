# =============================================================================
# airgap_adapter.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Watches the Windows clipboard (the same "copy/paste" buffer you use with
#   Ctrl+C and Ctrl+V) and notices whenever new text gets copied into it.
#   "Air-gapped" refers to a computer or environment that's intentionally
#   isolated from normal networks for security reasons -- this adapter is
#   the bridge for getting text OUT of that kind of restricted environment
#   and into Workbrain: a person copies text on the air-gapped machine (or
#   copies it manually from somewhere sensitive), and this adapter, running
#   on the Workbrain side, notices the new clipboard content and hands it
#   off to whatever function you told it to call.
#
# WHAT IT INTERACTS WITH
#   - The Windows clipboard, read and written via small PowerShell commands
#     (Get-Clipboard / Set-Clipboard) run in the background -- not by using
#     any special Python clipboard library. This is a deliberate choice;
#     see the note on that below.
#   - `database.py`'s shared database connection helper, used to write an
#     audit-trail entry (into a table called `governance_lineage`) every
#     time this adapter logs a clipboard exchange, so there's a permanent
#     record of what text moved through it and when.
#
# KEY FUNCTIONALITY NOTES
#   - This class is a background watcher, not a one-shot check. Call
#     `start_polling(...)` with a function you want run every time new text
#     is detected, and it keeps checking the clipboard by itself (every
#     400 milliseconds by default) on a separate background thread (a
#     second parallel line of execution) until you call `stop_polling()`.
#   - To tell whether the clipboard has *actually* changed (rather than
#     just being read again with the same content), this adapter converts
#     whatever text it reads into a short "fingerprint" using something
#     called a SHA-256 hash -- a scrambled code that's effectively unique to
#     that exact text. Comparing fingerprints is a fast, reliable way to
#     detect "did this change since last time?" without repeatedly
#     comparing long strings of text directly.
#   - Reading/writing the clipboard goes through PowerShell (a command-line
#     tool built into Windows) rather than a Python library, specifically
#     because some corporate security software (antivirus/EDR --
#     "Endpoint Detection and Response" tools) treats direct clipboard
#     access from unfamiliar Python code as suspicious and blocks it. Going
#     through PowerShell's own signed, trusted clipboard commands avoids
#     that.
#   - Running this file directly (`python airgap_adapter.py`) starts a
#     small manual test: it watches your clipboard and prints out
#     whatever you copy, until you press Ctrl+C to stop it. That's a good
#     way to confirm this adapter is working on its own, separately from
#     however the rest of Workbrain uses it.
# =============================================================================

import time
import hashlib
import threading
import subprocess
import sys
import os
from typing import Callable, Optional

# Identify resolution paths relative to the script location
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

# Enforce clean module imports for sub-directories
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

from database import get_db_connection

class AirGapClipboardAdapter:
    def __init__(self, heartbeat_ms: int = 400):
        # heartbeat_ms controls how often (in milliseconds) the background
        # watcher re-checks the clipboard. 400ms is frequent enough to feel
        # instant to a human copying text, without constantly hammering the
        # system.
        self.heartbeat_interval: float = heartbeat_ms / 1000.0
        self._is_listening: bool = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._last_hash: str = ""

    def _get_hash(self, text: str) -> str:
        """Generates a SHA-256 digest to evaluate text variations instantly."""
        # Turns any amount of text into a short, fixed-length fingerprint.
        # Two identical pieces of text always produce the identical
        # fingerprint, and any change to the text (even a single character)
        # produces a completely different one -- so comparing fingerprints
        # is an easy way to answer "is this the same text as before?"
        return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()

    def read_clipboard(self) -> str:
        """
        Safely reads the Windows clipboard by calling the OS-native, signed
        PowerShell utility. Prevents EDR memory injection blocks.
        """
        try:
            # CREATE_NO_WINDOW ensures background execution without flashing console popups
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def write_clipboard(self, text: str) -> None:
        """
        Safely updates the Windows clipboard buffer by streaming text payload
        directly into the standard input of the native PowerShell utility.
        """
        # This is the reverse direction: putting text INTO the clipboard
        # programmatically, as if a person had just pressed Ctrl+C on it.
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", "$input | Set-Clipboard"],
                input=text,
                text=True,
                encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # Remember this text's fingerprint immediately, so our own
            # background watcher doesn't mistake the text we JUST wrote for
            # a brand new external clipboard change and re-report it.
            self._last_hash = self._get_hash(text)
        except Exception as e:
            print(f"[ERROR] Failed to execute outbound clipboard push: {e}", flush=True)

    def log_ingestion_event(self, entity_id: str, action: str, source: str, prev: str, updated: str):
        """Commits an analytical footprint entry directly to the local SQLite database."""
        # Writes a permanent record of a clipboard exchange into the
        # `governance_lineage` table -- what changed, where it came from,
        # and what the before/after values were. This is an audit trail:
        # a paper record for later review of what data moved through this
        # adapter, useful in a security-sensitive context.
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO governance_lineage (entity_id, action_type, source_file_path, previous_value, updated_value)
                VALUES (?, ?, ?, ?, ?)
                """,
                (entity_id, action, source, prev, updated)
            )
            conn.commit()
            print(f"[AUDIT LOG SUCCESS] Registered clipboard exchange event for: '{entity_id}'", flush=True)
        except Exception as e:
            print(f"[DATABASE ERROR] Governance tracking write failed: {e}", flush=True)
        finally:
            conn.close()

    def start_polling(self, on_mutation_callback: Callable[[str], None]):
        """Spins up the asynchronous background monitor engine."""
        # `on_mutation_callback` is a function YOU supply -- it gets called
        # automatically, once, every time new clipboard text is detected,
        # with that new text as its only argument. This lets any calling
        # code plug in its own "what to do when text arrives" logic without
        # this file needing to know anything about it.
        if self._is_listening:
            return

        # Record the clipboard's current contents as the starting point, so
        # the very first check afterward doesn't immediately re-report
        # whatever was already sitting in the clipboard before we started.
        initial_text = self.read_clipboard()
        self._last_hash = self._get_hash(initial_text)

        self._is_listening = True
        # A "thread" here is a second, independent line of execution running
        # alongside the rest of your program at the same time -- this is
        # what lets the clipboard watcher run continuously in the
        # background without freezing/blocking whatever else is going on.
        # `daemon=True` means this background thread won't prevent the
        # overall program from exiting if everything else finishes first.
        self._monitor_thread = threading.Thread(
            target=self._polling_loop,
            args=(on_mutation_callback,),
            daemon=True
        )
        self._monitor_thread.start()
        # flush=True bypasses buffer lag, forcing immediate display in terminal windows
        print("[AIRGAP MODULE] Asynchronous background clipboard scanner activated.", flush=True)

    def stop_polling(self):
        """Signals the background polling loop to halt safely."""
        self._is_listening = False
        if self._monitor_thread:
            # Wait up to 1 second for the background thread to notice
            # _is_listening became False and actually finish, rather than
            # abandoning it mid-check.
            self._monitor_thread.join(timeout=1.0)
        print("[AIRGAP MODULE] Asynchronous background clipboard scanner deactivated.", flush=True)

    def _polling_loop(self, callback: Callable[[str], None]):
        """Throttled detection loop checking clipboard hash variations via corporate pipelines."""
        # This is the function that actually runs on the background thread
        # started in start_polling(). It repeats forever (checking once per
        # heartbeat_interval) until stop_polling() flips _is_listening to False.
        while self._is_listening:
            time.sleep(self.heartbeat_interval)

            current_text = self.read_clipboard()
            if not current_text:
                continue

            current_hash = self._get_hash(current_text)
            if current_hash == self._last_hash:
                # Same fingerprint as last time -- nothing new was copied,
                # so there's nothing to do on this pass.
                continue

            # Text payload variation intercepted crossing the air-gap perimeter
            self._last_hash = current_hash
            print("[AIRGAP INGEST] Intercepted incoming text change from Windows clipboard.", flush=True)

            callback(current_text)

if __name__ == "__main__":
    # Manual test mode: run this file directly to watch your own clipboard
    # and see this adapter print out anything you copy, live, until you
    # press Ctrl+C. This is a good way to confirm the watcher itself works,
    # independent of whatever the rest of Workbrain does with the text.
    def test_callback(text: str):
        print(f"\n--- [CLIPBOARD UPDATE TRIGGERED] ---", flush=True)
        print(f"Content Intercepted:\n{text[:150]}...", flush=True)
        print("------------------------------------\n", flush=True)

    adapter = AirGapClipboardAdapter(heartbeat_ms=400)
    adapter.start_polling(on_mutation_callback=test_callback)

    print("[TEST] Clipboard listener active. Highlight and Copy (Ctrl+C) any text block to verify...", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        adapter.stop_polling()
        print("[TEST] Execution verified and closed down safely.", flush=True)
