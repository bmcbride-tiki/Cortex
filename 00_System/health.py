# =============================================================================
# health.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A basic "is the app's data-processing layer intact?" check -- tries to
#   import `data_processing`'s core modules and reports whether each one
#   loaded cleanly. Meant to be run by an external process (a container
#   orchestrator, a monitoring probe, a developer's terminal) that wants a
#   quick UP/DOWN signal without starting the full web server.
#
# WHAT IT INTERACTS WITH
#   - `data_processing/workflow_schema.py` and
#     `data_processing/enterprise_adapters.py` -- the two modules it tries
#     to import as its liveness check. A failed import of either flips the
#     overall status to `DOWN`.
#   - `Dockerfile`, which runs this file as its container health-check
#     command (`python 00_System/health.py`).
#
# KEY FUNCTIONALITY NOTES
#   - Adds `00_System` itself to `sys.path` first (same bootstrap pattern as
#     `server.py`), so `data_processing.*` imports resolve correctly no
#     matter what directory this script is launched from.
#   - `check_health()` never raises -- every import attempt is wrapped in
#     its own `try/except`, so one broken module shows up as `UNHEALTHY` in
#     the report rather than crashing the whole check.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

def check_health():
    status = {
        "status": "UP",
        "python_version": sys.version,
        "modules": {}
    }
    try:
        from data_processing.workflow_schema import WorkflowPayload  # noqa: F401
        status["modules"]["workflow_schema"] = "HEALTHY"
    except Exception as e:
        status["modules"]["workflow_schema"] = f"UNHEALTHY: {str(e)}"
        status["status"] = "DOWN"

    try:
        from data_processing.enterprise_adapters import M365OneDriveAdapter  # noqa: F401
        status["modules"]["enterprise_adapters"] = "HEALTHY"
    except Exception as e:
        status["modules"]["enterprise_adapters"] = f"UNHEALTHY: {str(e)}"
        status["status"] = "DOWN"

    return status

if __name__ == "__main__":
    print(json.dumps(check_health(), indent=2))
