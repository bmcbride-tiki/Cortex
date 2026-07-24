---
tool_id: 'airgap_adapter'
title: 'Air-Gap Clipboard Adapter'
classification: '00_System_Core/adapters'
data_policy: 'protected'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, tier/zero-input, function/clipboard-bridge, scope/air-gap-ingestion, connects/database]
---

# airgap-adapter

> **Status:** Active but incomplete -- `log_ingestion_event()`'s audit-trail write targets a `governance_lineage` table that does not exist in [[database]]'s schema (see that file's Known Gap note). Calling it against a fresh database currently raises `sqlite3.OperationalError: no such table`. Not currently imported by [[server]], [[core_router]], or [[workflow_engine]] -- no wired-up caller yet.

## Purpose

Bridges text out of an air-gapped (network-isolated) environment via the Windows clipboard: a background watcher notices whenever new text is copied and hands it to a caller-supplied callback function. Reads/writes the clipboard through PowerShell's `Get-Clipboard`/`Set-Clipboard` rather than a Python clipboard library, specifically to avoid corporate EDR/antivirus software flagging direct clipboard access from unfamiliar Python code.

## Processing Logic

### `AirGapClipboardAdapter(heartbeat_ms=400)`

* `read_clipboard()` / `write_clipboard(text)` -- shell out to PowerShell (`subprocess.run(["powershell.exe", ...], creationflags=CREATE_NO_WINDOW)`) rather than touching the clipboard API directly.
* `start_polling(on_mutation_callback)` -- records the clipboard's current SHA-256 fingerprint as a baseline, then starts a daemon background thread (`_polling_loop`) that re-checks the clipboard every `heartbeat_ms` and calls `on_mutation_callback(new_text)` exactly once per detected change (fingerprint comparison, not text-diffing, so it's fast even on large clipboard contents).
* `stop_polling()` -- signals the loop to stop and joins the thread (1s timeout).
* `log_ingestion_event(entity_id, action, source, prev, updated)` -- intended to write an audit-trail row into `governance_lineage` via [[database|get_db_connection()]] -- see the Status note above; this currently fails until that table is added.

### Manual test mode

`python airgap_adapter.py` starts a live watcher printing whatever you copy, until Ctrl+C -- exercises the watcher independent of any real caller/callback.

## Output

No return value from `start_polling`/`stop_polling` -- results flow entirely through the caller-supplied callback function. `log_ingestion_event` writes to [[database|brain_state.db]] (currently broken, see Status).

## Notes for AI reuse

Before relying on `log_ingestion_event`, add a `CREATE TABLE IF NOT EXISTS governance_lineage (...)` block to [[database]]'s `initialize_database()` -- follow that file's existing numbered-comment convention when adding it. This module has no current caller wiring it into the rest of Cortex; if adopted for a real air-gap workflow, it would need a small script (following the `if __name__ == "__main__":` pattern already here) that supplies a real callback instead of the demo `test_callback`.
