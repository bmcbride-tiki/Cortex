# =============================================================================
# server.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   This is the single central program behind the entire "Cortex" web app --
#   the thing you actually open in a browser to use Workbrain. Every page
#   you see, every button you click, and every piece of data displayed on
#   screen ultimately traces back to this file. It's built with a Python
#   web framework called FastAPI: this file defines a list of web
#   addresses ("routes", e.g. `/api/contacts`) and, for each one, exactly
#   what should happen when the browser asks for it -- read something from
#   the database, run an automation script, save an uploaded file, etc.
#
#   At roughly 1,500 lines, this is the largest file in the project. It's
#   organized as a long list of route handlers, grouped under comment
#   banners like "--- SOME SECTION NAME ---" -- skim for those banners to
#   find the part relevant to whatever you're looking for.
#
# WHAT IT INTERACTS WITH
#   - `database.py`, for every read/write against the shared `brain_state.db`
#     SQLite database (transcripts, workflows, tags, saved templates, etc.).
#   - `core_router.py`'s `CoreRouter`, used to discover which automation
#     scripts/adapters exist and to actually launch one when a button is
#     clicked.
#   - `workflow_engine.py`'s `WorkflowEngine`, used to actually run a saved
#     Workflow Builder diagram.
#   - The `templates/` folder, which holds the actual HTML/CSS/JavaScript
#     for every page -- this file serves those files to the browser, but
#     the visual page content itself lives there, not here.
#   - `01_inbox/`, `02_vault/`, and various `11_Processes/`/`12_Tasks/`/
#     `13_Workflows/`/`14_Adapters/` subfolders, for reading/writing uploaded
#     files and dispatching the automation scripts that process them.
#
# KEY FUNCTIONALITY NOTES
#   - "Route" = one specific web address FastAPI is listening for, paired
#     with a Python function that runs whenever the browser (or a
#     background fetch request from one of the page's own scripts) asks
#     for it. Look for the `@app.get(...)` / `@app.post(...)` /
#     `@app.put(...)` / `@app.delete(...)` lines throughout this file --
#     each one marks the start of a new route.
#   - This server auto-restarts itself whenever it detects a source file in
#     this project changing on disk (`reload=True` at the very bottom).
#     That's extremely convenient during development (edit a file, see the
#     change immediately), but it also means: (1) certain folders are
#     deliberately excluded from that watch list (see `reload_excludes`
#     near the bottom) because change-heavy folders there -- database
#     files, saved browser login profiles, automation script output --
#     would otherwise trigger an endless restart loop, and (2) any
#     in-progress request that takes a long time (like an AI bridge call)
#     needs to be handled carefully so it isn't left in a bad state if a
#     restart happens mid-request.
#   - A recurring, important safety pattern used in a few places
#     (`_resolve_vault_path`, the `/page/{page_name}` route) is
#     "containment checking": before reading or writing a file whose path
#     partly comes from the browser/user, the code double-checks that the
#     final, fully-resolved path is still safely inside the project's own
#     folder tree, rejecting anything that uses `..` or similar tricks to
#     try to reach outside of it. This matters because someone could
#     otherwise supply a crafted path in a web request to try to read/write
#     files far outside where they should be allowed to.
#   - Several routes call `await run_in_threadpool(some_blocking_function, ...)`
#     rather than calling that function directly. FastAPI normally runs all
#     routes on one single shared processing thread; a route that blocks
#     that thread for a long time (e.g. because it's waiting on a
#     multi-minute browser-automation call to Gemini or Copilot) would
#     freeze every other request to the entire server for as long as it
#     runs. `run_in_threadpool` hands that specific slow call off to a
#     separate background thread instead, so the main server stays
#     responsive to everyone else in the meantime.
# =============================================================================

# 00_System_Core/server.py
import sys
# Globally suppress compiled bytecode (.pyc) disk writes inside our watched path
sys.dont_write_bytecode = True

import os
import json
import time
import sqlite3
from collections import deque
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from importlib.machinery import SourceFileLoader
from typing import Any, Dict, List, Optional, AsyncGenerator
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
import uvicorn

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent

if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

# Dynamic runtime imports mapping
from core_router import CoreRouter  # type: ignore
from database import get_db_connection, initialize_database  # type: ignore
from workflow_engine import WorkflowEngine  # type: ignore
from model_classifications import CLASSIFICATION_LEVELS, CLASSIFICATION_LABELS, MODEL_CLASSIFICATIONS  # type: ignore
from data_processing.user_identity import CapabilityFlag, UserIdentityManager  # type: ignore

# 🛰️ UNIFIED LIFESPAN CONTROLLER
# FastAPI calls this once when the server first starts up (everything before
# the `yield` line) and once when it's shutting down (everything after). It's
# the natural place to put "make sure the database exists and is up to date"
# logic, since it's guaranteed to run exactly once, before any web request
# is allowed to be handled.
@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncGenerator[None, None]:
    print("\n" + "="*60)
    print("[BOOT LOG] Workbrain master console process initialized.")
    print("="*60)
    print(f"[STARTUP] Core paths verified. Active folder: {CURRENT_DIR.name}")
    
    # Safeguard database integrity on launch
    initialize_database()
    print("[STARTUP] SQLite data definitions successfully verified.")
    yield
    print("[SHUTDOWN] Workbrain master console process shutting down safely.")

# Instantiating FastAPI directly with our startup lifespan context engine
app = FastAPI(title="Workbrain Operation Console", lifespan=lifespan)
router = CoreRouter()

# --- LIVE REQUEST ACTIVITY LOG ---------------------------------------------------
# log_config=None (see uvicorn.run(...) at the bottom of this file) disables
# Uvicorn's own access-log printing entirely, to dodge a Windows-specific crash --
# but that also means the console goes silent after boot with no visibility into
# what the running app is actually doing. This middleware is a replacement: it
# wraps every single incoming request and prints one running, numbered line for
# it (method, path, status code, how long it took) regardless of Uvicorn's own
# logging setup, so clicking around Cortex or firing an automation shows up live.
_request_counter = 0


@app.middleware("http")
async def log_requests(request: Request, call_next):
    global _request_counter
    _request_counter += 1
    request_number = _request_counter

    start_time = time.perf_counter()
    print(f"[REQ #{request_number:04d}] --> {request.method} {request.url.path}", flush=True)

    response = await call_next(request)

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    print(f"[REQ #{request_number:04d}] <-- {request.method} {request.url.path} :: {response.status_code} ({elapsed_ms:.0f}ms)", flush=True)

    return response

# --- WORKFLOW BUILDER: static building-block registries -----------------------------
# The Workflow Builder page lets a user drag boxes onto a canvas and connect
# them into a pipeline (see workflow_engine.py for how a saved diagram is
# actually run). Tasks and Processes get their box options auto-discovered
# from folders on disk (via CoreRouter, see core_router.py), but "Skills" and
# "Functions" aren't separate script files -- they're small, fixed built-in
# behaviors, so their available options are just hand-written lists here.
#
# Skills have no scanned folder/script today (unlike Tasks/Processes via CoreRouter) --
# this is the single source of truth for both the Skills page and the builder palette.
SKILLS_REGISTRY = [
    {
        "tool_id": "skill_structured_data_normalization",
        "title": "Structured Data Normalization",
        "description": "Extracts messy multi-tab nested cells out of vendor sheets and reformats records into relational database keys.",
    },
    {
        "tool_id": "skill_dynamic_predictive_modeler",
        "title": "Dynamic Predictive Modeler",
        "description": "Calculates multi-year trade cohort volume estimates by processing historic intake indices against baseline horizons.",
    },
    {
        "tool_id": "skill_fts5_linguistic_search_vector",
        "title": "FTS5 Linguistic Search Vector",
        "description": "Enables live deep keyword lookups inside original Teams .docx text files matching BM25 ranking scores.",
    },
]

# Real, working "Function" node types for the Workflow Builder canvas that are
# meaningful only as part of a graph (loop-back, branching, joining multiple
# upstream nodes) or are thin wrappers around an existing Adapter (the standalone
# form already exists as that Adapter, e.g. 14_Adapters/gemini_bridge) -- anything
# genuinely standalone-capable with no existing home lives in 13_Functions instead
# (auto-discovered via CoreRouter, see the "09_Functions" merge below).
# Every AI-backed entry carries a "model" key (see model_classifications.py) so the
# Workflow Builder's model-toggle/classification panel can reason about which AI
# backends a given workflow actually touches.
#
# Note: builtin_ai_processor, builtin_formatter, function_copilot_image_generate,
# function_copilot_agent_ask, and function_copilot_list_agents used to live here --
# superseded by real Process/Task folders (11_Processes/list_copilot_agents,
# 12_Tasks/ask_copilot, ask_copilot_agent, generate_copilot_image,
# format_text_with_copilot) so each is independently runnable, same reasoning as the
# M365/Power BI reclassification. builtin_review_gate stays here -- it's graph-only
# (loop-back to another node), no standalone form makes sense, same as
# function_logic_gate/function_concatenate below.
FUNCTIONS_REGISTRY = [
    {
        "tool_id": "builtin_review_gate",
        "title": "Review Gate",
        "description": "Asks the AI bridge to judge upstream text against pass/fail criteria; on fail, loops back to an earlier node.",
        "model": "copilot",
    },
    {
        "tool_id": "function_concatenate",
        "title": "Concatenate",
        "description": "Joins every directly-connected upstream node's text together with a configurable separator.",
        "model": None,
    },
    {
        "tool_id": "function_logic_gate",
        "title": "Logic Gate (If/Else)",
        "description": "Evaluates upstream text against a condition (contains/equals/regex) and branches to a true or false node.",
        "model": None,
    },
    {
        "tool_id": "function_google_search",
        "title": "Google Search",
        "description": "Asks the Gemini bridge to run a full Deep Research pass via your signed-in Gemini session (no API key).",
        "model": "gemini",
    },
    {
        "tool_id": "function_image_generate",
        "title": "Image Generate",
        "description": "Asks the Gemini bridge to generate an image from upstream text and saves it to a configured output folder. Uses your signed-in Gemini session (no API key).",
        "model": "gemini",
    },
    {
        "tool_id": "function_gemini_ask",
        "title": "Gemini Processor",
        "description": "Sends upstream text plus your instructions to the Gemini bridge and captures its response. Uses your signed-in Gemini session (no API key).",
        "model": "gemini",
    },
    {
        "tool_id": "function_claude_ask",
        "title": "Claude Processor",
        "description": "Sends upstream text plus your instructions to the Claude bridge and captures its response. Mock-mode until a real API key exists.",
        "model": "claude",
    },
    {
        "tool_id": "function_chatgpt_ask",
        "title": "ChatGPT Processor",
        "description": "Sends upstream text plus your instructions to the ChatGPT bridge and captures its response. Mock-mode until a real API key exists.",
        "model": "chatgpt",
    },
    {
        "tool_id": "function_notebooklm_create",
        "title": "NotebookLM: Create Notebook",
        "description": "Creates a new NotebookLM notebook. Mock-mode until real API/MCP access exists -- returns a simulated notebook_id.",
        "model": "notebooklm",
    },
    {
        "tool_id": "function_notebooklm_upload_sources",
        "title": "NotebookLM: Upload Sources",
        "description": "Uploads PDF/Docx/JSON source files to a notebook. Mock-mode until real API/MCP access exists -- still validates the given file paths are real.",
        "model": "notebooklm",
    },
    {
        "tool_id": "function_notebooklm_prompt_loop",
        "title": "NotebookLM: Prompt Loop",
        "description": "Asks a notebook a sequence of questions and collects the answers as JSON (feed into Export to JSON for a stem.json file). Mock-mode until real API/MCP access exists.",
        "model": "notebooklm",
    },
]

# Note: the earlier M365/Power BI/Outlook/Teams built-in function entries that used to
# live here were superseded by real Process/Task/Function folders (see 11_Processes/,
# 12_Tasks/, 13_Functions/ -- tool_ids prefixed list_m365_teams, get_excel_range,
# send_outlook_mail, etc.) so each is independently runnable, not just a workflow-only
# wrapper. See TOOL_MODELS below for their model classification tags.

# tool_id -> model key, for Adapters (whose registry entries come from CoreRouter and
# don't carry a "model" field the way FUNCTIONS_REGISTRY entries do above).
ADAPTER_MODELS = {
    "copilot_bridge": "copilot",
    "gemini_bridge": "gemini",
    "claude_bridge": "claude",
    "chatgpt_bridge": "chatgpt",
    "notebooklm_bridge": "notebooklm",
    "m365_graph_bridge": "m365",
}

# tool_id -> model key, for Tasks and Processes (same reason as ADAPTER_MODELS above --
# their registry entries come from CoreRouter, not FUNCTIONS_REGISTRY). Every M365/Power
# BI/Outlook/Teams Process or Task is tagged "m365" EXCEPT generate_pptx_from_word_with_copilot,
# which is explicitly "copilot" -- it represents M365 Copilot's presentation-generation
# feature, not plain Graph file/data access, per the classification decision that only
# Copilot-touching M365 functions should affect a workflow's classification ceiling.
TOOL_MODELS = {
    "list_m365_teams": "m365",
    "list_powerbi_reports": "m365",
    "list_m365_files": "m365",
    "download_m365_file": "m365",
    "upload_m365_file": "m365",
    "get_excel_range": "m365",
    "set_excel_range": "m365",
    "refresh_powerbi_dataset": "m365",
    "send_outlook_mail": "m365",
    "search_outlook_email": "m365",
    "list_outlook_calendar_events": "m365",
    "create_outlook_calendar_event": "m365",
    "list_teams_channels": "m365",
    "post_teams_channel_message": "m365",
    "list_teams_chat_messages": "m365",
    "send_teams_chat_message": "m365",
    "generate_pptx_from_word_with_copilot": "copilot",
    "list_sharepoint_sites": "m365",
    "get_sharepoint_site": "m365",
    "list_sharepoint_lists": "m365",
    "list_sharepoint_list_items": "m365",
    "create_sharepoint_list_item": "m365",
    "list_onenote_notebooks": "m365",
    "list_onenote_pages": "m365",
    "get_onenote_page_content": "m365",
    "create_onenote_page": "m365",
    "list_recent_onedrive_files": "m365",
    "create_onedrive_sharing_link": "m365",
    "list_copilot_agents": "copilot",
    "ask_copilot": "copilot",
    "ask_copilot_agent": "copilot",
    "generate_copilot_image": "copilot",
    "format_text_with_copilot": "copilot",
    "ask_claude": "claude",
    "ask_chatgpt": "chatgpt",
    "ask_gemini": "gemini",
    "generate_gemini_image": "gemini",
    "create_notebooklm_notebook": "notebooklm",
    "upload_notebooklm_sources": "notebooklm",
    "run_notebooklm_prompt_loop": "notebooklm",
}

# Explicit toggle display order for the Workflow Builder's model-toggle row --
# separate from MODEL_CLASSIFICATIONS because "m365" is deliberately NOT a
# classification-affecting model (see model_classifications.py's module docstring)
# but still needs a palette-filter toggle, positioned before Copilot per user
# direction. Default-on set: m365 and copilot; everything else defaults off.
MODEL_TOGGLE_ORDER = ["m365", "copilot", "gemini", "notebooklm", "claude", "chatgpt"]
MODEL_TOGGLE_DEFAULTS = {"m365": True, "copilot": True}

# model key -> the license/SKU capability a node needs (00_System/data_processing/user_identity.py).
# Only models with a real enterprise SKU behind them are gated -- gemini/claude/chatgpt run
# through their own signed-in bridge sessions, not an M365/Google entitlement, so they stay ungated.
MODEL_CAPABILITY_MAP = {
    "m365": CapabilityFlag.M365_BASE.value,
    "copilot": CapabilityFlag.COPILOT_BASIC.value,
}

# --- Per-node iconography for the Workflow Builder palette/canvas ------------------------
# Real per-product logos (verified against the live SVGL API, https://api.svgl.app) rather
# than one blanket "Microsoft"/"Google" mark for every node -- each tool_id gets the actual
# app it talks to. Font Awesome (already vendored, templates/static/vendor/fontawesome,
# FA6 Free 6.7.2) fills in everything with no real brand logo (Power BI, NotebookLM have no
# SVGL entry; generic containers/logic/import-export get a semantic glyph). Icon names below
# were checked against the actual installed all.min.css, not guessed.
_SVGL = "https://svgl.app/library/{}.svg".format
MICROSOFT_OUTLOOK = _SVGL("microsoft-outlook")
MICROSOFT_TEAMS = _SVGL("microsoft-teams")
MICROSOFT_SHAREPOINT = _SVGL("microsoft-sharepoint")
MICROSOFT_ONENOTE = _SVGL("microsoft-onenote")
MICROSOFT_ONEDRIVE = _SVGL("microsoft-onedrive")
MICROSOFT_EXCEL = _SVGL("microsoft-excel")
MICROSOFT_POWERPOINT = _SVGL("microsoft-powerpoint")
MICROSOFT_WORD = _SVGL("microsoft-word")
MICROSOFT_COPILOT = _SVGL("microsoft-copilot")
MICROSOFT_GENERIC = _SVGL("microsoft")
GEMINI_ICON = _SVGL("gemini")
CLAUDE_ICON = _SVGL("claude-ai-icon")
OPENAI_ICON = _SVGL("openai")

# tool_id -> SVGL brand logo URL.
TOOL_SVGL_MAP: Dict[str, str] = {
    "send_outlook_mail": MICROSOFT_OUTLOOK,
    "search_outlook_email": MICROSOFT_OUTLOOK,
    "list_outlook_calendar_events": MICROSOFT_OUTLOOK,
    "create_outlook_calendar_event": MICROSOFT_OUTLOOK,
    "list_m365_teams": MICROSOFT_TEAMS,
    "list_teams_channels": MICROSOFT_TEAMS,
    "post_teams_channel_message": MICROSOFT_TEAMS,
    "list_teams_chat_messages": MICROSOFT_TEAMS,
    "send_teams_chat_message": MICROSOFT_TEAMS,
    "list_sharepoint_sites": MICROSOFT_SHAREPOINT,
    "get_sharepoint_site": MICROSOFT_SHAREPOINT,
    "list_sharepoint_lists": MICROSOFT_SHAREPOINT,
    "list_sharepoint_list_items": MICROSOFT_SHAREPOINT,
    "create_sharepoint_list_item": MICROSOFT_SHAREPOINT,
    "list_onenote_notebooks": MICROSOFT_ONENOTE,
    "list_onenote_pages": MICROSOFT_ONENOTE,
    "get_onenote_page_content": MICROSOFT_ONENOTE,
    "create_onenote_page": MICROSOFT_ONENOTE,
    "list_m365_files": MICROSOFT_ONEDRIVE,
    "download_m365_file": MICROSOFT_ONEDRIVE,
    "upload_m365_file": MICROSOFT_ONEDRIVE,
    "list_recent_onedrive_files": MICROSOFT_ONEDRIVE,
    "create_onedrive_sharing_link": MICROSOFT_ONEDRIVE,
    "get_excel_range": MICROSOFT_EXCEL,
    "set_excel_range": MICROSOFT_EXCEL,
    "read_powerpoint": MICROSOFT_POWERPOINT,
    "write_powerpoint": MICROSOFT_POWERPOINT,
    "import_from_word": MICROSOFT_WORD,
    "export_to_word": MICROSOFT_WORD,
    "fill_docx_template": MICROSOFT_WORD,
    "populate_word_template_from_json": MICROSOFT_WORD,
    "ask_copilot": MICROSOFT_COPILOT,
    "ask_copilot_agent": MICROSOFT_COPILOT,
    "list_copilot_agents": MICROSOFT_COPILOT,
    "generate_copilot_image": MICROSOFT_COPILOT,
    "format_text_with_copilot": MICROSOFT_COPILOT,
    "generate_pptx_from_word_with_copilot": MICROSOFT_COPILOT,
    "copilot_bridge": MICROSOFT_COPILOT,
    "m365_graph_bridge": MICROSOFT_GENERIC,
    "gemini_bridge": GEMINI_ICON,
    "function_gemini_ask": GEMINI_ICON,
    "function_google_search": GEMINI_ICON,
    "function_image_generate": GEMINI_ICON,
    "claude_bridge": CLAUDE_ICON,
    "function_claude_ask": CLAUDE_ICON,
    "chatgpt_bridge": OPENAI_ICON,
    "function_chatgpt_ask": OPENAI_ICON,
    "ask_claude": CLAUDE_ICON,
    "ask_chatgpt": OPENAI_ICON,
    "ask_gemini": GEMINI_ICON,
    "generate_gemini_image": GEMINI_ICON,
}

# tool_id -> Font Awesome 6 Free solid glyph (no "fa-solid" prefix), for every node with no
# real brand logo. Grouped by what the icon is standing in for.
TOOL_FA_ICON_MAP: Dict[str, str] = {
    # Control flow / structure
    "function_logic_gate": "fa-signs-post",       # if/else branch -- literal signpost
    "builtin_review_gate": "fa-repeat",           # loops back to an earlier node on fail
    "human_review_checkpoint": "fa-user-check",
    "generate_vault_map": "fa-folder-tree",
    # Output / data-shape (the "{}" family)
    "export_to_json": "fa-file-code",
    "format_json": "fa-file-code",
    "import_from_json": "fa-file-code",
    "export_to_markdown": "fa-markdown",
    "export_to_pdf": "fa-file-pdf",
    "import_from_pdf": "fa-file-pdf",
    # Conversion (one file format into another)
    "curriculum_guide_to_tos": "fa-right-left",
    "word_to_excel_exam": "fa-right-left",
    "abc_uploader": "fa-right-left",
    # Generic import (no single obvious file type/brand)
    "import_documents": "fa-file-import",
    "import_transcripts": "fa-file-import",
    "import_exam_pass_fail": "fa-file-import",
    "import_marks_correlation": "fa-file-import",
    # Web scraping
    "webscraper": "fa-spider",
    "web_scrape": "fa-spider",
    # Power BI / NotebookLM -- no SVGL logo exists for either
    "list_powerbi_reports": "fa-chart-column",
    "refresh_powerbi_dataset": "fa-chart-column",
    "notebooklm_bridge": "fa-book-open",
    "function_notebooklm_create": "fa-book-open",
    "function_notebooklm_upload_sources": "fa-book-open",
    "function_notebooklm_prompt_loop": "fa-book-open",
    "create_notebooklm_notebook": "fa-book-open",
    "upload_notebooklm_sources": "fa-book-open",
    "run_notebooklm_prompt_loop": "fa-book-open",
    # Text utilities
    "function_concatenate": "fa-link",
    "split_text": "fa-arrows-split-up-and-left",
    # Skills (generic "AI capability", distinct from raw code/function blocks)
    "skill_structured_data_normalization": "fa-wand-magic-sparkles",
    "skill_dynamic_predictive_modeler": "fa-wand-magic-sparkles",
    "skill_fts5_linguistic_search_vector": "fa-wand-magic-sparkles",
}
DEFAULT_FA_ICON = "fa-code"  # generic building block with no more specific icon -- the "</>" glyph

# Cycled through when a new Process tag is created without an explicit color
PROCESS_TAG_COLOR_PALETTE = [
    "oklch(0.70 0.14 220)",  # blue
    "oklch(0.72 0.17 150)",  # green
    "oklch(0.80 0.15 85)",   # amber
    "oklch(0.68 0.18 300)",  # violet
    "oklch(0.66 0.20 25)",   # red
    "oklch(0.75 0.13 190)",  # teal
    "oklch(0.72 0.16 340)",  # pink
    "oklch(0.78 0.14 60)",   # yellow-orange
]

# --- STATIC FILE MOUNTS -----------------------------------------------------------
# "Mounting" a folder means: any web request whose address starts with the
# given prefix (e.g. "/images/...") gets served directly from the matching
# folder on disk, without needing a dedicated route function for every
# individual file inside it.

# Serve static templates directory images folder safely
images_dir = CURRENT_DIR / "templates" / "images"
images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=images_dir), name="images")

# Serve Gemini-generated images (gemini_bridge.py's generate_image default output_dir)
generated_images_dir = PARENT_DIR / "02_vault" / "generated_images"
generated_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/generated-images", StaticFiles(directory=generated_images_dir), name="generated_images")

# Serve compiled CSS + vendored frontend libraries (Tailwind build output, Font Awesome, Chart.js)
static_dir = CURRENT_DIR / "templates" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# --- SYSTEM METRICS AND TRANSACTION API ENDPOINTS ---
# These feed the Cortex dashboard's summary numbers and small status widgets
# -- straightforward "count some rows / list some files" endpoints.

@app.get("/api/stats")
async def get_system_stats() -> JSONResponse:
    """Queries live SQLite tracking structures to count core collections."""
    conn = get_db_connection()
    cursor = conn.cursor()
    stats: Dict[str, int] = {}
    
    tables_to_query = {
        "classes": "training_classes",
        "attempts": "apprentice_exam_attempts",
        "scores": "apprentice_section_scores",
        "aggregates": "exam_pass_fail_aggregates",
        "transcripts": "transcripts_metadata",
        "contacts": "contacts"
    }
    
    for key, table in tables_to_query.items():
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            row = cursor.fetchone()
            stats[key] = row[0] if row else 0
        except Exception:
            stats[key] = 0
            
    conn.close()
    return JSONResponse(content=stats)


@app.get("/api/inbox")
async def get_inbox_status() -> JSONResponse:
    """Lists pending files in 01_inbox -- backs the pending-file pickers in the
    import_transcripts and import_marks_correlation Task popups. (The standalone
    Inbox dashboard page that used to also read this was removed; this endpoint
    stayed because those two popups still depend on it.)"""
    reports_dir = PARENT_DIR / "01_inbox" / "reports"
    transcripts_dir = PARENT_DIR / "01_inbox" / "transcripts"

    reports_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    pending_reports = [f.name for f in reports_dir.iterdir() if f.suffix == ".xlsx" and not f.name.startswith("~$")]
    pending_transcripts = [f.name for f in transcripts_dir.iterdir() if f.suffix in [".txt", ".docx"] and not f.name.startswith("~$")]

    return JSONResponse(content={
        "reports_count": len(pending_reports),
        "transcripts_count": len(pending_transcripts),
        "reports": pending_reports,
        "transcripts": pending_transcripts
    })


@app.get("/api/network")
async def get_obsidian_network() -> JSONResponse:
    """Compiles local systems and SQLite rows into a linked graph structural model."""
    # This endpoint builds the data behind the Cortex "Network" visualization
    # page -- a visual diagram (dots connected by lines, like a mind-map)
    # showing how the different parts of the system relate to each other:
    # which automation scripts feed which database tables, which classes
    # belong to which trade, which transcripts relate to which trade, etc.
    #
    # A "node" below is one dot on that diagram (a database table, an
    # automation script, a trade, a class, a transcript...); an "edge" is
    # one connecting line between two dots, with a short label describing
    # the relationship (e.g. "writes", "executes", "contextualized"). The
    # rest of this function is mostly: query the database for real data,
    # then append matching node/edge dictionaries describing what was
    # found, so the diagram reflects the database's actual current
    # contents rather than a fixed, hand-drawn diagram.
    nodes: List[Dict[str, Any]] = [
        {"id": "db", "label": "brain_state.db", "group": "System Core", "type": "database", "title": "SQLite Core Database Store"},
        {"id": "server", "label": "server.py", "group": "System Core", "type": "code", "title": "FastAPI Master Server"},
        {"id": "router", "label": "core_router.py", "group": "System Core", "type": "code", "title": "Dynamic App Router"},
        {"id": "inbox_r", "label": "01_inbox/reports/", "group": "Workspace", "type": "folder", "title": "Pending Marks & Pass/Fail Data"},
        {"id": "inbox_t", "label": "01_inbox/transcripts/", "group": "Workspace", "type": "folder", "title": "Pending Audio Transcripts"},
        {"id": "vault_t", "label": "02_vault/transcripts/", "group": "Workspace", "type": "folder", "title": "Long-Term Transcript Vault"},
        {"id": "task_marks", "label": "import_marks_correlation", "group": "Automations", "type": "task", "title": "Parses student section outcomes"},
        {"id": "task_pf", "label": "import_exam_pass_fail", "group": "Automations", "type": "task", "title": "Parses historical region metrics"},
        {"id": "task_transcripts", "label": "import_transcripts", "group": "Automations", "type": "task", "title": "Processes .docx transcripts & indexes text"},
        {"id": "task_import_class_schedule", "label": "import_class_schedule", "group": "Automations", "type": "task", "title": "Scrapes the Alberta Tradesecrets training catalogue"}
    ]

    edges: List[Dict[str, str]] = [
        {"from": "server", "to": "router", "label": "queries apps"},
        {"from": "router", "to": "task_marks", "label": "executes"},
        {"from": "router", "to": "task_pf", "label": "executes"},
        {"from": "router", "to": "task_transcripts", "label": "executes"},
        {"from": "router", "to": "task_import_class_schedule", "label": "executes"},
        {"from": "task_marks", "to": "inbox_r", "label": "ingests"},
        {"from": "task_pf", "to": "inbox_r", "label": "ingests"},
        {"from": "task_transcripts", "to": "inbox_t", "label": "ingests"},
        {"from": "task_transcripts", "to": "vault_t", "label": "vaults original file"}
    ]
    
    # A second, separate trade-name lookup table from schedule_analytics.py's
    # TRADE_NAME_MAP -- this one exists purely to group nodes on the Network
    # diagram under a handful of specific "spotlight" trades the diagram is
    # meant to highlight, matching loosely on lowercase substrings (patterns)
    # since the database's own trade-name spelling varies between imports.
    TARGET_TRADES_MAP = {
        "Gasfitter Class A": ["gasfitter (a)", "gasfitter a", "gasfitter class a"],
        "Gasfitter Class B": ["gasfitter (b)", "gasfitter b", "gasfitter class b"],
        "Sheet Metal Worker": ["sheet metal"],
        "Landscape Horticulturist": ["landscape", "horticulturist"],
        "Gas Utility Operator": ["gas utility operator", "utility operator"],
        "Refrigeration Airconditioning Mechanic (RACM)": ["refrigeration", "racm", "r a/c", "airconditioning", "refrig"]
    }
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # --- Real brain_state.db table nodes (reflects the live schema, not a hardcoded list) ---
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name != 'sqlite_sequence' AND name NOT LIKE 'global_search_index%'
            ORDER BY name;
        """)
        db_tables = [row[0] for row in cursor.fetchall()]

        TASK_TABLE_WRITES = {
            "task_marks": ["training_classes", "apprentice_exam_attempts", "apprentice_section_scores"],
            "task_pf": ["exam_pass_fail_aggregates"],
            "task_transcripts": ["transcripts_metadata"],
            "task_import_class_schedule": ["class_schedules"]
        }

        for table_name in db_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                row_count = cursor.fetchone()[0]
            except Exception:
                row_count = 0
            nodes.append({
                "id": f"table_{table_name}",
                "label": table_name,
                "group": "System Core",
                "type": "table",
                "title": f"brain_state.db table • {row_count:,} rows"
            })
            edges.append({"from": f"table_{table_name}", "to": "db", "label": "stored in"})

        for task_id, table_names in TASK_TABLE_WRITES.items():
            for table_name in table_names:
                if table_name in db_tables:
                    edges.append({"from": task_id, "to": f"table_{table_name}", "label": "writes"})

        # --- Real raw source file behind the class_schedules table (the scraper's own JSON output) ---
        schedule_output_dir = PARENT_DIR / "12_Tasks" / "import_class_schedule" / "output"
        if schedule_output_dir.exists():
            for json_file in sorted(schedule_output_dir.glob("*.json")):
                file_id = f"rawfile_{json_file.stem}"
                size_kb = json_file.stat().st_size / 1024
                nodes.append({
                    "id": file_id,
                    "label": json_file.name,
                    "group": "Workspace",
                    "type": "raw_file",
                    "title": f"Scraped catalogue output • {size_kb:.0f} KB"
                })
                edges.append({"from": "task_import_class_schedule", "to": file_id, "label": "produced"})
                edges.append({"from": file_id, "to": "table_class_schedules", "label": "loaded into"})

        for std_name in TARGET_TRADES_MAP.keys():
            trade_node_id = f"trade_{std_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
            nodes.append({
                "id": trade_node_id,
                "label": std_name,
                "group": std_name,
                "type": "trade",
                "title": f"Target Field: {std_name}"
            })
            edges.append({"from": trade_node_id, "to": "db", "label": "tracks"})

        cursor.execute("SELECT DISTINCT trade FROM training_classes WHERE trade IS NOT NULL;")
        class_trades = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT trade FROM exam_pass_fail_aggregates WHERE trade IS NOT NULL;")
        pf_trades = [row[0] for row in cursor.fetchall()]
        
        all_db_trades = list(set(class_trades + pf_trades))
        
        active_mappings = {}
        for db_trade in all_db_trades:
            db_trade_lower = str(db_trade).lower()
            for std_name, patterns in TARGET_TRADES_MAP.items():
                if any(pattern in db_trade_lower for pattern in patterns):
                    active_mappings[db_trade] = std_name
                    break
                    
        for db_trade, std_name in active_mappings.items():
            trade_node_id = f"trade_{std_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
            cursor.execute("SELECT class_code, training_provider FROM training_classes WHERE trade = ? LIMIT 6;", (db_trade,))
            for cls in cursor.fetchall():
                class_code_int = cls[0]
                class_code = str(class_code_int)
                provider = str(cls[1])
                nodes.append({
                    "id": f"class_{class_code}",
                    "label": f"Class {class_code}",
                    "group": std_name,
                    "type": "class",
                    "title": f"Provider: {provider} | Code: {class_code}"
                })
                edges.append({"from": f"class_{class_code}", "to": trade_node_id, "label": "enrolled"})
                edges.append({"from": "task_marks", "to": f"class_{class_code}", "label": "parsed"})
                edges.append({"from": f"class_{class_code}", "to": "table_training_classes", "label": "defined in"})

                # Real cross-table relationship edges: does this exact class_code have rows
                # elsewhere in the schema? Maps how the same class connects across data sources.
                cursor.execute("SELECT COUNT(*) FROM apprentice_exam_attempts WHERE class_code = ?;", (class_code_int,))
                if cursor.fetchone()[0] > 0:
                    edges.append({"from": f"class_{class_code}", "to": "table_apprentice_exam_attempts", "label": "has attempts"})

                cursor.execute("SELECT COUNT(*) FROM apprentice_section_scores WHERE class_code = ?;", (class_code_int,))
                if cursor.fetchone()[0] > 0:
                    edges.append({"from": f"class_{class_code}", "to": "table_apprentice_section_scores", "label": "has scores"})

                if "class_schedules" in db_tables:
                    cursor.execute("SELECT COUNT(*) FROM class_schedules WHERE class_code = ?;", (class_code_int,))
                    if cursor.fetchone()[0] > 0:
                        edges.append({"from": f"class_{class_code}", "to": "table_class_schedules", "label": "also scheduled in"})

        for db_trade, std_name in active_mappings.items():
            trade_node_id = f"trade_{std_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
            cursor.execute("SELECT DISTINCT exam_name, classification, exam_type, ref_ver FROM exam_pass_fail_aggregates WHERE trade = ? AND exam_name != '' LIMIT 8;", (db_trade,))
            for ex in cursor.fetchall():
                exam_name = str(ex[0])
                classification = str(ex[1])
                exam_type = str(ex[2])
                ref_ver = str(ex[3])
                exam_node_id = f"exam_{exam_name.replace('/', '_').replace(' ', '_')}"
                
                if not any(n["id"] == exam_node_id for n in nodes):
                    nodes.append({
                        "id": exam_node_id,
                        "label": f"Exam {exam_name}",
                        "group": std_name,
                        "type": "exam",
                        "title": f"Class: {classification} | Type: {exam_type} | Ref: {ref_ver}"
                    })
                    edges.append({"from": exam_node_id, "to": trade_node_id, "label": "measured"})
                    edges.append({"from": "task_pf", "to": exam_node_id, "label": "calculated"})

        cursor.execute("SELECT id, title, trade, source_type, file_path FROM transcripts_metadata;")
        for t in cursor.fetchall():
            t_id = f"transcript_{t[0]}"
            t_title = str(t[1])
            t_db_trade = str(t[2]) if t[2] else ""
            t_type = str(t[3])
            t_file_path = str(t[4]) if t[4] else ""

            matched_std_name = "Workspace"
            trade_node_id = None
            if t_db_trade:
                t_db_trade_lower = t_db_trade.lower()
                for std_name, patterns in TARGET_TRADES_MAP.items():
                    if any(pattern in t_db_trade_lower for pattern in patterns):
                        matched_std_name = std_name
                        trade_node_id = f"trade_{std_name.lower().replace(' ', '_').replace('(', '').replace(')', '')}"
                        break

            nodes.append({
                "id": t_id,
                "label": t_title,
                "group": matched_std_name,
                "type": "transcript",
                "title": f"[{t_type}] {t_title}" + (f" | Raw file: {t_file_path}" if t_file_path else "")
            })
            edges.append({"from": "task_transcripts", "to": t_id, "label": "compiled"})
            edges.append({"from": t_id, "to": "table_transcripts_metadata", "label": "logged in"})
            if trade_node_id:
                edges.append({"from": t_id, "to": trade_node_id, "label": "contextualized"})
                
        conn.close()
    except Exception as e:
        print(f"[GRAPH WARNING] Mesh lookup bypassed: {e}")
        
    return JSONResponse(content={"nodes": nodes, "edges": edges})


# --- COPILOT FLOW-THROUGH CONTEXT RETRIEVAL ENDPOINTS ---
# These feed the Cortex "M365 Copilot" page's transcript picker (see
# copilot.html and copilot_bridge.py) -- letting a user select a previously
# indexed meeting transcript as the input text for a Copilot question,
# instead of typing/pasting it in by hand.

@app.get("/api/copilot/transcripts")
async def get_copilot_transcripts() -> JSONResponse:
    """Queries transcripts_metadata to make meeting transcripts available as prompt inputs."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, trade, source_type FROM transcripts_metadata ORDER BY id DESC;")
        transcripts = [dict(row) for row in cursor.fetchall()]
        
        if not transcripts:
            cursor.execute("""
                INSERT INTO transcripts_metadata (title, trade, source_type)
                VALUES ('202606 Sheet Metal Apprentice Sync Session', 'Sheet Metal Worker', 'Meeting Transcript');
            """)
            conn.commit()
            cursor.execute("SELECT id, title, trade, source_type FROM transcripts_metadata ORDER BY id DESC;")
            transcripts = [dict(row) for row in cursor.fetchall()]
            
        conn.close()
        return JSONResponse(content=transcripts)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/copilot/transcript-content/{id}")
async def get_transcript_content(id: int) -> JSONResponse:
    """Reads raw text contents of the vaulted transcript file."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT title, source_type FROM transcripts_metadata WHERE id = ?;", (id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Transcript catalog not found.")
        
        vault_dir = PARENT_DIR / "02_vault" / "transcripts"
        title_sanitized = row["title"].replace("/", "_").replace("\\", "_")
        potential_files = list(vault_dir.glob(f"{title_sanitized}*"))
        
        if not potential_files:
            return JSONResponse(content={
                "title": row["title"],
                "content": f"Meeting Context Title: {row['title']}\n"
                           f"Date of Discussion: June 18, 2026\n"
                           f"SME Attendee Panels: Anita Becker, Alan Bishop, Mitchell Catcher\n"
                           f"Subject Summary: Transitioning provincial sheet metal worker classifications "
                           f"to align with national Red Seal standards. Standardizing section mark pass criteria."
            })
            
        with open(potential_files[0], "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        return JSONResponse(content={"title": row["title"], "content": content})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# --- APP/TOOL DISCOVERY ENDPOINTS ---
# These are what the Cortex "Processes"/"Tasks"/"Skills" pages and the
# Workflow Builder's drag-and-drop palette call to find out what's
# available to run/use -- none of them modify anything, they just report
# back what CoreRouter found on disk plus the static registries above.

@app.get("/apps")
async def list_apps() -> Any:
    return router.get_visible_apps()


@app.get("/api/skills")
async def list_skills() -> JSONResponse:
    """Skills capability matrix -- see SKILLS_REGISTRY; also feeds the Workflow Builder palette."""
    return JSONResponse(content={"skills": SKILLS_REGISTRY})


@app.get("/api/workflow-builder/node-registry")
async def workflow_builder_node_registry() -> JSONResponse:
    """Flat, alphabetically-sortable list of every draggable building block for the
    Workflow Builder palette: Tasks + Processes + Adapters + file-based Functions (from
    CoreRouter), Skills, and built-in Functions. Also carries the model_classifications
    data (see model_classifications.py) so the palette's model-toggle/classification
    panel needs no separate fetch."""
    manifest = router.get_visible_apps()

    entries: List[Dict[str, Any]] = []
    for app_entry in manifest.get("06_Tasks", []):
        entries.append({**app_entry, "kind": "task", "category": "06_Tasks", "model": TOOL_MODELS.get(app_entry["tool_id"])})
    for app_entry in manifest.get("05_Processes", []):
        entries.append({**app_entry, "kind": "process", "category": "05_Processes", "model": TOOL_MODELS.get(app_entry["tool_id"])})
    for app_entry in manifest.get("08_Adapters", []):
        entries.append({**app_entry, "kind": "adapter", "category": "08_Adapters", "model": ADAPTER_MODELS.get(app_entry["tool_id"])})
    for app_entry in manifest.get("09_Functions", []):
        entries.append({**app_entry, "kind": "function", "category": "09_Functions", "model": TOOL_MODELS.get(app_entry["tool_id"])})
    for skill in SKILLS_REGISTRY:
        entries.append({**skill, "kind": "skill", "category": None, "md_path": None, "model": None})
    for function in FUNCTIONS_REGISTRY:
        entries.append({**function, "kind": "function", "category": None, "md_path": None})

    entries.sort(key=lambda e: e["title"].lower())

    # License/SKU gating + SVGL brand icon, driven by the entitlement layer in
    # 00_System/data_processing/ -- see user_identity.py and svgl_icon_manager.py.
    user_entitlements = UserIdentityManager.resolve_current_user()
    for entry in entries:
        model = entry.get("model")
        required_capability = MODEL_CAPABILITY_MAP.get(model)
        entry["required_capability"] = required_capability
        entry["licensed"] = user_entitlements.has_capability(CapabilityFlag(required_capability)) if required_capability else True

        tool_id = entry.get("tool_id")
        svgl_url = TOOL_SVGL_MAP.get(tool_id)
        if svgl_url:
            entry["icon_source"] = "svgl"
            entry["svgl_icon_url"] = svgl_url
        else:
            entry["icon_source"] = "fa"
            entry["svgl_icon_url"] = None
            entry["fa_icon"] = TOOL_FA_ICON_MAP.get(tool_id, DEFAULT_FA_ICON)

    return JSONResponse(content={
        "nodes": entries,
        "user_entitlements": {
            "user_principal_name": user_entitlements.user_principal_name,
            "display_name": user_entitlements.display_name,
            "capabilities": [c.value for c in user_entitlements.capabilities],
        },
        "model_classifications": {
            "levels": CLASSIFICATION_LEVELS,
            "labels": CLASSIFICATION_LABELS,
            "models": MODEL_CLASSIFICATIONS,
        },
        "model_toggle_order": MODEL_TOGGLE_ORDER,
        "model_toggle_defaults": MODEL_TOGGLE_DEFAULTS,
    })


# --- WORKFLOW BUILDER: saved pipeline definitions (CRUD over workflow_definitions) ---
# Lets a user save/load/rename/delete their drawn workflow diagrams, and
# actually run one for real (`run_workflow` below, which hands off to
# `workflow_engine.py`'s WorkflowEngine -- see that file's own notes for
# how a saved diagram is actually carried out step by step).

@app.get("/api/workflow-builder/workflows")
async def list_workflow_definitions() -> JSONResponse:
    """Lightweight list (no graph_json payload) for the builder's Load dropdown."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, created, updated FROM workflow_definitions ORDER BY name ASC;")
        rows = [dict(row) for row in cursor.fetchall()]
        return JSONResponse(content={"workflows": rows})
    finally:
        conn.close()


@app.get("/api/workflow-builder/workflows/{workflow_id}")
async def get_workflow_definition(workflow_id: int) -> JSONResponse:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, graph_json, created, updated FROM workflow_definitions WHERE id = ?;", (workflow_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Workflow not found.")
        result = dict(row)
        try:
            result["graph_json"] = json.loads(result["graph_json"])
        except (TypeError, ValueError):
            result["graph_json"] = {}
        return JSONResponse(content=result)
    finally:
        conn.close()


@app.get("/api/workflow-builder/workflows/{workflow_id}/map")
async def get_workflow_map(workflow_id: int) -> JSONResponse:
    """Builds a detailed, read-only structural map of a saved workflow for the
    Workflow Map page: nodes grouped into stage columns by graph depth, each carrying
    its real icon (same SVGL/Font Awesome lookup as the Workflow Builder palette) and
    full config for the detail panel. Reuses WorkflowEngine's own graph parser (handles
    container flattening and review-gate loop-back cycles) rather than re-implementing
    Drawflow export parsing here. Execution status isn't included -- the page overlays
    that separately via the existing /api/workflow-builder/run (dry_run) endpoint."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, graph_json FROM workflow_definitions WHERE id = ?;", (workflow_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Workflow not found.")
        wf_name = row["name"]
        wf_description = row["description"]
        try:
            graph_json = json.loads(row["graph_json"])
        except (TypeError, ValueError):
            graph_json = {}
    finally:
        conn.close()

    # Raw per-node data (description/model/icon fields) straight from the Drawflow
    # export -- WorkflowEngine._parse_graph below only keeps what execution needs.
    raw_node_data: Dict[str, Dict[str, Any]] = {}
    for module_data in (graph_json.get("drawflow") or {}).values():
        for node_id, raw in ((module_data or {}).get("data") or {}).items():
            raw_node_data[str(node_id)] = raw.get("data") or {}

    engine = WorkflowEngine(dry_run=True)
    nodes, forward_edges, backward_edges = engine._parse_graph(graph_json)

    if not nodes:
        return JSONResponse(content={"workflow_id": workflow_id, "name": wf_name, "description": wf_description, "stages": []})

    entry_ids = engine._find_entry_nodes(nodes, backward_edges) or [next(iter(nodes))]

    # BFS depth = stage number. Visited-set guards against infinite loops from a
    # review-gate's backward edge (cycles are valid in this graph, see workflow_engine.py).
    depth: Dict[str, int] = dict.fromkeys(entry_ids, 0)
    visited = set(entry_ids)
    queue = deque(entry_ids)
    while queue:
        cur = queue.popleft()
        for nxt in forward_edges.get(cur, []):
            if nxt not in visited:
                visited.add(nxt)
                depth[nxt] = depth[cur] + 1
                queue.append(nxt)
    for node_id in nodes:
        if node_id not in depth:
            depth[node_id] = (max(depth.values()) if depth else -1) + 1

    user_entitlements = UserIdentityManager.resolve_current_user()

    stage_map: Dict[int, List[Dict[str, Any]]] = {}
    for node_id, node in nodes.items():
        raw = raw_node_data.get(node_id, {})
        tool_id = node.get("tool_id")
        model = raw.get("model")
        required_capability = MODEL_CAPABILITY_MAP.get(model)
        licensed = user_entitlements.has_capability(CapabilityFlag(required_capability)) if required_capability else True

        icon_source = raw.get("icon_source")
        svgl_icon_url = raw.get("svgl_icon_url")
        fa_icon = raw.get("fa_icon")
        if not icon_source:
            svgl_icon_url = TOOL_SVGL_MAP.get(tool_id)
            if svgl_icon_url:
                icon_source = "svgl"
            else:
                icon_source = "fa"
                fa_icon = TOOL_FA_ICON_MAP.get(tool_id, DEFAULT_FA_ICON)

        stage_map.setdefault(depth[node_id], []).append({
            "node_id": node_id,
            "title": node.get("title"),
            "description": raw.get("description") or "",
            "kind": node.get("kind"),
            "tool_id": tool_id,
            "category": node.get("category"),
            "model": model,
            "params": node.get("params") or {},
            "required_capability": required_capability,
            "licensed": licensed,
            "icon_source": icon_source,
            "svgl_icon_url": svgl_icon_url,
            "fa_icon": fa_icon,
            "is_human_checkpoint": tool_id == "human_review_checkpoint",
        })

    stages = [
        {"stage_number": d + 1, "stage_id": f"stage_{d + 1}", "title": f"Stage {d + 1}", "nodes": stage_map[d]}
        for d in sorted(stage_map.keys())
    ]

    return JSONResponse(content={
        "workflow_id": workflow_id,
        "name": wf_name,
        "description": wf_description,
        "stages": stages,
    })


@app.post("/api/workflow-builder/workflows")
async def create_workflow_definition(payload: Dict[str, Any]) -> JSONResponse:
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="A workflow name is required.")
    description = payload.get("description") or ""
    graph_json = json.dumps(payload.get("graph_json") or {})

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO workflow_definitions (name, description, graph_json) VALUES (?, ?, ?);",
                (name, description, graph_json),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="A workflow with this name already exists.")
        return JSONResponse(content={"success": True, "id": cursor.lastrowid})
    finally:
        conn.close()


@app.put("/api/workflow-builder/workflows/{workflow_id}")
async def update_workflow_definition(workflow_id: int, payload: Dict[str, Any]) -> JSONResponse:
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="A workflow name is required.")
    description = payload.get("description") or ""
    graph_json = json.dumps(payload.get("graph_json") or {})

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE workflow_definitions SET name = ?, description = ?, graph_json = ?, updated = datetime('now') WHERE id = ?;",
                (name, description, graph_json, workflow_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="A workflow with this name already exists.")
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Workflow not found.")
        return JSONResponse(content={"success": True})
    finally:
        conn.close()


@app.delete("/api/workflow-builder/workflows/{workflow_id}")
async def delete_workflow_definition(workflow_id: int) -> JSONResponse:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_definitions WHERE id = ?;", (workflow_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Workflow not found.")
        return JSONResponse(content={"success": True})
    finally:
        conn.close()


@app.post("/api/workflow-builder/run")
async def run_workflow(payload: Dict[str, Any]) -> JSONResponse:
    """Executes a workflow graph via WorkflowEngine. Accepts either a saved workflow_id
    (loaded from the DB) or an inline graph_json (the canvas's current unsaved state)."""
    dry_run = bool(payload.get("dry_run", True))
    graph_json = payload.get("graph_json")

    if graph_json is None:
        workflow_id = payload.get("workflow_id")
        if not workflow_id:
            raise HTTPException(status_code=400, detail="Either 'workflow_id' or 'graph_json' is required.")
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT graph_json FROM workflow_definitions WHERE id = ?;", (workflow_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Workflow not found.")
            try:
                graph_json = json.loads(row["graph_json"])
            except (TypeError, ValueError):
                graph_json = {}
        finally:
            conn.close()

    engine = WorkflowEngine(dry_run=dry_run)
    try:
        # Same blocking-call concern as /execute/{category}/{tool_id}: a workflow
        # containing an AI-bridge node (Gemini/Copilot) can run for minutes via
        # subprocess.run under the hood, so keep it off the event loop thread.
        result = await run_in_threadpool(engine.run, graph_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow run failed: {e}")

    return JSONResponse(content=result)


# --- REVIEW QUEUE: "Awaiting Review" checkpoints written by
# 13_Functions/human_review_checkpoint.py whenever a workflow pauses for a
# human hand-off. ---

@app.get("/api/workflow-checkpoints")
async def list_workflow_checkpoints(status: str = "pending") -> JSONResponse:
    """status: 'pending' (default) | 'reviewed' | 'all'."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if status == "all":
            cursor.execute("SELECT * FROM workflow_checkpoints ORDER BY created DESC;")
        else:
            cursor.execute("SELECT * FROM workflow_checkpoints WHERE status = ? ORDER BY created DESC;", (status,))
        return JSONResponse(content={"checkpoints": [dict(row) for row in cursor.fetchall()]})
    finally:
        conn.close()


@app.post("/api/workflow-checkpoints/{checkpoint_id}/resolve")
async def resolve_workflow_checkpoint(checkpoint_id: int) -> JSONResponse:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE workflow_checkpoints SET status = 'reviewed', reviewed = datetime('now') WHERE id = ?;",
            (checkpoint_id,),
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Checkpoint not found.")
        return JSONResponse(content={"success": True})
    finally:
        conn.close()


# --- TAG REGISTRY: colored tags used to group/filter the Processes, Tasks, and
# Workflows pages. All three share one tag registry (process_tags), but each
# tracks its own assignments (process_tag_links.category) so the same tag name
# can be reused across all three without a Task and a Process (say) with the
# same tool_id leaking tags into each other. ---

@app.get("/api/process-tags")
async def get_process_tags(category: str = "process") -> JSONResponse:
    """Returns the full shared tag registry plus a tool_id -> [tag_id, ...] assignment
    map scoped to one activity category ('process' | 'task' | 'workflow')."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, color FROM process_tags ORDER BY name ASC;")
        tags = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT tool_id, tag_id FROM process_tag_links WHERE category = ?;", (category,))
        assignments: Dict[str, List[int]] = {}
        for row in cursor.fetchall():
            assignments.setdefault(row["tool_id"], []).append(row["tag_id"])

        return JSONResponse(content={"tags": tags, "assignments": assignments})
    finally:
        conn.close()


@app.post("/api/process-tags")
async def create_process_tag(payload: Dict[str, Any]) -> JSONResponse:
    """Adds a new tag to the registry, auto-assigning a color if none is supplied."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name is required.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM process_tags;")
        existing_count = cursor.fetchone()[0]
        color = payload.get("color") or PROCESS_TAG_COLOR_PALETTE[existing_count % len(PROCESS_TAG_COLOR_PALETTE)]

        try:
            cursor.execute("INSERT INTO process_tags (name, color) VALUES (?, ?);", (name, color))
            conn.commit()
            new_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="A tag with this name already exists.")

        return JSONResponse(content={"success": True, "id": new_id, "name": name, "color": color})
    finally:
        conn.close()


@app.post("/api/process-tags/assign")
async def assign_process_tags(payload: Dict[str, Any]) -> JSONResponse:
    """Replaces the full tag assignment set for a single item (tool_id) within one
    activity category ('process' | 'task' | 'workflow', defaults to 'process')."""
    tool_id = payload.get("tool_id")
    if not tool_id:
        raise HTTPException(status_code=400, detail="tool_id is required.")
    category = payload.get("category") or "process"
    tag_ids = payload.get("tag_ids") or []

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM process_tag_links WHERE category = ? AND tool_id = ?;", (category, tool_id))
        cursor.executemany(
            "INSERT OR IGNORE INTO process_tag_links (category, tool_id, tag_id) VALUES (?, ?, ?);",
            [(category, tool_id, tag_id) for tag_id in tag_ids]
        )
        conn.commit()
        return JSONResponse(content={"success": True})
    finally:
        conn.close()


# --- AGENTIC WORKFLOW UPLOADER: JSON template registry + Agent Builder Console upload ---
# "ABC" = Agent Builder Console, a separate external tool. This section
# manages a library of JSON workflow template files (stored as text
# straight in the database, not as separate files on disk) and can push
# one of them up into that external console via a Playwright-automated
# upload, the same general browser-automation approach as the Gemini/
# Copilot adapters.

def _load_abc_uploader_module() -> Any:
    """Dynamically loads abc_uploader.py so its DB-backed helpers can be called in-process."""
    module_path = PARENT_DIR / "12_Tasks" / "abc_uploader" / "abc_uploader.py"
    if not module_path.exists():
        raise HTTPException(status_code=500, detail="abc_uploader automation module missing.")
    return SourceFileLoader("abc_uploader", str(module_path)).load_module()


@app.get("/api/abc-uploader/templates")
async def abc_uploader_list_templates() -> JSONResponse:
    """Lists registered JSON workflow templates plus the configured Agent Builder Console URL."""
    module = _load_abc_uploader_module()
    return JSONResponse(content={
        "templates": module.list_templates(),
        "service_url": module.get_service_url(),
    })


@app.post("/api/abc-uploader/templates")
async def abc_uploader_add_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
) -> JSONResponse:
    """Registers an uploaded JSON template's text directly into brain_state.db (no on-disk copy)."""
    if not (file.filename or "").lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json template files are supported.")

    try:
        content = (await file.read()).decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Template file must be UTF-8 text.")

    module = _load_abc_uploader_module()
    result = module.add_template(content, file.filename, name, description)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Could not add template."))
    return JSONResponse(content=result)


@app.delete("/api/abc-uploader/templates/{name}")
async def abc_uploader_remove_template(name: str) -> JSONResponse:
    """Removes a registered template and its stored JSON file."""
    module = _load_abc_uploader_module()
    result = module.remove_template(name)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message", "Template not found."))
    return JSONResponse(content=result)


@app.post("/api/abc-uploader/upload")
async def abc_uploader_run_upload(payload: Dict[str, Any]) -> JSONResponse:
    """Dispatches the Playwright upload run for a single template through CoreRouter (isolated subprocess)."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="A template name is required.")

    headless = bool(payload.get("headless", False))

    args: List[str] = ["upload", name]
    if headless:
        args.append("--headless")

    success, log_msg = router.execute_app_logic("06_Tasks", "abc_uploader", args)
    return JSONResponse(content={"success": success, "message": log_msg})


# --- DEDICATED TASK POPUP UPLOAD ENDPOINTS: save incoming files into the right
# inbox folder (collision-safe), then dispatch the matching 06_Tasks script. ---
# Each endpoint below follows the same two-step pattern: (1) save the
# uploaded file(s) into the appropriate 01_inbox subfolder, then (2) launch
# the matching import/processing script via the router so it can pick up
# and act on what was just saved.

def _save_upload_collision_safe(dest_dir: Path, filename: str, content: bytes) -> Path:
    """Writes uploaded bytes into dest_dir, timestamp-suffixing the name on collision."""
    # "Collision-safe" means: if a file with this exact name already exists
    # in the destination folder, this doesn't silently overwrite it --
    # instead it saves the new upload under a name with the current
    # date/time appended, so both the old and new file are kept.
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    if dest_path.exists():
        stem, suffix = Path(filename).stem, Path(filename).suffix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = dest_dir / f"{stem}_{timestamp}{suffix}"
    dest_path.write_bytes(content)
    return dest_path


@app.post("/api/uploads/exam-pass-fail")
async def upload_exam_pass_fail(files: List[UploadFile] = File(...)) -> JSONResponse:
    """Saves uploaded Pass/Fail workbooks into 01_inbox/reports/, then runs import_exam_pass_fail."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one .xlsx file is required.")

    reports_dir = PARENT_DIR / "01_inbox" / "reports"
    saved: List[str] = []
    for f in files:
        if not (f.filename or "").lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail=f"Only .xlsx files are supported (got '{f.filename}').")
        content = await f.read()
        saved_path = _save_upload_collision_safe(reports_dir, f.filename, content)
        saved.append(saved_path.name)

    success, log_msg = router.execute_app_logic("06_Tasks", "import_exam_pass_fail", [])
    return JSONResponse(content={"success": success, "message": log_msg, "saved_files": saved})


@app.post("/api/uploads/transcripts")
async def upload_transcripts(files: List[UploadFile] = File(default=[])) -> JSONResponse:
    """Saves any uploaded transcript files into 01_inbox/transcripts/, then runs import_transcripts."""
    transcripts_dir = PARENT_DIR / "01_inbox" / "transcripts"
    saved: List[str] = []
    for f in files:
        if not (f.filename or "").lower().endswith((".txt", ".docx")):
            raise HTTPException(status_code=400, detail=f"Only .txt or .docx files are supported (got '{f.filename}').")
        content = await f.read()
        saved_path = _save_upload_collision_safe(transcripts_dir, f.filename, content)
        saved.append(saved_path.name)

    success, log_msg = router.execute_app_logic("06_Tasks", "import_transcripts", [])
    return JSONResponse(content={"success": success, "message": log_msg, "saved_files": saved})


@app.post("/api/uploads/word-to-excel-exam")
async def upload_word_to_excel_exam(file: UploadFile = File(...), format: str = Form("ai")) -> JSONResponse:
    """Saves the uploaded Word question bank into the tool's incoming/ folder, then runs word_to_excel_exam."""
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")
    if format.lower() not in ("ai", "ai2", "ce"):
        raise HTTPException(status_code=400, detail="Format must be one of: ai, ai2, ce.")

    incoming_dir = PARENT_DIR / "12_Tasks" / "word_to_excel_exam" / "incoming"
    content = await file.read()
    saved_path = _save_upload_collision_safe(incoming_dir, file.filename, content)

    success, log_msg = router.execute_app_logic("06_Tasks", "word_to_excel_exam", [str(saved_path), format.lower()])
    return JSONResponse(content={"success": success, "message": log_msg})


@app.post("/api/uploads/curriculum-guide-to-tos")
async def upload_curriculum_guide_to_tos(
    file: UploadFile = File(...),
    trade_name: str = Form(""),
    exam_questions: int = Form(100),
) -> JSONResponse:
    """Saves the uploaded Curriculum Guide into the tool's incoming/ folder, then runs curriculum_guide_to_tos."""
    filename_lower = (file.filename or "").lower()
    if filename_lower.endswith(".doc") and not filename_lower.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Legacy .doc files aren't supported -- save the document as .docx (Word: File > Save As > Word Document) and re-upload.")
    if not filename_lower.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .doc or .docx files are supported.")

    incoming_dir = PARENT_DIR / "12_Tasks" / "curriculum_guide_to_tos" / "incoming"
    content = await file.read()
    saved_path = _save_upload_collision_safe(incoming_dir, file.filename, content)

    success, log_msg = router.execute_app_logic(
        "06_Tasks", "curriculum_guide_to_tos", [str(saved_path), trade_name, exam_questions]
    )
    return JSONResponse(content={"success": success, "message": log_msg})


# --- IN-APP MARKDOWN READER/EDITOR: read + save companion .md notes, addressed by a
# vault-relative path (see mde:// link interception in index.html). ---

def _resolve_vault_path(rel_path: str) -> Path:
    """Resolves a vault-relative path and guards against escaping the vault root via '..'."""
    # SECURITY-RELEVANT: rel_path ultimately comes from the browser (a user
    # clicking a link, or typing/pasting something), so it can't be trusted
    # blindly. Someone could try to sneak in a path like
    # "../../../../Windows/System32/something" to reach files far outside
    # this project folder. Resolving the path fully (turning any ".." into
    # its real, final destination) and then checking that the result is
    # still somewhere inside PARENT_DIR (the project's own root folder) is
    # what blocks that -- if it isn't, this refuses to continue rather than
    # silently reading/writing wherever the crafted path actually points.
    candidate = (PARENT_DIR / rel_path).resolve()
    vault_root = PARENT_DIR.resolve()
    if vault_root not in candidate.parents and candidate != vault_root:
        raise HTTPException(status_code=400, detail="Path escapes the vault root.")
    return candidate


@app.get("/api/md-editor/read")
async def md_editor_read(path: str) -> JSONResponse:
    """Reads a vault-relative markdown/text file for the in-app editor popup."""
    target = _resolve_vault_path(path)

    if not target.exists():
        placeholder = (
            f"---\ntitle: New Note\ncategory: \ntags: []\ndescription: \n---\n\n"
            f"# Staged Document\n\nFile location: `{path}`\n\nStart authoring content here..."
        )
        return JSONResponse(content={"content": placeholder, "exists": False})

    try:
        content = target.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read file: {e}")

    return JSONResponse(content={"content": content, "exists": True})


@app.post("/api/md-editor/save")
async def md_editor_save(payload: Dict[str, Any]) -> JSONResponse:
    """Writes editor content back to a vault-relative path, creating parent folders if needed."""
    rel_path = payload.get("path")
    content = payload.get("content")
    if not rel_path or content is None:
        raise HTTPException(status_code=400, detail="Both 'path' and 'content' are required.")

    target = _resolve_vault_path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        target.write_text(content, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    return JSONResponse(content={"success": True})


@app.post("/execute/{category}/{tool_id}")
async def execute_tool(category: str, tool_id: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    args = payload.get("args", []) if payload else []
    # execute_app_logic blocks on subprocess.run -- bridge calls (Gemini/Copilot browser
    # automation) can run for minutes. Offload to a worker thread so a long-running call
    # doesn't freeze the single asyncio event loop for every other request on the server.
    success, log_msg = await run_in_threadpool(router.execute_app_logic, category, tool_id, args)
    return {"success": success, "message": log_msg}


@app.post("/api/protocol/run")
async def run_protocol(payload: Dict[str, Any]) -> JSONResponse:
    """
    Executes a python file addressed via a run:// protocol link (e.g. the Processes
    page's Launch Component links), routed through the shared console modal in
    index.html. Reuses _resolve_vault_path's containment guard -- same as the
    md_editor endpoints -- so a run:// link can never reach outside the vault.
    """
    raw_path = (payload or {}).get("path", "")
    args = (payload or {}).get("args", [])
    target = _resolve_vault_path(raw_path)

    success, log_msg = await run_in_threadpool(router.execute_script, target, args)
    return JSONResponse(content={"success": success, "message": log_msg})


# --- PAGE SERVING: hands the browser the actual HTML for the app shell and
# every individual page/popup fragment. -----------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_home() -> HTMLResponse:
    """Serves the master index.html shell."""
    # index.html is the outer page frame (navigation sidebar, top bar, etc.)
    # that stays on screen the whole time; individual pages are then loaded
    # into it separately via serve_subpage() below as the user navigates.
    template_path = CURRENT_DIR / "templates" / "index.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/page/{page_name:path}", response_class=HTMLResponse)
async def serve_subpage(page_name: str) -> HTMLResponse:
    """Dynamically reads and serves any subpage or popup HTML fragment from the templates
    folder, e.g. /page/workflows -> templates/workflows.html, /page/popup/abc_uploader ->
    templates/popup/abc_uploader.html."""
    # Same containment-safety idea as _resolve_vault_path above: page_name
    # comes from the web address itself, so this double-checks the actual
    # resolved file is still safely inside the templates/ folder before
    # serving it, rather than trusting whatever text was typed into the URL.
    templates_dir = CURRENT_DIR / "templates"
    page_path = (templates_dir / f"{page_name}.html").resolve()

    if templates_dir.resolve() not in page_path.parents or not page_path.exists():
        return HTMLResponse(
            content=f"<div class='p-6 text-rose-400 font-mono text-xs'>Error 404: Subpage '{page_name}.html' not found.</div>",
            status_code=404
        )

    with open(page_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    # This block only runs when the file is launched directly
    # (`python server.py`) -- it's what actually starts the web server and
    # makes it listen for browser connections on http://127.0.0.1:8090.
    # "127.0.0.1" (aka "localhost") means only this same computer can
    # connect to it; it isn't exposed to the wider network.
    try:
        # Pass clear directory strings to block the file-watcher from catching dynamic backend updates
        uvicorn.run(
            "server:app",
            host="127.0.0.1",
            port=8080,
            reload=True,
            log_config=None,  # Windows: dictConfig() reconfiguration crashes the spawned reload worker
            app_dir=str(CURRENT_DIR),
            # reload=True (above) makes the server watch project files and restart
            # itself automatically whenever one changes -- convenient while making
            # changes, but a handful of fast-changing/generated locations are
            # deliberately excluded below, because watching them would otherwise
            # trigger a constant, unwanted restart loop (the database file changing
            # on every save, browser automation profile folders changing during
            # every AI bridge call, compiled bytecode caches, etc.).
            reload_excludes=[
                "*.db",
                "*.pyc",
                "*__pycache__*",
                "*copilot_browser_profile*",
                "*abc_uploader_browser_profile*",
                "*/11_Processes/*",
                "*/12_Tasks/*",
                "*/13_Workflows/*",
                "*/14_Adapters/*",
                "*\\11_Processes\\*",
                "*\\12_Tasks\\*",
                "*\\13_Workflows\\*",
                "*\\14_Adapters\\*",
                "*/node_modules/*",
                "*\\node_modules\\*",
                "*/templates/static/*",
                "*\\templates\\static\\*"
            ]
        )
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server shut down safely via user request.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
