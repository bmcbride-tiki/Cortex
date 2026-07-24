# =============================================================================
# canvas_parser.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   Actually RUNS a `WorkflowCanvasGraph` (see `canvas_schema.py`) -- walks
#   its nodes in order, calls each node's real Python function, and updates
#   that node's on-screen status (`SUCCESS`, `FAILED`, `GREYED_OUT`) as it
#   goes, so a visual canvas can show live per-node progress. This is the
#   missing bridge between the standalone `canvas_schema.py` graph model
#   and `core_router.py`'s actual execution engine -- nothing else in the
#   codebase connected the two until this file was written.
#
# WHAT IT INTERACTS WITH
#   - `workflow_schema.py`'s `WorkflowPayload`, the running state threaded
#     through every node it executes.
#   - `canvas_schema.py`'s `WorkflowCanvasGraph`, the graph it walks.
#   - `user_identity.py`'s `CapabilityFlag`, to convert a node's plain-string
#     `required_capability` back into a real capability enum before checking it.
#   - `core_router.py`'s `CoreWorkflowRouter`, which does the actual work --
#     this file's whole job is calling `execute_block_async()` once per
#     node and translating the result (or a `PermissionError`) into that
#     node's `status`.
#
# KEY FUNCTIONALITY NOTES
#   - Stops at the first node that fails or hits a `PermissionError`
#     (license denied) -- it does not skip a blocked node and try the next
#     one; a licensing gap or an error halts the whole run at that point,
#     with everything after it left at its default `IDLE` status.
#   - A node with no matching function in the `registry` passed to the
#     constructor is treated as a failure (`status = "FAILED"`), not an
#     error raised back to the caller.
# =============================================================================

from typing import Callable, Dict, Optional
from .workflow_schema import WorkflowPayload
from .canvas_schema import WorkflowCanvasGraph
from .user_identity import CapabilityFlag
from core_router import CoreWorkflowRouter

class VisualWorkflowExecutor:
    """Runs a WorkflowCanvasGraph's nodes in sequence through CoreWorkflowRouter,
    mapping each node's func_name to a callable via the registry and reflecting
    the execution outcome back onto the node's `status` for canvas UI rendering.
    """

    def __init__(self, registry: Dict[str, Callable]):
        self.registry = registry
        self.router = CoreWorkflowRouter()

    async def execute_canvas_graph_async(self, graph: WorkflowCanvasGraph, payload: WorkflowPayload) -> WorkflowPayload:
        current_payload = payload

        for i, node in enumerate(graph.nodes):
            block_func = self.registry.get(node.func_name)
            if block_func is None:
                node.status = "FAILED"
                break

            next_step_id = graph.nodes[i + 1].id if i + 1 < len(graph.nodes) else f"{node.id}_complete"
            required_cap: Optional[CapabilityFlag] = CapabilityFlag(node.required_capability) if node.required_capability else None

            node.status = "RUNNING"
            try:
                current_payload = await self.router.execute_block_async(
                    block_func, current_payload, next_step_id,
                    block_type=node.block_type, required_capability=required_cap
                )
                node.status = "SUCCESS"
            except PermissionError:
                node.status = "GREYED_OUT"
                break
            except Exception:
                node.status = "FAILED"
                break

        return current_payload
