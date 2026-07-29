# =============================================================================
# sandbox_smoke_test.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A single runnable script that exercises every piece of the
#   `data_processing/` layer together, end to end, without needing the web
#   server running or a browser open. It's the fastest way to check "did my
#   change break the workflow-state/licensing/canvas machinery?" -- run it
#   directly (`python 00_System/sandbox_smoke_test.py`) and read the printed
#   output; every check is a plain Python `assert`, so it stops with a
#   traceback the moment something doesn't match what's expected.
#
#   Four independent checks run in sequence, each printing its own banner:
#     1. `test_data_flow` -- ingest two files, run them through two workflow
#        steps (a plain task, then an AI-flavored skill), confirm output
#        and file lists carry forward correctly.
#     2. `test_licensing` -- confirm a licensed block runs, an unlicensed
#        one is correctly reported as unavailable, and running an
#        unlicensed block anyway raises `PermissionError`.
#     3. `test_visual_canvas` -- build a small 3-node visual graph, confirm
#        its SVGL brand icon resolves and its nodes run/get greyed out
#        exactly as licensing dictates.
#     4. `test_observer_pipeline` -- run a short workflow, then transform
#        its resulting history into the observer pipeline view and confirm
#        the human-approval stage shows up correctly.
#
# WHAT IT INTERACTS WITH
#   - Every module in `data_processing/`: `workflow_schema.py`,
#     `enterprise_adapters.py`, `user_identity.py`, `theme_exporter.py`,
#     `canvas_schema.py`, `canvas_parser.py`, `observer_transformer.py`.
#   - `core_router.py`'s `CoreWorkflowRouter`, used to actually execute each
#     simulated workflow step.
#   - Environment variables (`CORTEX_USER_UPN`, `HAS_COPILOT_PREMIUM`,
#     `HAS_VISIO`) -- this script sets them itself mid-run to simulate
#     different signed-in users, rather than reading them from a real
#     enterprise login.
#
# KEY FUNCTIONALITY NOTES
#   - Adds `00_System` to `sys.path` first, then uses plain (non-relative)
#     imports like `from data_processing.workflow_schema import ...` -- the
#     same bootstrap pattern `server.py`/`health.py` use, so this file can
#     be run directly regardless of the current working directory.
#   - No test framework (pytest, unittest) is used -- each check is a
#     plain `async def` function called in order from `main()`.
# =============================================================================

import sys
import os
import asyncio
import uuid
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from data_processing.workflow_schema import WorkflowPayload, WorkflowInputData, WorkflowContext
from data_processing.enterprise_adapters import M365OneDriveAdapter, GoogleDriveAdapter
from data_processing.user_identity import CapabilityFlag, UserIdentityManager
from data_processing.theme_exporter import ShadCNThemePalette
from data_processing.canvas_schema import WorkflowCanvasGraph, CanvasNode, CanvasEdge, NodePosition, CanvasNodeStyle, IconSource
from data_processing.canvas_parser import VisualWorkflowExecutor
from data_processing.observer_transformer import PipelineObserverTransformer
from core_router import CoreWorkflowRouter

async def test_data_flow():
    print("--- Starting Cortex Enterprise Sandbox Verification ---")

    file1 = M365OneDriveAdapter.ingest_drive_item(
        {"id": "item_881", "name": "q3_report.pdf", "file": {"mimeType": "application/pdf"}},
        "s3://cortex-vault/sandbox/q3_report.pdf"
    )
    file2 = GoogleDriveAdapter.ingest_drive_file(
        {"id": "gitem_102", "name": "specs.json", "mimeType": "application/json"},
        "s3://cortex-vault/sandbox/specs.json"
    )

    payload = WorkflowPayload(
        workflow_id=f"wf_sb_{uuid.uuid4().hex[:6]}",
        step_id="step_0_ingest",
        input=WorkflowInputData(files=[file1, file2], data={"user": "admin@enterprise.com"}),
        context=WorkflowContext(workflow_id="wf_sb_01", current_step_id="step_0_ingest")
    )

    def parse_task_block(input_obj: WorkflowInputData):
        return {"parsed_files_count": len(input_obj.files), "parser_status": "SUCCESS"}

    async def ai_analysis_skill(input_obj: WorkflowInputData):
        await asyncio.sleep(0.01)
        return {"ai_classification": "FINANCIAL_STATEMENT", "risk_score": 0.12}

    router = CoreWorkflowRouter()

    p1 = await router.execute_block_async(parse_task_block, payload, "step_1_parser", block_type="task")
    p2 = await router.execute_block_async(ai_analysis_skill, p1, "step_2_ai_agent", block_type="skill")

    assert p2.input.data["parser_status"] == "SUCCESS"
    assert p2.input.data["ai_classification"] == "FINANCIAL_STATEMENT"
    assert len(p2.input.files) == 2
    assert len(p2.context.history) == 2

    print("--- Sandbox Verification Succeeded: Architecture Ready! ---")

async def test_licensing():
    print("\n--- Starting Cortex SSO & User Licensing Entitlement Verification ---")

    os.environ["CORTEX_USER_UPN"] = "standard_user@enterprise.com"
    os.environ["HAS_COPILOT_PREMIUM"] = "false"
    os.environ["HAS_VISIO"] = "false"

    user_ent = UserIdentityManager.resolve_current_user()
    print(f"Loaded User: {user_ent.user_principal_name}")
    print(f"Active Capabilities: {[c.value for c in user_ent.capabilities]}")

    payload = WorkflowPayload(
        workflow_id=f"wf_lic_{uuid.uuid4().hex[:6]}",
        step_id="step_0_start",
        input=WorkflowInputData(data={"initiator": user_ent.user_principal_name}),
        context=WorkflowContext(
            workflow_id="wf_lic_01",
            current_step_id="step_0_start",
            user_entitlements=user_ent
        )
    )

    router = CoreWorkflowRouter()

    def standard_m365_task(input_obj: WorkflowInputData):
        return {"status": "m365_base_success"}

    p1 = await router.execute_block_async(
        standard_m365_task, payload, "step_1_base", block_type="task", required_capability=CapabilityFlag.M365_BASE
    )
    assert p1.input.data["status"] == "m365_base_success"
    print("Base M365 block executed successfully")

    block_map = {
        "BaseIngestBlock": CapabilityFlag.M365_BASE,
        "PremiumCopilotSkill": CapabilityFlag.COPILOT_PREMIUM,
        "VisioDiagramExport": CapabilityFlag.VISIO_EXPORT
    }
    ui_status = router.get_building_block_availability(p1, block_map)
    print("\n--- UI Availability Matrix ---")
    for b_name, b_info in ui_status.items():
        print(f"Block: {b_name:<20} | Status: {b_info['status']:<12} | Required: {b_info['required_capability']}")

    assert ui_status["BaseIngestBlock"]["enabled"] is True
    assert ui_status["PremiumCopilotSkill"]["enabled"] is False
    assert ui_status["VisioDiagramExport"]["enabled"] is False

    def visio_export_block(input_obj: WorkflowInputData):
        return {"status": "visio_exported"}

    try:
        await router.execute_block_async(
            visio_export_block, p1, "step_2_visio", block_type="adapter", required_capability=CapabilityFlag.VISIO_EXPORT
        )
        assert False, "Execution should have failed with PermissionError"
    except PermissionError as e:
        print(f"Successfully intercepted unlicensed execution: {e}")

    print("\n--- All Licensing & User Layer Checks Passed! ---")

async def test_visual_canvas():
    print("\n=== Starting Cortex ShadCN UI & SVGL Visual Canvas Verification ===")

    os.environ["CORTEX_USER_UPN"] = "devops_builder@enterprise.com"
    os.environ["HAS_COPILOT_PREMIUM"] = "true"
    os.environ["HAS_VISIO"] = "false"

    user_ent = UserIdentityManager.resolve_current_user()
    print(f"Authenticated User: {user_ent.user_principal_name}")

    def mock_m365_ingest(input_obj: WorkflowInputData):
        return {"ingested_count": len(input_obj.files), "status": "FILE_PARSED"}

    def mock_copilot_premium(input_obj: WorkflowInputData):
        return {"ai_summary": "Extracted key enterprise contract risk terms."}

    def mock_visio_export(input_obj: WorkflowInputData):
        return {"visio_diagram": "EXPORTED"}

    block_registry = {
        "m365_ingest": mock_m365_ingest,
        "copilot_premium": mock_copilot_premium,
        "visio_export": mock_visio_export
    }

    graph = WorkflowCanvasGraph(
        workflow_id="wf_shadcn_001",
        theme_mode="dark",
        nodes=[
            CanvasNode(
                id="node_1",
                label="Microsoft 365 Ingestion",
                subtitle="Fetch OneDrive Contract",
                block_type="adapter",
                func_name="m365_ingest",
                required_capability=CapabilityFlag.M365_BASE.value,
                position=NodePosition(x=100, y=150),
                style=CanvasNodeStyle(
                    icon_source=IconSource.SVGL,
                    icon_name="m365",
                    badge_label="TRIGGER",
                    brand_color="#0078D4"
                )
            ),
            CanvasNode(
                id="node_2",
                label="Copilot Premium Skill",
                subtitle="AI Risk Extraction",
                block_type="skill",
                func_name="copilot_premium",
                required_capability=CapabilityFlag.COPILOT_PREMIUM.value,
                position=NodePosition(x=450, y=150),
                style=CanvasNodeStyle(
                    icon_source=IconSource.SVGL,
                    icon_name="openai",
                    badge_label="AI AGENT",
                    brand_color="#10A37F"
                )
            ),
            CanvasNode(
                id="node_3",
                label="MS Visio Flow Export",
                subtitle="Generate Diagram",
                block_type="adapter",
                func_name="visio_export",
                required_capability=CapabilityFlag.VISIO_EXPORT.value,  # Unlicensed
                position=NodePosition(x=800, y=150),
                style=CanvasNodeStyle(
                    icon_source=IconSource.SVGL,
                    icon_name="m365",
                    badge_label="EXPORT",
                    brand_color="#2B579A"
                )
            )
        ],
        edges=[
            CanvasEdge(id="e1_2", source_node_id="node_1", target_node_id="node_2", edge_label="1 file"),
            CanvasEdge(id="e2_3", source_node_id="node_2", target_node_id="node_3", edge_label="JSON payload")
        ]
    )

    assert "https://svgl.app/" in graph.nodes[0].style.svgl_url
    print(f"SVGL logo URL resolved: {graph.nodes[0].style.svgl_url}")

    dark_palette = ShadCNThemePalette.get_theme("dark")
    assert dark_palette["canvas"]["bg_color"] == "#09090B"
    print("ShadCN dark palette initialized successfully")

    file_ref = M365OneDriveAdapter.ingest_drive_item(
        {"id": "doc_99", "name": "SLA_Agreement.pdf", "file": {"mimeType": "application/pdf"}},
        "s3://cortex-vault/SLA_Agreement.pdf"
    )

    payload = WorkflowPayload(
        workflow_id="wf_shadcn_001",
        step_id="node_1",
        input=WorkflowInputData(files=[file_ref]),
        context=WorkflowContext(workflow_id="wf_shadcn_001", current_step_id="node_1", user_entitlements=user_ent)
    )

    executor = VisualWorkflowExecutor(registry=block_registry)
    await executor.execute_canvas_graph_async(graph, payload)

    assert graph.nodes[0].status == "SUCCESS"
    assert graph.nodes[1].status == "SUCCESS"
    assert graph.nodes[2].status == "GREYED_OUT"  # Visio block greyed out due to missing SKU

    print("\n--- Visual Canvas Verification Succeeded! ---")
    print(f"Node 1 [{graph.nodes[0].label}] Status: {graph.nodes[0].status}")
    print(f"Node 2 [{graph.nodes[1].label}] Status: {graph.nodes[1].status}")
    print(f"Node 3 [{graph.nodes[2].label}] Status: {graph.nodes[2].status} (Greyed Out - License Enforced)")

async def test_observer_pipeline():
    print("\n=== Starting Cortex Visual Observer Pipeline Verification ===")

    os.environ["CORTEX_USER_UPN"] = "lead_devops@enterprise.com"
    os.environ["HAS_COPILOT_PREMIUM"] = "true"
    os.environ["HAS_VISIO"] = "false"

    user_ent = UserIdentityManager.resolve_current_user()

    file_ref = M365OneDriveAdapter.ingest_drive_item(
        {"id": "doc_2026_001", "name": "project_proposal.pdf", "file": {"mimeType": "application/pdf"}},
        "s3://cortex-vault/sandbox/project_proposal.pdf"
    )

    payload = WorkflowPayload(
        workflow_id=f"wf_obs_{uuid.uuid4().hex[:6]}",
        step_id="stage_01_capture",
        input=WorkflowInputData(files=[file_ref], data={"project_slug": "no-hype-ai"}),
        context=WorkflowContext(workflow_id="wf_obs_01", current_step_id="stage_01_capture", user_entitlements=user_ent)
    )

    def classify_step(input_obj: WorkflowInputData):
        return {"route": "project_shaped", "confidence": 0.89}

    async def ai_research_step(input_obj: WorkflowInputData):
        await asyncio.sleep(0.01)
        return {"ai_summary": "Auto-research completed for project_shaped proposal."}

    router = CoreWorkflowRouter()

    p1 = await router.execute_block_async(classify_step, payload, "stage_02_classify", block_type="task")
    p2 = await router.execute_block_async(ai_research_step, p1, "stage_04_process", block_type="skill")
    p2.step_id = "human_gate"  # Move to human checkpoint

    observer_view = PipelineObserverTransformer.build_observer_view(p2, "Idea Capture & Execution Pipeline")

    assert len(observer_view.stages) == 6
    assert observer_view.stages[0].status == "COMPLETED"
    assert observer_view.stages[4].nodes[0].status == "WAITING_APPROVAL"

    print("\n--- Visual Pipeline Observer Model Generated Successfully ---")
    print(json.dumps(observer_view.model_dump(), indent=2, default=str))

    print("\n=== All Visual Observer Pipeline Verification Checks Passed! ===")

async def main():
    await test_data_flow()
    await test_licensing()
    await test_visual_canvas()
    await test_observer_pipeline()

if __name__ == "__main__":
    asyncio.run(main())
