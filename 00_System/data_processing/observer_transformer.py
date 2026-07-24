# =============================================================================
# observer_transformer.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Converts a real, in-progress `WorkflowPayload` (a workflow's current
#   state plus its step-by-step history) into the fixed 6-stage
#   `PipelineObserverView` shape defined in `observer_schema.py`, so it
#   could be rendered as a visual pipeline dashboard. Given the same
#   payload's file list, step history, and current step, it works out which
#   stage each already-completed step belongs to and whether the workflow
#   is currently waiting on a human approval.
#
# WHAT IT INTERACTS WITH
#   - `workflow_schema.py`'s `WorkflowPayload`, the only input.
#   - `observer_schema.py`, for every model this file builds.
#   - `svgl_icon_manager.py`, for the brand logo attached to the ingestion
#     node and to any AI-skill step.
#   - `user_identity.py`'s `UserIdentityManager`, to resolve the current
#     user (for the human-gate node's approver name) if the payload doesn't
#     already carry resolved entitlements.
#   - `sandbox_smoke_test.py`, the only current caller of
#     `build_observer_view()`.
#
#   ⚠ Same tech-debt note as `observer_schema.py`: this transformer isn't
#   wired into any real page yet. The live Workflow Map tool computes its
#   own stage layout directly in `server.py` instead of calling this.
#
# KEY FUNCTIONALITY NOTES
#   - Distributes each history entry across stages 2-4 (Classify/Route/
#     Process) by its position in the history list (`min(idx + 1, 3)`) --
#     a simple placeholder mapping, not a real analysis of what kind of
#     work each step actually did.
#   - The human-gate stage is only marked `WAITING_APPROVAL` when the
#     payload's `step_id` is literally the string `"human_gate"` -- there's
#     no broader convention yet for which step IDs represent a checkpoint.
# =============================================================================

from datetime import datetime, timezone
from .workflow_schema import WorkflowPayload
from .observer_schema import (
    PipelineObserverView, PipelineStage, PipelineNode,
    StageStatus, PipelineNodeType, HumanGateAction, TelemetryLogEntry
)
from .svgl_icon_manager import SvglIconManager
from .user_identity import UserIdentityManager

class PipelineObserverTransformer:
    """Transforms raw WorkflowPayload state into structured visual pipeline stages for the Observer View."""

    @classmethod
    def build_observer_view(
        cls,
        payload: WorkflowPayload,
        pipeline_title: str = "Enterprise Cortex Pipeline"
    ) -> PipelineObserverView:
        user_ent = payload.context.user_entitlements or UserIdentityManager.resolve_current_user(payload.context.auth_references)

        # Define Standard 6-Stage Visual Schema (matching reference pipeline)
        stages = [
            PipelineStage(stage_number=1, stage_id="stage_01_capture", title="Stage 01: Capture", subtitle="File/Ingestion Drop"),
            PipelineStage(stage_number=2, stage_id="stage_02_classify", title="Stage 02: Classify", subtitle="Metadata & AI Classifier"),
            PipelineStage(stage_number=3, stage_id="stage_03_route", title="Stage 03: Route", subtitle="Fork & Decision Route"),
            PipelineStage(stage_number=4, stage_id="stage_04_process", title="Stage 04: Process", subtitle="Task & AI Skill Engine"),
            PipelineStage(stage_number=5, stage_id="stage_05_gate", title="Stage 05: Human Gate", subtitle="Human in the Loop Checkpoint"),
            PipelineStage(stage_number=6, stage_id="stage_06_execute", title="Stage 06: Execute", subtitle="Enterprise Adapter Export")
        ]

        # 1. Populate Stage 01: Ingestion
        files_data = [f.filename for f in payload.input.files]
        stages[0].nodes.append(
            PipelineNode(
                node_id="node_capture_01",
                stage_id="stage_01_capture",
                title="M365 / Google Ingest",
                subtitle=f"{len(payload.input.files)} files attached",
                node_type=PipelineNodeType.CAPTURE,
                icon_source="svgl",
                icon_name="microsoft",
                icon_url=SvglIconManager.get_icon_url("m365"),
                status=StageStatus.COMPLETED if payload.input.files else StageStatus.PENDING,
                payload_snapshot={"files": files_data}
            )
        )
        stages[0].status = StageStatus.COMPLETED if payload.input.files else StageStatus.PENDING

        # 2. Map History Items to Intermediate Stages
        for idx, history_step in enumerate(payload.context.history):
            target_stage_idx = min(idx + 1, 3)  # Distribute across classify, route, process

            node_status = StageStatus.COMPLETED if history_step.status == "completed" else StageStatus.FAILED

            stages[target_stage_idx].nodes.append(
                PipelineNode(
                    node_id=f"node_hist_{history_step.step_id}",
                    stage_id=stages[target_stage_idx].stage_id,
                    title=f"Step: {history_step.step_id}",
                    subtitle=f"Block Type: {history_step.block_type}",
                    node_type=PipelineNodeType.PROCESS,
                    icon_source="svgl",
                    icon_name="openai" if history_step.block_type == "skill" else "code",
                    icon_url=SvglIconManager.get_icon_url("openai") if history_step.block_type == "skill" else None,
                    status=node_status,
                    payload_snapshot={"output_keys": history_step.output_keys}
                )
            )
            stages[target_stage_idx].status = node_status

        # 3. Handle Human Gate Checkpoint Stage
        gate_status = StageStatus.WAITING_APPROVAL if payload.step_id == "human_gate" else StageStatus.PENDING
        stages[4].nodes.append(
            PipelineNode(
                node_id="node_human_gate",
                stage_id="stage_05_gate",
                title=f"{user_ent.display_name} Reviews Plan",
                subtitle="Approval Required to proceed",
                node_type=PipelineNodeType.HUMAN_GATE,
                icon_source="lucide",
                icon_name="user-check",
                status=gate_status,
                human_gate=HumanGateAction(
                    approver_upn=user_ent.user_principal_name,
                    status="PENDING" if gate_status == StageStatus.WAITING_APPROVAL else "APPROVED"
                )
            )
        )
        stages[4].status = gate_status

        # Build Telemetry Log
        telemetry = [
            TelemetryLogEntry(
                timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
                level="INFO",
                message=f"Pipeline initialized for workflow {payload.workflow_id}",
                correlation_id=payload.context.correlation_id
            ),
            TelemetryLogEntry(
                timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
                level="INFO",
                message=f"Current Step: '{payload.step_id}' - Active User: {user_ent.user_principal_name}",
                correlation_id=payload.context.correlation_id
            )
        ]

        return PipelineObserverView(
            workflow_id=payload.workflow_id,
            title=pipeline_title,
            description="Live Visual Execution Map & Human Checkpoint Observer",
            status=StageStatus.IN_PROGRESS if payload.step_id != "completed" else StageStatus.COMPLETED,
            current_stage_id=payload.step_id,
            theme_mode="dark",
            stages=stages,
            telemetry_logs=telemetry
        )
