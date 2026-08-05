# =============================================================================
# canvas_schema.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Defines the shape of an n8n-style visual workflow graph -- a list of
#   `CanvasNode`s (boxes, each with a position, an icon, and a status) and
#   `CanvasEdge`s (the lines connecting them) that together describe one
#   workflow diagram. This is a separate, standalone graph model built
#   during an early visual-canvas exploration -- it is NOT the same graph
#   format the real, running Workflow Builder page actually uses (that page
#   saves/loads a raw Drawflow.js export, parsed by `workflow_engine.py`).
#
# WHAT IT INTERACTS WITH
#   - `svgl_icon_manager.py`, which `CanvasNode.model_post_init()` calls
#     automatically to fill in a node's brand logo URL the moment the node
#     is created, if its style says `icon_source: svgl` and no URL was
#     given directly.
#   - `canvas_parser.py`'s `VisualWorkflowExecutor`, the only real consumer
#     -- it walks a `WorkflowCanvasGraph`'s `nodes` in order and runs each
#     one through `CoreWorkflowRouter`.
#   - `sandbox_smoke_test.py`, which builds a small `WorkflowCanvasGraph` by
#     hand to exercise the license-gating + SVGL icon resolution together.
#
# KEY FUNCTIONALITY NOTES
#   - `CanvasNode.status` is a plain, mutable string (`IDLE` / `RUNNING` /
#     `SUCCESS` / `FAILED` / `GREYED_OUT`) that `VisualWorkflowExecutor`
#     updates in place as it runs each node -- there's no history of past
#     statuses, only the current one.
#   - `required_capability` on a node is a plain string (a `CapabilityFlag`
#     value), not the enum itself -- `VisualWorkflowExecutor` converts it
#     back to a real `CapabilityFlag` right before checking it.
# =============================================================================

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from .svgl_icon_manager import SvglIconManager

class IconSource(str, Enum):
    SVGL = "svgl"
    LUCIDE = "lucide"

class NodePosition(BaseModel):
    x: float
    y: float

class CanvasNodeStyle(BaseModel):
    icon_source: IconSource = IconSource.SVGL
    icon_name: str                                  # e.g., "microsoft", "google-drive", "code", "bot"
    svgl_url: Optional[str] = None                   # SVGL remote or cached URL
    badge_label: Optional[str] = None                # e.g., "TRIGGER", "SKILL", "ADAPTER"
    brand_color: str = "#0078D4"

class CanvasNode(BaseModel):
    id: str
    label: str
    subtitle: Optional[str] = None
    block_type: str = Field(..., description="skill | task | function | adapter | logic")
    func_name: str
    required_capability: Optional[str] = None
    position: NodePosition
    style: CanvasNodeStyle
    status: str = Field("IDLE", description="IDLE | RUNNING | SUCCESS | FAILED | GREYED_OUT")
    node_data: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Auto-resolves SVGL URLs if source is set to SVGL."""
        if self.style.icon_source == IconSource.SVGL and not self.style.svgl_url:
            self.style.svgl_url = SvglIconManager.get_icon_url(self.style.icon_name)

class CanvasEdge(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    source_handle: Optional[str] = "output"
    target_handle: Optional[str] = "input"
    edge_label: Optional[str] = None                # e.g., "1 item", "true", "false"

class WorkflowCanvasGraph(BaseModel):
    workflow_id: str
    theme_mode: str = "dark"
    nodes: List[CanvasNode] = Field(default_factory=list)
    edges: List[CanvasEdge] = Field(default_factory=list)
