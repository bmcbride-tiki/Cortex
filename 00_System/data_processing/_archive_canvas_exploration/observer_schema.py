# =============================================================================
# observer_schema.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Defines the data shape for a "pipeline observer" view: a workflow drawn
#   as a fixed sequence of named stages (Capture -> Classify -> Route ->
#   Process -> Human Gate -> Execute), each holding one or more nodes with a
#   status, plus a running telemetry log. Built for a proposed n8n-style
#   execution dashboard.
#
# WHAT IT INTERACTS WITH
#   - `observer_transformer.py`, the only consumer -- it builds a
#     `PipelineObserverView` (via `PipelineObserverTransformer.build_observer_view()`)
#     out of a real `WorkflowPayload`'s history.
#   - `sandbox_smoke_test.py`, which exercises that transformer and prints
#     the resulting view as JSON.
#
#   ⚠ Tech-debt note found during this documentation pass: this schema's
#   fixed 6-stage shape is NOT what the actual, live "Workflow Map" tool
#   (`server.py`'s `/api/workflow-builder/workflows/{id}/map` endpoint) uses
#   -- that endpoint computes its own, more general stage columns directly
#   from a saved workflow's real graph (by BFS depth), independent of this
#   file. `PipelineObserverTransformer`/`PipelineObserverView` are currently
#   exercised only by the smoke test, not by any page a user can open.
#   Either wire this into a real page, or fold its useful ideas (status
#   enum, telemetry log entries) into the Workflow Map endpoint and retire
#   this one, so there aren't two competing "workflow status view" models.
#
# KEY FUNCTIONALITY NOTES
#   - `StageStatus`: the fixed set of states a stage or node can be in,
#     including `WAITING_APPROVAL` for a human-in-the-loop checkpoint and
#     `GREYED_OUT` for a licensing block.
#   - `PipelineNode.human_gate`: only set for a node representing a human
#     approval checkpoint -- carries who needs to approve it and their
#     decision so far.
# =============================================================================

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class StageStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    GREYED_OUT = "GREYED_OUT"

class PipelineNodeType(str, Enum):
    CAPTURE = "capture"
    CLASSIFY = "classify"
    ROUTE = "route"
    PROCESS = "process"
    HUMAN_GATE = "human_gate"
    EXECUTE = "execute"

class HumanGateAction(BaseModel):
    approver_upn: Optional[str] = None
    status: str = Field("PENDING", description="PENDING | APPROVED | REJECTED")
    comments: Optional[str] = None
    action_timestamp: Optional[datetime] = None

class PipelineNode(BaseModel):
    node_id: str
    stage_id: str
    title: str
    subtitle: Optional[str] = None
    node_type: PipelineNodeType
    icon_source: str = Field("svgl", description="svgl | lucide")
    icon_name: str
    icon_url: Optional[str] = None
    status: StageStatus = StageStatus.PENDING
    payload_snapshot: Dict[str, Any] = Field(default_factory=dict)
    human_gate: Optional[HumanGateAction] = None
    required_capability: Optional[str] = None
    execution_time_ms: Optional[float] = None

class PipelineStage(BaseModel):
    stage_number: int
    stage_id: str
    title: str
    subtitle: Optional[str] = None
    status: StageStatus = StageStatus.PENDING
    nodes: List[PipelineNode] = Field(default_factory=list)

class TelemetryLogEntry(BaseModel):
    timestamp: str
    level: str = "INFO"
    message: str
    correlation_id: str

class PipelineObserverView(BaseModel):
    workflow_id: str
    title: str
    description: Optional[str] = None
    status: StageStatus = StageStatus.PENDING
    current_stage_id: Optional[str] = None
    theme_mode: str = "dark"
    stages: List[PipelineStage] = Field(default_factory=list)
    telemetry_logs: List[TelemetryLogEntry] = Field(default_factory=list)
