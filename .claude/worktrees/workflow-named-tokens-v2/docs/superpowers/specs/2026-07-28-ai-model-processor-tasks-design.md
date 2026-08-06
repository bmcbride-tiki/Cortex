# AI-Model "Processor" Tasks — Design Spec

**Date:** 2026-07-28
**Status:** Approved by user, ready for implementation plan

## Background

The Workflow Builder palette (`/api/workflow-builder/node-registry`) shows
function nodes titled "Gemini Processor", "Claude Processor", "ChatGPT
Processor", and three "NotebookLM: ..." nodes. These come entirely from
hard-coded metadata in `00_System/server.py`'s `FUNCTIONS_REGISTRY`
(`server.py:202-269`) — `tool_id`/`title`/`description`/`model` only, no
`md_path`, no backing file. The actual logic lives inline in
`00_System/workflow_engine.py`'s `_execute_function_node` if/elif ladder,
which calls the real adapters in `14_Adapters/{claude,chatgpt,gemini,notebooklm}_bridge/`.

User-reported symptom: "Claude Processor" is visible as a function in the
Workflow Builder, but doesn't exist anywhere in the file structure and
doesn't appear in the Tasks tab / API site — because it doesn't correspond
to a real file at all.

This is a real gap for some of these nodes and by-design for others:

* `builtin_review_gate`, `function_concatenate`, `function_logic_gate` are
  genuinely graph-only — they read upstream/backward-edge context
  (`loop_back_node_id`, connected-node lists) that only exists inside a
  running workflow. No standalone form makes sense. **Not touched by this
  spec.**
* `function_gemini_ask`, `function_claude_ask`, `function_chatgpt_ask`,
  `function_google_search`, `function_image_generate`,
  `function_notebooklm_create`, `function_notebooklm_upload_sources`,
  `function_notebooklm_prompt_loop` all just take a prompt/params and
  return text/JSON — the same shape as `ask_copilot`
  (`12_Tasks/ask_copilot/ask_copilot.py`), which **is** a real file.
  `ask_copilot.md` confirms this migration already happened once before:
  "Supersedes the retired `builtin_ai_processor` built-in engine function —
  same underlying call, now a real, independently-runnable Task." Claude,
  ChatGPT, Gemini, and NotebookLM never got the same treatment.

**Decision (scoped by user choice):** add real, standalone sibling Tasks
under `12_Tasks/` covering the 8 AI-model operations above (7 task files —
`ask_gemini` folds `function_gemini_ask` and `function_google_search`
together, see table below), following
`ask_copilot.py`'s exact pattern (import the bridge function directly,
in-process, one JSON CLI payload in/out). Leave the Workflow Builder's
existing Processor/NotebookLM function nodes, `FUNCTIONS_REGISTRY`, and
`workflow_engine.py` completely untouched — this is the lower-risk of two
options considered; it does not touch the frontend param editor or the
workflow dispatch contract. The existing nodes remain a second, workflow-only
way to do the same operation; reconciling that duplication is future work,
not this spec.

## New Tasks (`12_Tasks/`)

Each gets `<tool_id>.py` + `<tool_id>.md` + co-located `test_<tool_id>.py`
(assert-based, no framework — matches `test_ask_copilot.py`'s convention).

| tool_id | Wraps | Signature |
|---|---|---|
| `ask_claude` | `claude_bridge.ask(prompt)` | `run(prompt: str) -> dict` |
| `ask_chatgpt` | `chatgpt_bridge.ask(prompt)` | `run(prompt: str) -> dict` |
| `ask_gemini` | `gemini_bridge.ask_gemini(prompt, use_search)` | `run(prompt: str, search: bool = False) -> dict` — folds in what's currently the separate "Google Search"/Deep-Research registry entry; one file instead of two |
| `generate_gemini_image` | `gemini_bridge.generate_image(prompt, output_dir)` | `run(prompt: str, output_dir: str) -> dict` — mirrors existing `generate_copilot_image` Task |
| `create_notebooklm_notebook` | `notebooklm_bridge.create_notebook(title)` | `run(title: str) -> dict` |
| `upload_notebooklm_sources` | `notebooklm_bridge.upload_sources(notebook_id, file_paths)` | `run(notebook_id: str, file_paths: list[str]) -> dict` |
| `run_notebooklm_prompt_loop` | `notebooklm_bridge.prompt_loop(notebook_id, prompts)` | `run(notebook_id: str, prompts: list[str]) -> dict` |

All follow `ask_copilot.py`'s import shape, e.g. for `ask_claude`:

```python
CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "claude_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))
from claude_bridge import ask as _ask_claude

class AskClaude:
    def run(self, prompt: str) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        try:
            return {"success": True, **_ask_claude(prompt)}
        except Exception as e:
            return {"success": False, "response": f"ask_claude error: {e}"}
```

`main()` block: one positional JSON CLI arg, same error-handling/exit-code
shape as `ask_copilot.py`/`generate_copilot_image.py`.

`.md` docs follow `ask_copilot.md`'s frontmatter + section shape
(`tool_id`/`title`/`classification: '06_Tasks'`/`data_policy`/
`execution_engine`/`tags`, then Purpose/Input/Processing Logic/Output/Notes
for AI reuse sections). `data_policy` set per `model_classifications.py`'s
existing per-model level (`claude`→public, `chatgpt`→public, `gemini`→
protected_a, `notebooklm`→protected_a). `execution_engine`: `'mock'` for the
4 mock-backed ones, `'browser_automation'` for the 2 Gemini ones (real
Playwright session, matching `ask_copilot.md`'s own labeling).

Tests mock the imported bridge function (same technique as
`test_ask_copilot.py`'s `patch.object(mod, "_ask_copilot", ...)`) — no real
browser/network calls in the test suite. `run_notebooklm_prompt_loop`'s test
can run against real mock-mode logic directly (like
`test_notebooklm_bridge.py` does) since `notebooklm_bridge` has no external
side effects in mock mode.

## Two small fixes riding along

### 1. `gemini_bridge.py` gets a `MOCK_MODE` toggle

Unlike `claude_bridge`/`chatgpt_bridge`/`notebooklm_bridge`, `gemini_bridge.py`
has no `MOCK_MODE` — every action requires a live signed-in Playwright/Edge
session. Add the same pattern:

```python
MOCK_MODE = os.environ.get("GEMINI_MOCK_MODE", "1") != "0"
```

`ask_gemini()` and `generate_image()` check it first and return a
`[MOCK Gemini response] ...` / a fake file path under `output_dir` (writing
a tiny placeholder file, matching "realistic data contracts" — a real
`file_path` a caller can point at) without touching Playwright when
`MOCK_MODE` is on. When off, behavior is unchanged (real browser-session
flow, as today). This makes the new `ask_gemini`/`generate_gemini_image`
Tasks (and the existing workflow Processor nodes, as a side effect) runnable
out of the box, matching every other adapter's mock-first default.

### 2. Missing adapter-level tests

`notebooklm_bridge` has `test_notebooklm_bridge.py`; `claude_bridge` and
`chatgpt_bridge` don't. Add `test_claude_bridge.py` / `test_chatgpt_bridge.py`
(same shape: call `ask()` directly in mock mode, assert the `[MOCK ...]`
response shape, then assert `MOCK_MODE = False` raises `RuntimeError`).

## Testing (overall)

* 7 new co-located `test_*.py` files (Tasks) + 2 new adapter test files —
  all assert-based `__main__` self-checks, no pytest fixtures/framework,
  matching the repo-wide convention.
* `pytest` run across the repo after changes (per `CLAUDE.md` §5) to confirm
  nothing existing regresses.
* Manual check: `CoreRouter.get_visible_apps()` picks up all 7 new Task
  folders automatically (convention-over-configuration, no registration
  needed) and they appear in the Tasks tab / node registry.

## Explicitly Out of Scope

* Retiring `FUNCTIONS_REGISTRY`'s Processor/NotebookLM entries or rewiring
  `workflow_engine.py`'s dispatch for those nodes — user chose the
  lower-risk sibling-Task option over this.
* Any change to `workflow-builder.html` (frontend param panels, palette).
* Real (non-mock) API/MCP wiring for any of the four AI models.
* Reconciling the resulting duplication (workflow-only Processor node vs.
  standalone Task doing the same call) — noted as a known follow-up, not
  solved here.
