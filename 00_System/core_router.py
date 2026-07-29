# =============================================================================
# core_router.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   This is the traffic-control layer between the Cortex web app and every
#   automation script in the project. It does two jobs:
#     1. Look around the project's folders and build a list of every
#        automation script/adapter that exists, so the Cortex web app can
#        show them as clickable items without anyone having to manually
#        register each one.
#     2. Actually run one of those scripts when asked (e.g. when someone
#        clicks a button in the Cortex web app, or a workflow step needs to
#        fire), and hand back whatever that script printed out plus whether
#        it succeeded or failed.
#
#   Think of it as a receptionist: it knows the building directory (which
#   scripts live where) and it's the one who actually walks over and knocks
#   on a script's door to run it, rather than the web app reaching into
#   the filesystem and running things directly itself.
#
# WHAT IT INTERACTS WITH
#   - `server.py`, the Cortex web app, which calls into this file's
#     `CoreRouter` class both to build its menu of available tools
#     (`get_visible_apps`) and to actually run one when the user triggers
#     it (`execute_app_logic` / `execute_script`).
#   - `11_Processes`, `12_Tasks`, `13_Workflows`, `14_Adapters` -- folders
#     this file scans to discover scripts automatically. (Internally still
#     referred to by their old category keys "05_Processes"/"06_Tasks"/
#     "07_Workflows"/"08_Adapters" -- see CATEGORY_DIR_MAP -- since the
#     frontend's API contract uses those keys and renaming them would be a
#     much wider-reaching change.) `14_Adapters` holds the AI bridge
#     adapters (`gemini_bridge/gemini_bridge.py`, `copilot_bridge/
#     copilot_bridge.py`, etc.) -- same convention as every other category,
#     no special-casing needed.
#   - Whatever Python script ends up being run -- this file launches it as
#     a completely separate operating-system process (like double-clicking
#     it, rather than importing it as a library), captures everything it
#     prints, and reports that back.
#
# KEY FUNCTIONALITY NOTES
#   - "Convention over configuration": a script is automatically recognized
#     as a runnable tool simply by living in the right folder with the
#     right filename pattern (a subfolder named `some_tool` containing
#     `some_tool.py`) -- nobody has to edit a master list anywhere to add
#     a new one.
#   - Every script gets launched as its own separate, isolated process
#     (via Python's `subprocess` module) rather than being imported and
#     called directly inside the running web server. This matters for two
#     big practical reasons: (1) if a script crashes or hangs, it can't
#     take down the whole Cortex web server with it, and (2) it protects
#     against the web server's own auto-reload behavior (it restarts
#     itself whenever project files change) interrupting a script that's
#     still mid-run.
#   - Whatever a script prints while it runs (both its normal output and
#     its error output) gets captured and combined into one big text blob
#     that gets sent back to whoever asked for it to run. IMPORTANT: normal
#     output is placed first, followed by a "[RUNTIME STDERR LOG]" marker
#     and then anything the script sent to its error channel -- so if a
#     caller is expecting a single clean line of JSON as the *whole*
#     response (several of the AI bridge adapters work exactly this way),
#     it must specifically pick out that one JSON line rather than assuming
#     the entire captured text is valid JSON, since error-channel logging
#     can legitimately follow it in this combined blob.
# =============================================================================

# 00_System_Core/core_router.py
import sys
# Globally suppress the compiled bytecode (.pyc) disk write track inside the workspace
sys.dont_write_bytecode = True

import os
import subprocess
import asyncio
import inspect
from pathlib import Path
from typing import Dict, List, Any, Tuple, Callable, Optional

from data_processing.workflow_schema import WorkflowPayload, FileReference
from data_processing.user_identity import CapabilityFlag, UserIdentityManager
from logger import CortexLogger

workflow_logger = CortexLogger.get_logger("CoreWorkflowRouter")

# Old pre-strip category names (still used as the manifest/API contract keys
# the frontend expects) mapped to where those categories actually live now.
CATEGORY_DIR_MAP: Dict[str, str] = {
    "05_Processes": "11_Processes",
    "06_Tasks": "12_Tasks",
    "07_Workflows": "13_Workflows",
    "09_Functions": "13_Functions",
    "08_Adapters": "14_Adapters",
}

# Full title overrides for tool_ids whose auto-titlecased folder name should
# never be shown as-is (e.g. "abc_uploader" -> "Abc Uploader" reads wrong).
TITLE_OVERRIDES: Dict[str, str] = {
    "abc_uploader": "ABC Builder",
}

# Words that .title() lowercases/undercapitalizes but should always render
# as a fixed acronym everywhere a title is displayed (e.g. "Tos" -> "TOS").
ACRONYM_WORDS: Dict[str, str] = {
    "tos": "TOS",
}

class CoreRouter:
    def __init__(self) -> None:
        """Initializes structural routing tracking paths relative to the system core."""
        # Everything below is computed relative to this file's own location,
        # so the router keeps working correctly no matter which folder it's
        # actually launched from.
        self.current_dir: Path = Path(__file__).resolve().parent
        self.base_dir: Path = self.current_dir.parent

    def get_visible_apps(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Dynamically scans the 11_Processes, 12_Tasks, 13_Workflows, 13_Functions, and
        14_Adapters execution category folders, auto-generating UI app manifest properties.
        """
        # This builds the data behind the Cortex web app's "Processes" page
        # (and similar) -- a dictionary describing every runnable tool found
        # on disk, grouped by category, so the web app can render a menu
        # without anything being hard-coded.
        manifest: Dict[str, List[Dict[str, Any]]] = {
            "05_Processes": [],
            "06_Tasks": [],
            "07_Workflows": [],
            "09_Functions": [],
            "08_Adapters": []
        }

        categories: List[str] = ["05_Processes", "06_Tasks", "07_Workflows", "09_Functions", "08_Adapters"]
        for cat in categories:
            cat_path: Path = self.base_dir / CATEGORY_DIR_MAP[cat]
            if not cat_path.exists():
                continue

            # Scan each script subfolder inside the category folder context.
            # Folders starting with "_" or "." are treated as private/hidden
            # and skipped, the same convention used by many file systems and
            # tools.
            for subfolder in sorted(cat_path.iterdir()):
                if subfolder.is_dir() and not subfolder.name.startswith(("_", ".")):
                    tool_id: str = subfolder.name
                    # Convert tool identifier snake case layout into a crisp title.
                    # e.g. a folder named "send_weekly_report" becomes the
                    # on-screen title "Send Weekly Report" -- except for
                    # TITLE_OVERRIDES (full rename) and ACRONYM_WORDS (fixed
                    # casing per word), which apply everywhere this manifest
                    # is consumed (Tasks page, Processes page, Workflow
                    # Builder palette).
                    if tool_id in TITLE_OVERRIDES:
                        title: str = TITLE_OVERRIDES[tool_id]
                    else:
                        words: List[str] = tool_id.replace("_", " ").title().split(" ")
                        title = " ".join(ACRONYM_WORDS.get(word.lower(), word) for word in words)

                    # Set a descriptive fallback based on folder category
                    if "Process" in cat:
                        fallback_type = "process pipeline"
                    elif "Workflow" in cat:
                        fallback_type = "multi-stage workflow"
                    elif "Adapter" in cat:
                        fallback_type = "AI bridge adapter"
                    else:
                        fallback_type = "automation task"
                    description: str = f"Dispatches the local {tool_id} engine to run specialized {fallback_type} operations."

                    # Companion documentation note lives alongside the script, same tool_id stem.
                    # Both kept vault-relative (not absolute) so mde:// / run:// links stay well-formed URIs.
                    md_path: str = (subfolder / f"{tool_id}.md").relative_to(self.base_dir).as_posix()
                    py_path: str = (subfolder / f"{tool_id}.py").relative_to(self.base_dir).as_posix()

                    manifest[cat].append({
                        "tool_id": tool_id,
                        "title": title,
                        "description": description,
                        "md_path": md_path,
                        "py_path": py_path
                    })

        return manifest

    def execute_app_logic(self, category: str, tool_id: str, args: List[Any] = None) -> Tuple[bool, str]:
        """
        Executes a targeted automation sub-script inside an isolated, safe subprocess track.
        Isolates environment and process groups to protect from parent console reloads.
        """
        # This is the main entry point the Cortex web app calls to actually
        # run something -- e.g. "run the tool named 'copilot_bridge' in
        # category '05_Processes', passing it this JSON instruction."
        if args is None:
            args = []

        tool_folder: Path = self.base_dir / CATEGORY_DIR_MAP.get(category, category) / tool_id
        script_path: Path = tool_folder / f"{tool_id}.py"

        if not script_path.exists():
            return False, f"Routing Error: Target execution script file missing at expected location:\n{script_path}"

        return self._run_script(script_path, tool_folder, args)

    def execute_script(self, script_path: Path, args: List[Any] = None) -> Tuple[bool, str]:
        """
        Executes a python script addressed by an already-resolved path, used by run://
        protocol links (e.g. the Processes page's Launch Component links). Vault
        containment is enforced upstream by server.py's _resolve_vault_path before this
        is ever called, so this only has to confirm the target is real and executable.
        """
        # A second, simpler way to trigger a script run: instead of naming
        # it by category/tool_id (which requires it to live in one of the
        # discovered folders), the caller can hand over a direct file path
        # already known to be safe. Used by the vault's internal
        # "run://some/script.py" style clickable links.
        if args is None:
            args = []

        if script_path.suffix != ".py":
            return False, f"Routing Error: run:// only executes .py files, got:\n{script_path}"

        if not script_path.exists():
            return False, f"Routing Error: Target execution script file missing at expected location:\n{script_path}"

        return self._run_script(script_path, script_path.parent, args)

    def _run_script(self, script_path: Path, cwd: Path, args: List[Any]) -> Tuple[bool, str]:
        """Shared subprocess execution track used by both category/tool_id and run:// path routing."""
        # This is the one place that actually launches a script, used by
        # both public methods above. "Subprocess" means a brand new,
        # independent program process is started (the same as if you'd
        # typed the equivalent command into a terminal yourself) rather
        # than running the script's code inside this same running program.
        try:
            # Build execution engine array arguments safely.
            # sys.executable is the exact same Python program currently
            # running this router, so the script we launch uses the
            # identical Python installation/environment.
            execution_cmd: List[str] = [sys.executable, str(script_path)] + [str(arg) for arg in args]

            # Forward complete system environment blocks to allow child processes to resolve system PATH coordinates
            sub_env = os.environ.copy()
            sub_env["PYTHONDONTWRITEBYTECODE"] = "1"

            # Windows Creation Flag: CREATE_NEW_PROCESS_GROUP = 0x00000200
            # Decouples console handles so parent reloads don't cross-propagate signals into child playwright tasks
            creationflags = 0x00000200 if os.name == 'nt' else 0

            # Fire separate process instance inside root workspace directory path.
            # capture_output=True means we get back everything the script
            # printed (both its normal output and its error output)
            # instead of it appearing directly in whatever terminal the web
            # server happens to be running in.
            result: subprocess.CompletedProcess = subprocess.run(
                execution_cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=str(cwd),
                env=sub_env,
                creationflags=creationflags
            )

            # Unpack stdout and stderr logs cleanly.
            # "stdout" is a program's normal printed output; "stderr" is its
            # separate error/diagnostic output channel. Here they're joined
            # into one combined text blob -- stdout first, then stderr (if
            # any) after a clearly labeled marker line. Callers that expect
            # a script's entire stdout to be one clean line of JSON (several
            # of the AI bridge adapters work this way) need to specifically
            # pick out that one line rather than trusting this whole
            # combined blob is valid JSON on its own, since stderr content
            # can legitimately end up appended after it.
            console_log: str = ""
            if result.stdout:
                console_log += result.stdout
            if result.stderr:
                console_log += f"\n[RUNTIME STDERR LOG]\n{result.stderr}"

            if result.returncode == 0:
                clean_output = console_log.strip() if console_log.strip() else "Process finished with zero exit state."
                return True, f"[SUCCESS]\n{clean_output}"
            else:
                return False, f"[PROCESS ABORTED] Pipeline finished with non-zero error exit code: {result.returncode}\n{console_log}"

        except Exception as err:
            return False, f"[SYSTEM ROUTING EXCEPTION] Critical sub-process tracking initialization failure: {str(err)}"


class CoreWorkflowRouter:
    """In-process step executor for the visual workflow builder, validating each
    block's input/output against the WorkflowPayload schema (00_System/data_processing/).
    Distinct from CoreRouter above, which launches 11_Processes/12_Tasks/etc. scripts
    as isolated subprocesses -- this instead runs a single in-memory block callable
    (e.g. a 13_Functions transform) against an already-validated payload.
    """
    def __init__(self, database_session: Any = None) -> None:
        self.db = database_session

    async def execute_block_async(
        self,
        block_func: Callable[[Any], Dict[str, Any]],
        payload: WorkflowPayload,
        next_step_id: str,
        block_type: str = "process",
        required_capability: Optional[CapabilityFlag] = None
    ) -> WorkflowPayload:
        """
        Asynchronously executes a building block (skill, task, or adapter),
        validates the output, appends generated file references, and transitions the payload.
        License/capability-gated blocks (required_capability set) are checked against the
        current user's entitlements before running; unlicensed access raises PermissionError.
        """
        correlation_id = payload.context.correlation_id

        if not payload.context.user_entitlements:
            payload.context.user_entitlements = UserIdentityManager.resolve_current_user(payload.context.auth_references)

        if required_capability and not payload.validate_capability_access(required_capability):
            err_msg = (
                f"Access Denied: User '{payload.context.user_entitlements.user_principal_name}' lacks required "
                f"license/capability '{required_capability.value}' for block '{block_func.__name__}'."
            )
            workflow_logger.error(err_msg, extra={"workflow_id": payload.workflow_id, "correlation_id": correlation_id})
            raise PermissionError(err_msg)

        workflow_logger.info(
            f"Executing {block_type} block at step '{payload.step_id}' (User: {payload.context.user_entitlements.user_principal_name})",
            extra={"workflow_id": payload.workflow_id, "correlation_id": correlation_id}
        )

        try:
            if inspect.iscoroutinefunction(block_func):
                block_result = await block_func(payload.input)
            else:
                block_result = block_func(payload.input)

            if not isinstance(block_result, dict):
                raise ValueError(f"Block function '{block_func.__name__}' must return a dict.")

            if "new_files" in block_result:
                for f_dict in block_result.pop("new_files"):
                    file_ref = FileReference(**f_dict) if isinstance(f_dict, dict) else f_dict
                    payload.input.files.append(file_ref)

            next_payload = payload.transition_to_next_step(
                next_step_id=next_step_id,
                block_output=block_result,
                block_type=block_type
            )

            workflow_logger.info(
                f"Successfully transitioned to step '{next_step_id}'",
                extra={"workflow_id": payload.workflow_id, "correlation_id": correlation_id}
            )
            return next_payload

        except Exception as e:
            workflow_logger.error(
                f"Error executing step '{payload.step_id}': {str(e)}",
                extra={"workflow_id": payload.workflow_id, "correlation_id": correlation_id}
            )
            raise

    def execute_block(self, block_func: Callable, payload: WorkflowPayload, next_step_id: str, block_type: str = "process") -> WorkflowPayload:
        """Synchronous wrapper for async workflow execution."""
        return asyncio.run(self.execute_block_async(block_func, payload, next_step_id, block_type))

    def get_building_block_availability(self, payload: WorkflowPayload, block_capability_map: Dict[str, CapabilityFlag]) -> Dict[str, Dict[str, Any]]:
        """
        Helper for the UI/workflow-builder view layer to determine which blocks
        should be enabled or greyed out for the current user's entitlements.
        """
        user_ent = payload.context.user_entitlements or UserIdentityManager.resolve_current_user(payload.context.auth_references)

        status_map: Dict[str, Dict[str, Any]] = {}
        for block_name, cap in block_capability_map.items():
            is_allowed = user_ent.has_capability(cap)
            status_map[block_name] = {
                "enabled": is_allowed,
                "status": "AVAILABLE" if is_allowed else "GREYED_OUT",
                "required_capability": cap.value,
                "reason": None if is_allowed else f"Requires active license/SKU for {cap.value}"
            }
        return status_map
