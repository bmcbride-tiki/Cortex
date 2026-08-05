# =============================================================================
# sandbox_smoke_test.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A single runnable script that exercises every piece of the
#   `data_processing/` layer together, end to end, without needing the web
#   server running or a browser open. It's the fastest way to check "did my
#   change break the workflow-state/licensing/canvas machinery?" -- run it
#   directly (`python 00_System/tests/sandbox_smoke_test.py`) and read the printed
#   output; every check is a plain Python `assert`, so it stops with a
#   traceback the moment something doesn't match what's expected.
#
#   Two independent checks run in sequence, each printing its own banner:
#     1. `test_data_flow` -- ingest two files, run them through two workflow
#        steps (a plain task, then an AI-flavored skill), confirm output
#        and file lists carry forward correctly.
#     2. `test_licensing` -- confirm a licensed block runs, an unlicensed
#        one is correctly reported as unavailable, and running an
#        unlicensed block anyway raises `PermissionError`.
#
#   This file used to also exercise the visual-canvas and observer-pipeline
#   modules (`test_visual_canvas`, `test_observer_pipeline`). Those modules
#   were archived under `data_processing/_archive_canvas_exploration/` --
#   see that folder's README and `CORTEX_ARCHITECTURE_BLUEPRINT.md` §5 --
#   since they were never wired into the live Workflow Builder. The checks
#   were removed rather than repointed at the archive, since this script's
#   job is to guard the live path, not keep archived code green.
#
# WHAT IT INTERACTS WITH
#   - The retained modules in `data_processing/`: `workflow_schema.py`,
#     `enterprise_adapters.py`, `user_identity.py`.
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
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parents[1]
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from data_processing.workflow_schema import WorkflowPayload, WorkflowInputData, WorkflowContext
from data_processing.enterprise_adapters import M365OneDriveAdapter, GoogleDriveAdapter
from data_processing.user_identity import CapabilityFlag, UserIdentityManager
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

async def main():
    await test_data_flow()
    await test_licensing()

if __name__ == "__main__":
    asyncio.run(main())
