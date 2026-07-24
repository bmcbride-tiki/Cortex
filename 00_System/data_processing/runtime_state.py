# =============================================================================
# runtime_state.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Saves a workflow's current state to a plain JSON file on disk, and loads
#   it back later -- the mechanism that lets a long-running or paused
#   workflow be picked up again (by this process restarting, or a different
#   one) without losing track of what step it's on or what's happened so
#   far. Not a database; just a single JSON snapshot of one `WorkflowPayload`.
#
# WHAT IT INTERACTS WITH
#   - `workflow_schema.py`'s `WorkflowPayload`, the only thing this file
#     ever saves or loads -- it relies entirely on Pydantic's own
#     `model_dump_json()` / `model_validate_json()` for the actual
#     serialization, so no custom JSON handling lives here.
#   - `runtime_state.json`, written next to this file inside
#     `00_System/data_processing/` by default (overridable via the `path`
#     argument on both functions).
#
# KEY FUNCTIONALITY NOTES
#   - `save_state()` overwrites the target file every time -- there's no
#     history of past states, only the most recent one.
#   - `load_state()` raises a plain `FileNotFoundError` if nothing has been
#     saved yet; callers are expected to handle that rather than this file
#     silently returning an empty/default payload.
# =============================================================================

from pathlib import Path
from .workflow_schema import WorkflowPayload

STATE_FILE = Path(__file__).resolve().parent / "runtime_state.json"

def save_state(payload: WorkflowPayload, path: Path = STATE_FILE) -> None:
    """Persists a workflow's current step state so a run can be resumed."""
    path.write_text(payload.model_dump_json(indent=2))

def load_state(path: Path = STATE_FILE) -> WorkflowPayload:
    """Loads the last-persisted workflow state. Raises FileNotFoundError if none exists."""
    return WorkflowPayload.model_validate_json(path.read_text())
