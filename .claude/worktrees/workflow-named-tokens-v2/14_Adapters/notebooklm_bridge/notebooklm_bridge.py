# =============================================================================
# notebooklm_bridge.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Adapter for Google NotebookLM: create a notebook, upload sources
#   (PDF/Docx/JSON files), and ask it a sequence of questions. There is no
#   live Gemini Enterprise/NotebookLM API or MCP access wired up yet, so
#   every action runs in MOCK_MODE by default -- it returns realistic-shaped
#   fake data instead of talking to a real service. The action names,
#   parameters, and response shape are the real contract; only the inside of
#   each action function needs to change once real API/MCP access exists.
#
# WHAT IT INTERACTS WITH
#   - `core_router.py`, which is what actually runs this file when
#     `workflow_engine.py`'s NotebookLM function nodes dispatch to it (same
#     mechanism gemini_bridge.py/copilot_bridge.py use).
#
# KEY FUNCTIONALITY NOTES
#   - Every action is triggered by a small JSON instruction, e.g.
#     {"action": "create_notebook", "title": "..."}. This file always prints
#     back exactly one line of JSON describing what happened -- that's the
#     same "contract" gemini_bridge.py/copilot_bridge.py use.
#   - MOCK_MODE (env var NOTEBOOKLM_MOCK_MODE, default on) is a separate
#     concern from workflow_engine.py's own dry_run: dry_run means "don't
#     call any adapter at all yet", while MOCK_MODE means "this adapter has
#     no real backend to call yet, so simulate one realistically." With
#     MOCK_MODE off and no real backend wired in, actions fail clearly
#     instead of pretending to succeed.
#   - upload_sources still validates that every given file path is a real
#     file on disk, even in mock mode -- a real usage mistake (typo'd path)
#     should surface immediately rather than being hidden behind the mock.
# =============================================================================

# 14_Adapters/notebooklm_bridge/notebooklm_bridge.py
import sys
sys.dont_write_bytecode = True

import os
import json
import uuid
import argparse
from pathlib import Path
from typing import Any, Dict, List

MOCK_MODE = os.environ.get("NOTEBOOKLM_MOCK_MODE", "1") != "0"

NOT_CONFIGURED_MESSAGE = (
    "NotebookLM API/MCP access is not configured yet. Set NOTEBOOKLM_MOCK_MODE=1 "
    "(the default) to use simulated responses, or wire up real credentials/API "
    "calls inside notebooklm_bridge.py."
)


def create_notebook(title: str) -> Dict[str, Any]:
    if not MOCK_MODE:
        raise RuntimeError(NOT_CONFIGURED_MESSAGE)
    notebook_id = f"nb_{uuid.uuid4().hex[:12]}"
    return {"notebook_id": notebook_id, "title": title}


def upload_sources(notebook_id: str, file_paths: List[str]) -> Dict[str, Any]:
    if not MOCK_MODE:
        raise RuntimeError(NOT_CONFIGURED_MESSAGE)
    if not notebook_id:
        raise ValueError("upload_sources requires a notebook_id.")

    sources = []
    for raw_path in file_paths:
        src = Path(raw_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        sources.append({
            "source_id": f"src_{uuid.uuid4().hex[:12]}",
            "filename": src.name,
            "status": "processed",
        })
    return {"sources": sources}


def ask(notebook_id: str, prompt: str) -> Dict[str, Any]:
    if not MOCK_MODE:
        raise RuntimeError(NOT_CONFIGURED_MESSAGE)
    if not notebook_id:
        raise ValueError("ask requires a notebook_id.")
    return {"response": f"[MOCK NotebookLM response for notebook {notebook_id}] {prompt[:300]}"}


def prompt_loop(notebook_id: str, prompts: List[str]) -> Dict[str, Any]:
    if not MOCK_MODE:
        raise RuntimeError(NOT_CONFIGURED_MESSAGE)
    if not notebook_id:
        raise ValueError("prompt_loop requires a notebook_id.")

    qa_pairs = []
    for prompt_text in prompts:
        result = ask(notebook_id, prompt_text)
        qa_pairs.append({"prompt": prompt_text, "response": result["response"]})
    return {"qa_pairs": qa_pairs}


def main():
    # Expects one command-line argument: a small JSON instruction, e.g.
    #   {"action": "create_notebook", "title": "..."}
    # Always prints back exactly one line of JSON: either
    # {"success": true, ...} or {"success": false, "response": "<error>"}.
    parser = argparse.ArgumentParser(description="Workbrain NotebookLM Integration Bridge (mock-mode until real API/MCP access exists)")
    parser.add_argument("payload", nargs="?", default="", help="Inline JSON parameter from router")
    args = parser.parse_args()

    if not args.payload:
        print(json.dumps({
            "success": False,
            "response": 'No JSON payload provided. Expected: {"action": "create_notebook|upload_sources|ask|prompt_loop", ...}',
        }))
        sys.exit(1)

    try:
        params = json.loads(args.payload)
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "response": f"Malformed JSON payload: {e}"}))
        sys.exit(1)

    action = params.get("action", "")

    try:
        if action == "create_notebook":
            result = {"success": True, **create_notebook(params.get("title", "Untitled Notebook"))}
        elif action == "upload_sources":
            result = {"success": True, **upload_sources(params.get("notebook_id", ""), params.get("file_paths", []))}
        elif action == "ask":
            result = {"success": True, **ask(params.get("notebook_id", ""), params.get("prompt", ""))}
        elif action == "prompt_loop":
            result = {"success": True, **prompt_loop(params.get("notebook_id", ""), params.get("prompts", []))}
        else:
            result = {"success": False, "response": f"Unknown action: {action}"}
    except Exception as e:
        # Catch absolutely everything here rather than letting the script
        # crash with a raw Python error -- the caller (core_router.py,
        # workflow_engine.py) expects a clean JSON line back no matter what
        # went wrong.
        result = {"success": False, "response": f"NotebookLM bridge error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
