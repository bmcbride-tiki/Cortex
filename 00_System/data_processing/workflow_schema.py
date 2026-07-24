# =============================================================================
# workflow_schema.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Defines the standard "envelope" every workflow step passes to the next --
#   a single, consistent shape for the data, attached files, and run history
#   that flows through a Cortex workflow, no matter what kind of step (a
#   Task, an AI Skill, an enterprise Adapter...) produced it. Think of it as
#   the shipping container format every building block agrees to use, so any
#   step can plug into any other step without custom wiring per pair.
#
#   The main piece is `WorkflowPayload` -- one of these gets created at the
#   start of a workflow run and a new one is produced every time a step
#   finishes (via `transition_to_next_step`), carrying forward everything
#   collected so far plus that step's new output.
#
# WHAT IT INTERACTS WITH
#   - `user_identity.py`, for `UserEntitlements`/`CapabilityFlag` -- a
#     payload's `WorkflowContext` carries the current user's license/SKU
#     entitlements along with it, so license checks can happen at any step
#     without re-resolving the user each time.
#   - `core_router.py`'s `CoreWorkflowRouter`, the main consumer -- it calls
#     `transition_to_next_step()` after every step and `validate_capability_access()`
#     before running a license-gated one.
#   - `canvas_parser.py`'s `VisualWorkflowExecutor` and `observer_transformer.py`,
#     which both read a `WorkflowPayload`'s `input`/`context`/`history` to build
#     their own views on top of it (a visual canvas run, and a pipeline map).
#   - `runtime_state.py`, which saves/loads a `WorkflowPayload` to/from disk
#     as plain JSON so a run can be paused and resumed later.
#
# KEY FUNCTIONALITY NOTES
#   - `FileReference`: a pointer to one file the workflow is working with
#     (an uploaded document, a generated report...) -- it never stores the
#     file's actual bytes, just where to find them (`uri`) and identifying
#     details (source system, filename, type).
#   - `WorkflowInputData`: the actual working data for the current step --
#     free-form key/value `data`, the list of attached `files`, and any
#     `parameters`/flags the step was configured with.
#   - `StepHistory` / `WorkflowContext.history`: a running, append-only log
#     of every step that has run so far in this workflow (which step, what
#     kind of block it was, whether it succeeded) -- this is what lets later
#     tools (like the Workflow Map's execution trace) show what actually
#     happened during a run.
#   - `WorkflowContext`: everything about the *run itself* rather than the
#     data -- which workflow, which step is current, the signed-in user's
#     license entitlements, and the history log above.
#   - `transition_to_next_step()`: the one function that actually advances a
#     workflow from one step to the next. It merges the just-finished step's
#     output into the running `data`, records what happened in `history`,
#     and returns a brand-new `WorkflowPayload` pointed at the next step --
#     carrying the same user entitlements forward rather than losing them.
# =============================================================================

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

from .user_identity import UserEntitlements, CapabilityFlag, UserIdentityManager

class FileReference(BaseModel):
    file_id: str = Field(default_factory=lambda: f"file_{uuid.uuid4().hex[:8]}")
    source: str = Field(..., description="Source system: local, m365_onedrive, m365_sharepoint, google_drive, generated")
    filename: str
    mime_type: str = "application/octet-stream"
    uri: str = Field(..., description="Vault URI or internal storage path (e.g. s3://... or vault://...)")
    external_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WorkflowInputData(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured values, extraction results, and key-value payload")
    files: List[FileReference] = Field(default_factory=list, description="Collection of file pointers attached to workflow")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Execution parameters, flags, and configuration knobs")

class StepHistory(BaseModel):
    step_id: str
    block_type: str = Field(..., description="skill | task | function | adapter")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = Field("completed", description="pending | in_progress | completed | failed")
    output_keys: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None

class WorkflowContext(BaseModel):
    workflow_id: str
    tenant_id: str = "enterprise_default"
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_step_id: str
    user_entitlements: Optional[UserEntitlements] = None
    auth_references: Dict[str, str] = Field(default_factory=dict, description="Token references or vault keys for M365/Google APIs")
    history: List[StepHistory] = Field(default_factory=list)

class WorkflowPayload(BaseModel):
    workflow_id: str
    step_id: str
    input: WorkflowInputData
    context: WorkflowContext
    output: Dict[str, Any] = Field(default_factory=dict)

    def validate_capability_access(self, required_capability: Optional[CapabilityFlag]) -> bool:
        if not required_capability:
            return True
        if not self.context.user_entitlements:
            self.context.user_entitlements = UserIdentityManager.resolve_current_user(self.context.auth_references)
        return self.context.user_entitlements.has_capability(required_capability)

    def transition_to_next_step(self, next_step_id: str, block_output: Dict[str, Any], block_type: str = "process") -> "WorkflowPayload":
        """
        Auto-wraps current block output into the 'input.data' for the next step,
        appends processing history, and returns an updated WorkflowPayload object.
        """
        self.context.history.append(
            StepHistory(
                step_id=self.step_id,
                block_type=block_type,
                status="completed",
                output_keys=list(block_output.keys())
            )
        )

        merged_data = {**self.input.data, **block_output}

        return WorkflowPayload(
            workflow_id=self.workflow_id,
            step_id=next_step_id,
            input=WorkflowInputData(
                data=merged_data,
                files=self.input.files,
                parameters=self.input.parameters
            ),
            context=WorkflowContext(
                workflow_id=self.workflow_id,
                tenant_id=self.context.tenant_id,
                correlation_id=self.context.correlation_id,
                current_step_id=next_step_id,
                user_entitlements=self.context.user_entitlements,
                auth_references=self.context.auth_references,
                history=self.context.history
            ),
            output={}
        )
