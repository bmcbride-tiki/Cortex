# AI-Model Processor Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Claude/ChatGPT/Gemini/NotebookLM each a real, standalone, file-backed Task under `12_Tasks/` (mirroring the existing `ask_copilot` Task), so they show up in the file structure and the Tasks tab instead of only existing as metadata-only Workflow Builder nodes.

**Architecture:** Each new Task is a thin wrapper — import the corresponding function directly from its `14_Adapters/*_bridge/*_bridge.py` adapter (no subprocess, same pattern as `ask_copilot.py`/`generate_copilot_image.py`), expose a `run(...) -> dict` method, and a `__main__` CLI entry that takes one JSON payload arg and prints one JSON line. `gemini_bridge.py` gets a `MOCK_MODE` toggle (the other three bridges already have one) so the two new Gemini Tasks are runnable without a live browser session. `claude_bridge`/`chatgpt_bridge` get adapter-level tests to match `notebooklm_bridge`'s existing one.

**Tech Stack:** Plain Python 3, stdlib `json`/`argparse`/`pathlib`, `unittest.mock.patch` for test mocking. No new dependencies.

## Global Constraints

- Every new Task ships as a `<tool_id>.py` + `<tool_id>.md` + co-located `test_<tool_id>.py` triple — the established convention for every file in `11_Processes/12_Tasks/13_Functions/14_Adapters` (see `ask_copilot/` for the canonical example).
- Tests are plain `assert`-based scripts with a `__main__` self-check block (`python test_X.py` must exit 0) — **not** pytest; pytest isn't installed in this repo and no existing test file uses it, despite `CLAUDE.md`'s generic mention of `pytest`. Follow the repo's actual convention.
- Tasks import their adapter's function directly (`sys.path.append` the adapter dir, then `from <bridge_module> import <fn>`) — no `subprocess`, matching `ask_copilot.py`/`generate_copilot_image.py`, not `core_router.py`'s subprocess-launch path.
- Mock-mode env vars already in use: `CLAUDE_MOCK_MODE`, `CHATGPT_MOCK_MODE`, `NOTEBOOKLM_MOCK_MODE` (all default on). This plan adds `GEMINI_MOCK_MODE` (default on) to match.
- CoreRouter auto-discovers any `12_Tasks/<tool_id>/<tool_id>.py` folder with no registration needed (convention over configuration) — but the Workflow Builder's model/icon tagging (`server.py`'s `TOOL_MODELS`/`TOOL_SVGL_MAP`/`TOOL_FA_ICON_MAP`) is a separate, explicit dict every existing Task with a model badge is listed in (e.g. `ask_copilot` → `MICROSOFT_COPILOT`). New Tasks must be added there too or they'll render with a blank model tag and a generic default icon.
- Workflow Builder's existing "Claude/ChatGPT/Gemini Processor" and "NotebookLM: ..." function nodes, `FUNCTIONS_REGISTRY`, `workflow_engine.py`, and `workflow-builder.html` are **out of scope** — do not modify them.

---

### Task 1: `gemini_bridge.py` gets a `MOCK_MODE` toggle

**Files:**
- Modify: `14_Adapters/gemini_bridge/gemini_bridge.py:74-86` (add `MOCK_MODE`), `:298-303` (`ask_gemini`), `:306-309` (`generate_image`)

**Interfaces:**
- Produces: `gemini_bridge.MOCK_MODE: bool` (module-level, same shape as `claude_bridge.MOCK_MODE`/`chatgpt_bridge.MOCK_MODE`/`notebooklm_bridge.MOCK_MODE`). `ask_gemini(prompt: str, use_search: bool = False) -> str` and `generate_image(prompt: str, output_dir: str) -> str` unchanged signatures, now short-circuit to a mock result when `MOCK_MODE` is on.

- [ ] **Step 1: Confirm playwright/loguru/gemini_webapi are already importable (no new deps needed)**

Run: `python -c "import playwright, loguru, gemini_webapi; print('OK')"`
Expected: `OK` (already verified present in this environment — if it ever fails, `pip install playwright loguru gemini-webapi` per `CLAUDE.md`'s auto-install rule before continuing).

- [ ] **Step 2: Add the `MOCK_MODE` flag**

In `14_Adapters/gemini_bridge/gemini_bridge.py`, find:

```python
from loguru import logger as _loguru_logger
_loguru_logger.remove()

# Locate the root workbrain directory, matching copilot_bridge.py's layout
```

Replace with:

```python
from loguru import logger as _loguru_logger
_loguru_logger.remove()

# Same MOCK_MODE / [MOCK ...] contract as claude_bridge.py, chatgpt_bridge.py, and
# notebooklm_bridge.py -- lets ask_gemini()/generate_image() run without a live
# signed-in Playwright/Edge session. Real (non-mock) behavior is unchanged when off.
MOCK_MODE = os.environ.get("GEMINI_MOCK_MODE", "1") != "0"

# Locate the root workbrain directory, matching copilot_bridge.py's layout
```

- [ ] **Step 3: Short-circuit `ask_gemini()` in mock mode**

Find:

```python
def ask_gemini(prompt: str, use_search: bool = False) -> str:
    """Text generation. use_search=True runs it as a full Deep Research pass instead."""
    # Public entry point used by main() below. Handles the "get the login
    # cookies, then run the actual async Gemini call" sequence in one step.
    psid, psidts = _get_session_cookies()
    return asyncio.run(_ask_async(psid, psidts, prompt, deep_research=use_search))
```

Replace with:

```python
def ask_gemini(prompt: str, use_search: bool = False) -> str:
    """Text generation. use_search=True runs it as a full Deep Research pass instead."""
    if MOCK_MODE:
        mode = "search-grounded " if use_search else ""
        return f"[MOCK {mode}Gemini response] {prompt[:300]}"
    # Public entry point used by main() below. Handles the "get the login
    # cookies, then run the actual async Gemini call" sequence in one step.
    psid, psidts = _get_session_cookies()
    return asyncio.run(_ask_async(psid, psidts, prompt, deep_research=use_search))
```

- [ ] **Step 4: Short-circuit `generate_image()` in mock mode**

Find:

```python
def generate_image(prompt: str, output_dir: str) -> str:
    """Generates one image via Gemini's built-in image generation, saved to output_dir."""
    psid, psidts = _get_session_cookies()
    return asyncio.run(_generate_image_async(psid, psidts, prompt, output_dir))
```

Replace with:

```python
def generate_image(prompt: str, output_dir: str) -> str:
    """Generates one image via Gemini's built-in image generation, saved to output_dir."""
    if MOCK_MODE:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"gemini_image_mock_{int(time.time())}.png"
        (out_dir / filename).write_bytes(b"\x89PNG\r\n\x1a\n")
        return str(out_dir / filename)
    psid, psidts = _get_session_cookies()
    return asyncio.run(_generate_image_async(psid, psidts, prompt, output_dir))
```

- [ ] **Step 5: Manual smoke check (no automated test file for this adapter — see Global Constraints)**

Run from the repo root:
```bash
python 14_Adapters/gemini_bridge/gemini_bridge.py "{\"action\": \"ask\", \"prompt\": \"hello\"}"
```
Expected: one JSON line, `{"success": true, "response": "[MOCK Gemini response] hello"}` — no browser window opens, no error.

- [ ] **Step 6: Commit**

```bash
git add 14_Adapters/gemini_bridge/gemini_bridge.py
git commit -m "Add MOCK_MODE toggle to gemini_bridge, matching the other 3 AI bridges"
```

---

### Task 2: `test_claude_bridge.py` (adapter-level test)

**Files:**
- Create: `14_Adapters/claude_bridge/test_claude_bridge.py`

**Interfaces:**
- Consumes: `claude_bridge.ask(prompt: str) -> dict`, `claude_bridge.MOCK_MODE: bool` (both already exist, unchanged).

- [ ] **Step 1: Write the test**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claude_bridge as cb


def test_ask_returns_mock_response():
    result = cb.ask("What is the capital of France?")
    assert result["response"].startswith("[MOCK Claude response]")
    assert "What is the capital of France?" in result["response"]


def test_mock_mode_off_fails_clearly():
    cb.MOCK_MODE = False
    try:
        try:
            cb.ask("Anything")
            assert False, "expected RuntimeError when MOCK_MODE is off"
        except RuntimeError as e:
            assert "not configured" in str(e)
    finally:
        cb.MOCK_MODE = True


if __name__ == "__main__":
    test_ask_returns_mock_response()
    test_mock_mode_off_fails_clearly()
    print("All claude_bridge self-checks passed.")
```

- [ ] **Step 2: Run it**

Run: `python 14_Adapters/claude_bridge/test_claude_bridge.py`
Expected: `All claude_bridge self-checks passed.`, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add 14_Adapters/claude_bridge/test_claude_bridge.py
git commit -m "Add missing adapter-level test for claude_bridge"
```

---

### Task 3: `test_chatgpt_bridge.py` (adapter-level test)

**Files:**
- Create: `14_Adapters/chatgpt_bridge/test_chatgpt_bridge.py`

**Interfaces:**
- Consumes: `chatgpt_bridge.ask(prompt: str) -> dict`, `chatgpt_bridge.MOCK_MODE: bool` (both already exist, unchanged).

- [ ] **Step 1: Write the test**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chatgpt_bridge as cb


def test_ask_returns_mock_response():
    result = cb.ask("What is the capital of France?")
    assert result["response"].startswith("[MOCK ChatGPT response]")
    assert "What is the capital of France?" in result["response"]


def test_mock_mode_off_fails_clearly():
    cb.MOCK_MODE = False
    try:
        try:
            cb.ask("Anything")
            assert False, "expected RuntimeError when MOCK_MODE is off"
        except RuntimeError as e:
            assert "not configured" in str(e)
    finally:
        cb.MOCK_MODE = True


if __name__ == "__main__":
    test_ask_returns_mock_response()
    test_mock_mode_off_fails_clearly()
    print("All chatgpt_bridge self-checks passed.")
```

- [ ] **Step 2: Run it**

Run: `python 14_Adapters/chatgpt_bridge/test_chatgpt_bridge.py`
Expected: `All chatgpt_bridge self-checks passed.`, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add 14_Adapters/chatgpt_bridge/test_chatgpt_bridge.py
git commit -m "Add missing adapter-level test for chatgpt_bridge"
```

---

### Task 4: `ask_claude` Task

**Files:**
- Create: `12_Tasks/ask_claude/ask_claude.py`
- Create: `12_Tasks/ask_claude/ask_claude.md`
- Create: `12_Tasks/ask_claude/test_ask_claude.py`

**Interfaces:**
- Consumes: `claude_bridge.ask(prompt: str) -> dict` (from `14_Adapters/claude_bridge/claude_bridge.py`, unchanged).
- Produces: `class AskClaude` with `run(self, prompt: str) -> dict`, returning `{"success": bool, "response": str}`.

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_claude as mod


def test_missing_prompt_fails_without_touching_bridge():
    result = mod.AskClaude().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_claude", return_value={"response": "Mocked Claude answer"}):
        result = mod.AskClaude().run("Summarize this.")
        assert result["success"] is True
        assert result["response"] == "Mocked Claude answer"


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_bridge()
    test_run_returns_response()
    print("All ask_claude self-checks passed.")
```

Save as `12_Tasks/ask_claude/test_ask_claude.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python 12_Tasks/ask_claude/test_ask_claude.py`
Expected: `ModuleNotFoundError: No module named 'ask_claude'`

- [ ] **Step 3: Write the implementation**

```python
# =============================================================================
# ask_claude.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: sends a prompt to Anthropic Claude and captures its response.
#   Mock-mode until a real ANTHROPIC_API_KEY exists (see claude_bridge.py).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/claude_bridge/claude_bridge.py`'s `ask()`, called directly
#     in-process (no subprocess).
#   - `test_ask_claude.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `prompt` as a
#     JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "claude_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from claude_bridge import ask as _ask_claude


class AskClaude:
    """Sends a prompt to Anthropic Claude and captures its response. Reuses
    claude_bridge's ask() function directly (no subprocess) -- mock-mode
    until a real ANTHROPIC_API_KEY exists."""

    def run(self, prompt: str) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        try:
            return {"success": True, **_ask_claude(prompt)}
        except Exception as e:
            return {"success": False, "response": f"ask_claude error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"prompt": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = AskClaude().run(prompt=params.get("prompt", ""))
    except Exception as e:
        result = {"success": False, "response": f"ask_claude error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
```

Save as `12_Tasks/ask_claude/ask_claude.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python 12_Tasks/ask_claude/test_ask_claude.py`
Expected: `All ask_claude self-checks passed.`, exit code 0.

- [ ] **Step 5: Write the companion doc**

```markdown
---
tool_id: 'ask_claude'
title: 'Ask Claude'
classification: '06_Tasks'
data_policy: 'public'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/claude]
---

# ask-claude

> **Status:** Active. Requires a setting (`prompt`) before running — a Task, not a Process. **Mock-mode** — no ANTHROPIC_API_KEY configured yet.

## Purpose

Sends a prompt to Anthropic Claude and captures its response. Uses
[[claude_bridge]] directly — mock-mode until a real ANTHROPIC_API_KEY
exists.

## Input

One JSON payload, positional CLI arg: `{"prompt": "..."}`.

## Processing Logic

Imports and calls `ask()` directly from
`14_Adapters/claude_bridge/claude_bridge.py` (same Python environment, no
subprocess). Returns a `[MOCK Claude response] ...` placeholder while
`CLAUDE_MOCK_MODE` is on (the default).

## Output

`{"success": true, "response": "..."}`.

## Notes for AI reuse

Tagged `model: "claude"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "Claude Processor" function node
(`function_claude_ask` in `FUNCTIONS_REGISTRY`) — same underlying
`claude_bridge.ask()` call, now also independently runnable outside a
workflow. Has no real side effects in mock mode; safe to run in automated
tests.
```

Save as `12_Tasks/ask_claude/ask_claude.md`.

- [ ] **Step 6: Commit**

```bash
git add 12_Tasks/ask_claude/
git commit -m "Add ask_claude Task, a standalone sibling of the workflow-only Claude Processor node"
```

---

### Task 5: `ask_chatgpt` Task

**Files:**
- Create: `12_Tasks/ask_chatgpt/ask_chatgpt.py`
- Create: `12_Tasks/ask_chatgpt/ask_chatgpt.md`
- Create: `12_Tasks/ask_chatgpt/test_ask_chatgpt.py`

**Interfaces:**
- Consumes: `chatgpt_bridge.ask(prompt: str) -> dict` (from `14_Adapters/chatgpt_bridge/chatgpt_bridge.py`, unchanged).
- Produces: `class AskChatGPT` with `run(self, prompt: str) -> dict`, returning `{"success": bool, "response": str}`.

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_chatgpt as mod


def test_missing_prompt_fails_without_touching_bridge():
    result = mod.AskChatGPT().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_chatgpt", return_value={"response": "Mocked ChatGPT answer"}):
        result = mod.AskChatGPT().run("Summarize this.")
        assert result["success"] is True
        assert result["response"] == "Mocked ChatGPT answer"


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_bridge()
    test_run_returns_response()
    print("All ask_chatgpt self-checks passed.")
```

Save as `12_Tasks/ask_chatgpt/test_ask_chatgpt.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python 12_Tasks/ask_chatgpt/test_ask_chatgpt.py`
Expected: `ModuleNotFoundError: No module named 'ask_chatgpt'`

- [ ] **Step 3: Write the implementation**

```python
# =============================================================================
# ask_chatgpt.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: sends a prompt to OpenAI ChatGPT and captures its response.
#   Mock-mode until a real OPENAI_API_KEY exists (see chatgpt_bridge.py).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/chatgpt_bridge/chatgpt_bridge.py`'s `ask()`, called
#     directly in-process (no subprocess).
#   - `test_ask_chatgpt.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `prompt` as a
#     JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "chatgpt_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from chatgpt_bridge import ask as _ask_chatgpt


class AskChatGPT:
    """Sends a prompt to OpenAI ChatGPT and captures its response. Reuses
    chatgpt_bridge's ask() function directly (no subprocess) -- mock-mode
    until a real OPENAI_API_KEY exists."""

    def run(self, prompt: str) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        try:
            return {"success": True, **_ask_chatgpt(prompt)}
        except Exception as e:
            return {"success": False, "response": f"ask_chatgpt error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"prompt": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = AskChatGPT().run(prompt=params.get("prompt", ""))
    except Exception as e:
        result = {"success": False, "response": f"ask_chatgpt error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
```

Save as `12_Tasks/ask_chatgpt/ask_chatgpt.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python 12_Tasks/ask_chatgpt/test_ask_chatgpt.py`
Expected: `All ask_chatgpt self-checks passed.`, exit code 0.

- [ ] **Step 5: Write the companion doc**

```markdown
---
tool_id: 'ask_chatgpt'
title: 'Ask ChatGPT'
classification: '06_Tasks'
data_policy: 'public'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/chatgpt]
---

# ask-chatgpt

> **Status:** Active. Requires a setting (`prompt`) before running — a Task, not a Process. **Mock-mode** — no OPENAI_API_KEY configured yet.

## Purpose

Sends a prompt to OpenAI ChatGPT and captures its response. Uses
[[chatgpt_bridge]] directly — mock-mode until a real OPENAI_API_KEY exists.

## Input

One JSON payload, positional CLI arg: `{"prompt": "..."}`.

## Processing Logic

Imports and calls `ask()` directly from
`14_Adapters/chatgpt_bridge/chatgpt_bridge.py` (same Python environment, no
subprocess). Returns a `[MOCK ChatGPT response] ...` placeholder while
`CHATGPT_MOCK_MODE` is on (the default).

## Output

`{"success": true, "response": "..."}`.

## Notes for AI reuse

Tagged `model: "chatgpt"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "ChatGPT Processor" function node
(`function_chatgpt_ask` in `FUNCTIONS_REGISTRY`) — same underlying
`chatgpt_bridge.ask()` call, now also independently runnable outside a
workflow. Has no real side effects in mock mode; safe to run in automated
tests.
```

Save as `12_Tasks/ask_chatgpt/ask_chatgpt.md`.

- [ ] **Step 6: Commit**

```bash
git add 12_Tasks/ask_chatgpt/
git commit -m "Add ask_chatgpt Task, a standalone sibling of the workflow-only ChatGPT Processor node"
```

---

### Task 6: `ask_gemini` Task

**Files:**
- Create: `12_Tasks/ask_gemini/ask_gemini.py`
- Create: `12_Tasks/ask_gemini/ask_gemini.md`
- Create: `12_Tasks/ask_gemini/test_ask_gemini.py`

**Interfaces:**
- Consumes: `gemini_bridge.ask_gemini(prompt: str, use_search: bool = False) -> str` (from Task 1, now mock-aware).
- Produces: `class AskGemini` with `run(self, prompt: str, search: bool = False) -> dict`, returning `{"success": bool, "response": str}`.

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask_gemini as mod


def test_missing_prompt_fails_without_touching_bridge():
    result = mod.AskGemini().run("")
    assert result["success"] is False


def test_run_returns_response():
    with patch.object(mod, "_ask_gemini", return_value="Mocked Gemini answer") as mock_call:
        result = mod.AskGemini().run("Summarize this.", search=True)
        assert result["success"] is True
        assert result["response"] == "Mocked Gemini answer"
        mock_call.assert_called_once_with("Summarize this.", use_search=True)


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_bridge()
    test_run_returns_response()
    print("All ask_gemini self-checks passed.")
```

Save as `12_Tasks/ask_gemini/test_ask_gemini.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python 12_Tasks/ask_gemini/test_ask_gemini.py`
Expected: `ModuleNotFoundError: No module named 'ask_gemini'`

- [ ] **Step 3: Write the implementation**

```python
# =============================================================================
# ask_gemini.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: sends a prompt to Google Gemini and captures its response, or runs
#   it as a full Deep Research pass when search=True. Uses your signed-in
#   Google session via gemini_bridge.py (no API key) -- runs in mock mode by
#   default (GEMINI_MOCK_MODE) until a real session is configured.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/gemini_bridge/gemini_bridge.py`'s `ask_gemini()`, called
#     directly in-process (no subprocess).
#   - `test_ask_gemini.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `prompt`/`search`
#     as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import ask_gemini as _ask_gemini


class AskGemini:
    """Sends a prompt to Google Gemini and captures its response. Reuses
    gemini_bridge's ask_gemini() function directly (no subprocess) -- uses
    your signed-in Gemini session, or a mock response while GEMINI_MOCK_MODE
    is on (the default)."""

    def run(self, prompt: str, search: bool = False) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        try:
            return {"success": True, "response": _ask_gemini(prompt, use_search=search)}
        except Exception as e:
            return {"success": False, "response": f"ask_gemini error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"prompt": "...", "search": false}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = AskGemini().run(prompt=params.get("prompt", ""), search=bool(params.get("search", False)))
    except Exception as e:
        result = {"success": False, "response": f"ask_gemini error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
```

Save as `12_Tasks/ask_gemini/ask_gemini.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python 12_Tasks/ask_gemini/test_ask_gemini.py`
Expected: `All ask_gemini self-checks passed.`, exit code 0.

- [ ] **Step 5: Write the companion doc**

```markdown
---
tool_id: 'ask_gemini'
title: 'Ask Gemini'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'browser_automation'
tags: [type/task, domain/04-task, tier/zero-input, function/gemini]
---

# ask-gemini

> **Status:** Active. Requires a setting (`prompt`) before running — a Task, not a Process. **Mock-mode by default** (`GEMINI_MOCK_MODE`) — set it to `0` to use a real signed-in Gemini session.

## Purpose

Sends a prompt to Google Gemini and captures its response. Set `search:
true` to run it as a full Deep Research pass instead of a normal single-turn
answer. Uses [[gemini_bridge]] directly — your signed-in Gemini session, no
API key, when not in mock mode.

## Input

One JSON payload, positional CLI arg: `{"prompt": "...", "search": false}`.

## Processing Logic

Imports and calls `ask_gemini()` directly from
`14_Adapters/gemini_bridge/gemini_bridge.py` (same Python environment, no
subprocess). Returns a `[MOCK Gemini response] ...` placeholder while
`GEMINI_MOCK_MODE` is on (the default); otherwise a real Playwright browser
automation call against the signed-in session.

## Output

`{"success": true, "response": "..."}`.

## Notes for AI reuse

Tagged `model: "gemini"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "Gemini Processor" and "Google Search" function
nodes (`function_gemini_ask`/`function_google_search` in
`FUNCTIONS_REGISTRY`) — same underlying `gemini_bridge.ask_gemini()` call,
now also independently runnable outside a workflow, with both modes folded
into one `search` flag.
```

Save as `12_Tasks/ask_gemini/ask_gemini.md`.

- [ ] **Step 6: Commit**

```bash
git add 12_Tasks/ask_gemini/
git commit -m "Add ask_gemini Task, a standalone sibling of the workflow-only Gemini Processor/Google Search nodes"
```

---

### Task 7: `generate_gemini_image` Task

**Files:**
- Create: `12_Tasks/generate_gemini_image/generate_gemini_image.py`
- Create: `12_Tasks/generate_gemini_image/generate_gemini_image.md`
- Create: `12_Tasks/generate_gemini_image/test_generate_gemini_image.py`

**Interfaces:**
- Consumes: `gemini_bridge.generate_image(prompt: str, output_dir: str) -> str` (from Task 1, now mock-aware).
- Produces: `class GenerateGeminiImage` with `run(self, prompt: str, output_dir: str) -> dict`, returning `{"success": bool, "file_path": str}`.

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_gemini_image as mod


def test_missing_prompt_fails_without_touching_bridge():
    result = mod.GenerateGeminiImage().run("", "C:/tmp")
    assert result["success"] is False


def test_missing_output_dir_fails_without_touching_bridge():
    result = mod.GenerateGeminiImage().run("a cat", "")
    assert result["success"] is False


def test_run_returns_file_path():
    with patch.object(mod, "_generate_image", return_value="C:/tmp/gemini_image_mock_1.png") as mock_call:
        result = mod.GenerateGeminiImage().run("a cat", "C:/tmp")
        assert result["success"] is True
        assert result["file_path"] == "C:/tmp/gemini_image_mock_1.png"
        mock_call.assert_called_once_with("a cat", "C:/tmp")


if __name__ == "__main__":
    test_missing_prompt_fails_without_touching_bridge()
    test_missing_output_dir_fails_without_touching_bridge()
    test_run_returns_file_path()
    print("All generate_gemini_image self-checks passed.")
```

Save as `12_Tasks/generate_gemini_image/test_generate_gemini_image.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python 12_Tasks/generate_gemini_image/test_generate_gemini_image.py`
Expected: `ModuleNotFoundError: No module named 'generate_gemini_image'`

- [ ] **Step 3: Write the implementation**

```python
# =============================================================================
# generate_gemini_image.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: asks Google Gemini's built-in image generation to create an image
#   from a prompt and saves it to a local folder. Runs in mock mode by
#   default (GEMINI_MOCK_MODE) until a real session is configured.
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/gemini_bridge/gemini_bridge.py`'s `generate_image()`,
#     called directly in-process (no subprocess).
#   - `test_generate_gemini_image.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `prompt`/`output_dir` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "gemini_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from gemini_bridge import generate_image as _generate_image


class GenerateGeminiImage:
    """Asks the Gemini bridge to generate an image and saves it to a local
    folder. Reuses gemini_bridge's generate_image() function directly (no
    subprocess) -- uses your signed-in Gemini session, or a mock placeholder
    file while GEMINI_MOCK_MODE is on (the default)."""

    def run(self, prompt: str, output_dir: str) -> dict:
        if not prompt:
            return {"success": False, "response": "A prompt is required."}
        if not output_dir:
            return {"success": False, "response": "An output_dir is required."}
        try:
            return {"success": True, "file_path": _generate_image(prompt, output_dir)}
        except Exception as e:
            return {"success": False, "response": f"generate_gemini_image error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"prompt": "...", "output_dir": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = GenerateGeminiImage().run(prompt=params.get("prompt", ""), output_dir=params.get("output_dir", ""))
    except Exception as e:
        result = {"success": False, "response": f"generate_gemini_image error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
```

Save as `12_Tasks/generate_gemini_image/generate_gemini_image.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python 12_Tasks/generate_gemini_image/test_generate_gemini_image.py`
Expected: `All generate_gemini_image self-checks passed.`, exit code 0.

- [ ] **Step 5: Write the companion doc**

```markdown
---
tool_id: 'generate_gemini_image'
title: 'Generate Gemini Image'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'browser_automation'
tags: [type/task, domain/04-task, tier/zero-input, function/gemini]
---

# generate-gemini-image

> **Status:** Active. Requires settings (`prompt`, `output_dir`) before running — a Task, not a Process. **Mock-mode by default** (`GEMINI_MOCK_MODE`) — set it to `0` to use a real signed-in Gemini session.

## Purpose

Asks Google Gemini's built-in image generation to create an image from a
prompt and saves it to a local folder. Uses [[gemini_bridge]] directly —
your signed-in Gemini session, no API key, when not in mock mode.

## Input

One JSON payload, positional CLI arg: `{"prompt": "...", "output_dir": "..."}`.

## Processing Logic

Imports and calls `generate_image()` directly from
`14_Adapters/gemini_bridge/gemini_bridge.py` (same Python environment, no
subprocess). While `GEMINI_MOCK_MODE` is on (the default), writes a small
placeholder PNG-signature file into `output_dir` and returns its path
instead of launching a real browser session.

## Output

`{"success": true, "file_path": "..."}`.

## Notes for AI reuse

Tagged `model: "gemini"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "Image Generate" function node
(`function_image_generate` in `FUNCTIONS_REGISTRY`) — same underlying
`gemini_bridge.generate_image()` call, now also independently runnable
outside a workflow.
```

Save as `12_Tasks/generate_gemini_image/generate_gemini_image.md`.

- [ ] **Step 6: Commit**

```bash
git add 12_Tasks/generate_gemini_image/
git commit -m "Add generate_gemini_image Task, a standalone sibling of the workflow-only Image Generate node"
```

---

### Task 8: `create_notebooklm_notebook` Task

**Files:**
- Create: `12_Tasks/create_notebooklm_notebook/create_notebooklm_notebook.py`
- Create: `12_Tasks/create_notebooklm_notebook/create_notebooklm_notebook.md`
- Create: `12_Tasks/create_notebooklm_notebook/test_create_notebooklm_notebook.py`

**Interfaces:**
- Consumes: `notebooklm_bridge.create_notebook(title: str) -> dict` (from `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`, unchanged).
- Produces: `class CreateNotebookLMNotebook` with `run(self, title: str) -> dict`, returning `{"success": bool, "notebook_id": str, "title": str}`.

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import create_notebooklm_notebook as mod


def test_run_defaults_title_when_blank():
    with patch.object(mod, "_create_notebook", return_value={"notebook_id": "nb_test", "title": "Untitled Notebook"}) as mock_call:
        result = mod.CreateNotebookLMNotebook().run("")
        assert result["success"] is True
        mock_call.assert_called_once_with("Untitled Notebook")


def test_run_returns_notebook_id():
    with patch.object(mod, "_create_notebook", return_value={"notebook_id": "nb_abc123", "title": "My Notebook"}):
        result = mod.CreateNotebookLMNotebook().run("My Notebook")
        assert result["success"] is True
        assert result["notebook_id"] == "nb_abc123"
        assert result["title"] == "My Notebook"


if __name__ == "__main__":
    test_run_defaults_title_when_blank()
    test_run_returns_notebook_id()
    print("All create_notebooklm_notebook self-checks passed.")
```

Save as `12_Tasks/create_notebooklm_notebook/test_create_notebooklm_notebook.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python 12_Tasks/create_notebooklm_notebook/test_create_notebooklm_notebook.py`
Expected: `ModuleNotFoundError: No module named 'create_notebooklm_notebook'`

- [ ] **Step 3: Write the implementation**

```python
# =============================================================================
# create_notebooklm_notebook.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: creates a new Google NotebookLM notebook. Mock-mode until real
#   API/MCP access exists (see notebooklm_bridge.py).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`'s
#     `create_notebook()`, called directly in-process (no subprocess).
#   - `test_create_notebooklm_notebook.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its `title` as a
#     JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "notebooklm_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from notebooklm_bridge import create_notebook as _create_notebook


class CreateNotebookLMNotebook:
    """Creates a new NotebookLM notebook. Reuses notebooklm_bridge's
    create_notebook() function directly (no subprocess) -- mock-mode until
    real API/MCP access exists."""

    def run(self, title: str) -> dict:
        title = title or "Untitled Notebook"
        try:
            return {"success": True, **_create_notebook(title)}
        except Exception as e:
            return {"success": False, "response": f"create_notebooklm_notebook error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"title": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = CreateNotebookLMNotebook().run(title=params.get("title", ""))
    except Exception as e:
        result = {"success": False, "response": f"create_notebooklm_notebook error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
```

Save as `12_Tasks/create_notebooklm_notebook/create_notebooklm_notebook.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python 12_Tasks/create_notebooklm_notebook/test_create_notebooklm_notebook.py`
Expected: `All create_notebooklm_notebook self-checks passed.`, exit code 0.

- [ ] **Step 5: Write the companion doc**

```markdown
---
tool_id: 'create_notebooklm_notebook'
title: 'Create NotebookLM Notebook'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/notebooklm]
---

# create-notebooklm-notebook

> **Status:** Active. Optional setting (`title`) before running — a Task, not a Process. **Mock-mode** — no real NotebookLM API/MCP access configured yet.

## Purpose

Creates a new Google NotebookLM notebook. Uses [[notebooklm_bridge]]
directly — mock-mode until real API/MCP access exists.

## Input

One JSON payload, positional CLI arg: `{"title": "..."}` (defaults to
`"Untitled Notebook"` if blank).

## Processing Logic

Imports and calls `create_notebook()` directly from
`14_Adapters/notebooklm_bridge/notebooklm_bridge.py` (same Python
environment, no subprocess). Returns a simulated `notebook_id` (e.g.
`nb_<uuid4 hex[:12]>`) while `NOTEBOOKLM_MOCK_MODE` is on (the default).

## Output

`{"success": true, "notebook_id": "...", "title": "..."}`.

## Notes for AI reuse

Tagged `model: "notebooklm"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "NotebookLM: Create Notebook" function node
(`function_notebooklm_create` in `FUNCTIONS_REGISTRY`) — same underlying
`notebooklm_bridge.create_notebook()` call, now also independently runnable
outside a workflow. The returned `notebook_id` feeds
[[upload_notebooklm_sources]] and [[run_notebooklm_prompt_loop]].
```

Save as `12_Tasks/create_notebooklm_notebook/create_notebooklm_notebook.md`.

- [ ] **Step 6: Commit**

```bash
git add 12_Tasks/create_notebooklm_notebook/
git commit -m "Add create_notebooklm_notebook Task, a standalone sibling of the workflow-only NotebookLM Create node"
```

---

### Task 9: `upload_notebooklm_sources` Task

**Files:**
- Create: `12_Tasks/upload_notebooklm_sources/upload_notebooklm_sources.py`
- Create: `12_Tasks/upload_notebooklm_sources/upload_notebooklm_sources.md`
- Create: `12_Tasks/upload_notebooklm_sources/test_upload_notebooklm_sources.py`

**Interfaces:**
- Consumes: `notebooklm_bridge.upload_sources(notebook_id: str, file_paths: list) -> dict` (unchanged).
- Produces: `class UploadNotebookLMSources` with `run(self, notebook_id: str, file_paths: list) -> dict`, returning `{"success": bool, "sources": list}`.

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upload_notebooklm_sources as mod


def test_missing_notebook_id_fails_without_touching_bridge():
    result = mod.UploadNotebookLMSources().run("", ["a.pdf"])
    assert result["success"] is False


def test_missing_file_paths_fails_without_touching_bridge():
    result = mod.UploadNotebookLMSources().run("nb_test", [])
    assert result["success"] is False


def test_run_returns_sources():
    fake_sources = {"sources": [{"source_id": "src_1", "filename": "a.pdf", "status": "processed"}]}
    with patch.object(mod, "_upload_sources", return_value=fake_sources) as mock_call:
        result = mod.UploadNotebookLMSources().run("nb_test", ["a.pdf"])
        assert result["success"] is True
        assert result["sources"] == fake_sources["sources"]
        mock_call.assert_called_once_with("nb_test", ["a.pdf"])


if __name__ == "__main__":
    test_missing_notebook_id_fails_without_touching_bridge()
    test_missing_file_paths_fails_without_touching_bridge()
    test_run_returns_sources()
    print("All upload_notebooklm_sources self-checks passed.")
```

Save as `12_Tasks/upload_notebooklm_sources/test_upload_notebooklm_sources.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python 12_Tasks/upload_notebooklm_sources/test_upload_notebooklm_sources.py`
Expected: `ModuleNotFoundError: No module named 'upload_notebooklm_sources'`

- [ ] **Step 3: Write the implementation**

```python
# =============================================================================
# upload_notebooklm_sources.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: uploads source files (PDF/Docx/JSON) to a NotebookLM notebook.
#   Mock-mode until real API/MCP access exists (see notebooklm_bridge.py).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`'s
#     `upload_sources()`, called directly in-process (no subprocess).
#   - `test_upload_notebooklm_sources.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `notebook_id`/`file_paths` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "notebooklm_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from notebooklm_bridge import upload_sources as _upload_sources


class UploadNotebookLMSources:
    """Uploads source files to a NotebookLM notebook. Reuses
    notebooklm_bridge's upload_sources() function directly (no subprocess) --
    mock-mode until real API/MCP access exists. Still validates that every
    given file path is a real file on disk, even in mock mode."""

    def run(self, notebook_id: str, file_paths: list) -> dict:
        if not notebook_id:
            return {"success": False, "response": "A notebook_id is required."}
        if not file_paths:
            return {"success": False, "response": "At least one file path is required."}
        try:
            return {"success": True, **_upload_sources(notebook_id, file_paths)}
        except Exception as e:
            return {"success": False, "response": f"upload_notebooklm_sources error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"notebook_id": "...", "file_paths": ["..."]}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = UploadNotebookLMSources().run(
            notebook_id=params.get("notebook_id", ""),
            file_paths=params.get("file_paths", []),
        )
    except Exception as e:
        result = {"success": False, "response": f"upload_notebooklm_sources error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
```

Save as `12_Tasks/upload_notebooklm_sources/upload_notebooklm_sources.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python 12_Tasks/upload_notebooklm_sources/test_upload_notebooklm_sources.py`
Expected: `All upload_notebooklm_sources self-checks passed.`, exit code 0.

- [ ] **Step 5: Write the companion doc**

```markdown
---
tool_id: 'upload_notebooklm_sources'
title: 'Upload NotebookLM Sources'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/notebooklm]
---

# upload-notebooklm-sources

> **Status:** Active. Requires settings (`notebook_id`, `file_paths`) before running — a Task, not a Process. **Mock-mode** — no real NotebookLM API/MCP access configured yet.

## Purpose

Uploads source files (PDF/Docx/JSON) to a NotebookLM notebook. Uses
[[notebooklm_bridge]] directly — mock-mode until real API/MCP access
exists. Still validates that every given file path is a real file on disk,
even in mock mode (a real usage mistake should surface immediately).

## Input

One JSON payload, positional CLI arg:
`{"notebook_id": "...", "file_paths": ["C:\\...\\source1.pdf"]}`.

## Processing Logic

Imports and calls `upload_sources()` directly from
`14_Adapters/notebooklm_bridge/notebooklm_bridge.py` (same Python
environment, no subprocess).

## Output

`{"success": true, "sources": [{"source_id": "...", "filename": "...", "status": "processed"}, ...]}`.

## Notes for AI reuse

Tagged `model: "notebooklm"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "NotebookLM: Upload Sources" function node
(`function_notebooklm_upload_sources` in `FUNCTIONS_REGISTRY`) — same
underlying `notebooklm_bridge.upload_sources()` call, now also
independently runnable outside a workflow. Typically chained after
[[create_notebooklm_notebook]].
```

Save as `12_Tasks/upload_notebooklm_sources/upload_notebooklm_sources.md`.

- [ ] **Step 6: Commit**

```bash
git add 12_Tasks/upload_notebooklm_sources/
git commit -m "Add upload_notebooklm_sources Task, a standalone sibling of the workflow-only NotebookLM Upload node"
```

---

### Task 10: `run_notebooklm_prompt_loop` Task

**Files:**
- Create: `12_Tasks/run_notebooklm_prompt_loop/run_notebooklm_prompt_loop.py`
- Create: `12_Tasks/run_notebooklm_prompt_loop/run_notebooklm_prompt_loop.md`
- Create: `12_Tasks/run_notebooklm_prompt_loop/test_run_notebooklm_prompt_loop.py`

**Interfaces:**
- Consumes: `notebooklm_bridge.prompt_loop(notebook_id: str, prompts: list) -> dict` (unchanged).
- Produces: `class RunNotebookLMPromptLoop` with `run(self, notebook_id: str, prompts: list) -> dict`, returning `{"success": bool, "qa_pairs": list}`.

- [ ] **Step 1: Write the failing test**

```python
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_notebooklm_prompt_loop as mod


def test_missing_notebook_id_fails_without_touching_bridge():
    result = mod.RunNotebookLMPromptLoop().run("", ["What is X?"])
    assert result["success"] is False


def test_missing_prompts_fails_without_touching_bridge():
    result = mod.RunNotebookLMPromptLoop().run("nb_test", [])
    assert result["success"] is False


def test_run_returns_qa_pairs():
    fake_qa = {"qa_pairs": [{"prompt": "What is X?", "response": "X is..."}]}
    with patch.object(mod, "_prompt_loop", return_value=fake_qa) as mock_call:
        result = mod.RunNotebookLMPromptLoop().run("nb_test", ["What is X?"])
        assert result["success"] is True
        assert result["qa_pairs"] == fake_qa["qa_pairs"]
        mock_call.assert_called_once_with("nb_test", ["What is X?"])


if __name__ == "__main__":
    test_missing_notebook_id_fails_without_touching_bridge()
    test_missing_prompts_fails_without_touching_bridge()
    test_run_returns_qa_pairs()
    print("All run_notebooklm_prompt_loop self-checks passed.")
```

Save as `12_Tasks/run_notebooklm_prompt_loop/test_run_notebooklm_prompt_loop.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python 12_Tasks/run_notebooklm_prompt_loop/test_run_notebooklm_prompt_loop.py`
Expected: `ModuleNotFoundError: No module named 'run_notebooklm_prompt_loop'`

- [ ] **Step 3: Write the implementation**

```python
# =============================================================================
# run_notebooklm_prompt_loop.py
# -----------------------------------------------------------------------------
# WHAT THIS FILE DOES
#   A Task: asks a NotebookLM notebook a sequence of questions and collects
#   the answers. Mock-mode until real API/MCP access exists (see
#   notebooklm_bridge.py).
#
# WHAT IT INTERACTS WITH
#   - `14_Adapters/notebooklm_bridge/notebooklm_bridge.py`'s
#     `prompt_loop()`, called directly in-process (no subprocess).
#   - `test_run_notebooklm_prompt_loop.py`, this file's paired test.
#   - `core_router.py`/`server.py`, which pass this Task its
#     `notebook_id`/`prompts` as a JSON payload.
# =============================================================================

import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ADAPTER_DIR = CURRENT_DIR.parents[1] / "14_Adapters" / "notebooklm_bridge"
if str(ADAPTER_DIR) not in sys.path:
    sys.path.append(str(ADAPTER_DIR))

from notebooklm_bridge import prompt_loop as _prompt_loop


class RunNotebookLMPromptLoop:
    """Asks a NotebookLM notebook a sequence of questions and collects the
    answers. Reuses notebooklm_bridge's prompt_loop() function directly (no
    subprocess) -- mock-mode until real API/MCP access exists."""

    def run(self, notebook_id: str, prompts: list) -> dict:
        if not notebook_id:
            return {"success": False, "response": "A notebook_id is required."}
        if not prompts:
            return {"success": False, "response": "At least one prompt is required."}
        try:
            return {"success": True, **_prompt_loop(notebook_id, prompts)}
        except Exception as e:
            return {"success": False, "response": f"run_notebooklm_prompt_loop error: {e}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"notebook_id": "...", "prompts": ["..."]}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = RunNotebookLMPromptLoop().run(
            notebook_id=params.get("notebook_id", ""),
            prompts=params.get("prompts", []),
        )
    except Exception as e:
        result = {"success": False, "response": f"run_notebooklm_prompt_loop error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
```

Save as `12_Tasks/run_notebooklm_prompt_loop/run_notebooklm_prompt_loop.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python 12_Tasks/run_notebooklm_prompt_loop/test_run_notebooklm_prompt_loop.py`
Expected: `All run_notebooklm_prompt_loop self-checks passed.`, exit code 0.

- [ ] **Step 5: Write the companion doc**

```markdown
---
tool_id: 'run_notebooklm_prompt_loop'
title: 'Run NotebookLM Prompt Loop'
classification: '06_Tasks'
data_policy: 'protected_a'
execution_engine: 'mock'
tags: [type/task, domain/04-task, tier/zero-input, function/notebooklm]
---

# run-notebooklm-prompt-loop

> **Status:** Active. Requires settings (`notebook_id`, `prompts`) before running — a Task, not a Process. **Mock-mode** — no real NotebookLM API/MCP access configured yet.

## Purpose

Asks a NotebookLM notebook a sequence of questions and collects the answers
as JSON. Uses [[notebooklm_bridge]] directly — mock-mode until real API/MCP
access exists.

## Input

One JSON payload, positional CLI arg:
`{"notebook_id": "...", "prompts": ["What is Period 1 about?"]}`.

## Processing Logic

Imports and calls `prompt_loop()` directly from
`14_Adapters/notebooklm_bridge/notebooklm_bridge.py` (same Python
environment, no subprocess), asking each prompt in order.

## Output

`{"success": true, "qa_pairs": [{"prompt": "...", "response": "..."}, ...]}`.

## Notes for AI reuse

Tagged `model: "notebooklm"` in `server.py`'s `TOOL_MODELS`. Sibling to the
Workflow Builder's existing "NotebookLM: Prompt Loop" function node
(`function_notebooklm_prompt_loop` in `FUNCTIONS_REGISTRY`) — same
underlying `notebooklm_bridge.prompt_loop()` call, now also independently
runnable outside a workflow. Typically chained after
[[create_notebooklm_notebook]] and [[upload_notebooklm_sources]]; output
feeds directly into `export_to_json` for a `stem.json` file.
```

Save as `12_Tasks/run_notebooklm_prompt_loop/run_notebooklm_prompt_loop.md`.

- [ ] **Step 6: Commit**

```bash
git add 12_Tasks/run_notebooklm_prompt_loop/
git commit -m "Add run_notebooklm_prompt_loop Task, a standalone sibling of the workflow-only NotebookLM Prompt Loop node"
```

---

### Task 11: Wire the 7 new tool_ids into `server.py`'s model/icon maps

**Files:**
- Modify: `00_System/server.py:294-328` (`TOOL_MODELS`), `:369-417` (`TOOL_SVGL_MAP`), `:421-460` (`TOOL_FA_ICON_MAP`)

**Interfaces:**
- Consumes: `tool_id` strings from Tasks 4-10 (`ask_claude`, `ask_chatgpt`, `ask_gemini`, `generate_gemini_image`, `create_notebooklm_notebook`, `upload_notebooklm_sources`, `run_notebooklm_prompt_loop`); `CLAUDE_ICON`/`OPENAI_ICON`/`GEMINI_ICON` constants already defined at `server.py:364-366`.

- [ ] **Step 1: Add model tags to `TOOL_MODELS`**

In `00_System/server.py`, find:

```python
    "generate_pptx_from_word_with_copilot": "copilot",
}
```

Replace with:

```python
    "generate_pptx_from_word_with_copilot": "copilot",
    "ask_claude": "claude",
    "ask_chatgpt": "chatgpt",
    "ask_gemini": "gemini",
    "generate_gemini_image": "gemini",
    "create_notebooklm_notebook": "notebooklm",
    "upload_notebooklm_sources": "notebooklm",
    "run_notebooklm_prompt_loop": "notebooklm",
}
```

- [ ] **Step 2: Add brand icons to `TOOL_SVGL_MAP`**

Find:

```python
    "chatgpt_bridge": OPENAI_ICON,
    "function_chatgpt_ask": OPENAI_ICON,
}
```

Replace with:

```python
    "chatgpt_bridge": OPENAI_ICON,
    "function_chatgpt_ask": OPENAI_ICON,
    "ask_claude": CLAUDE_ICON,
    "ask_chatgpt": OPENAI_ICON,
    "ask_gemini": GEMINI_ICON,
    "generate_gemini_image": GEMINI_ICON,
}
```

- [ ] **Step 3: Add Font Awesome icons for the 3 NotebookLM tasks (no SVGL logo exists)**

Find:

```python
    "notebooklm_bridge": "fa-book-open",
    "function_notebooklm_create": "fa-book-open",
    "function_notebooklm_upload_sources": "fa-book-open",
    "function_notebooklm_prompt_loop": "fa-book-open",
```

Replace with:

```python
    "notebooklm_bridge": "fa-book-open",
    "function_notebooklm_create": "fa-book-open",
    "function_notebooklm_upload_sources": "fa-book-open",
    "function_notebooklm_prompt_loop": "fa-book-open",
    "create_notebooklm_notebook": "fa-book-open",
    "upload_notebooklm_sources": "fa-book-open",
    "run_notebooklm_prompt_loop": "fa-book-open",
```

- [ ] **Step 4: Verify the dicts parse and contain the new entries**

Run:
```bash
python -c "
import ast
tree = ast.parse(open('00_System/server.py', encoding='utf-8').read())
print('server.py parses OK')
"
```
Expected: `server.py parses OK` (a syntax check that doesn't require importing FastAPI/DB dependencies).

- [ ] **Step 5: Commit**

```bash
git add 00_System/server.py
git commit -m "Register the 7 new AI-model Tasks in server.py's model/icon maps"
```

---

### Task 12: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run every new test file**

```bash
python 14_Adapters/claude_bridge/test_claude_bridge.py
python 14_Adapters/chatgpt_bridge/test_chatgpt_bridge.py
python 12_Tasks/ask_claude/test_ask_claude.py
python 12_Tasks/ask_chatgpt/test_ask_chatgpt.py
python 12_Tasks/ask_gemini/test_ask_gemini.py
python 12_Tasks/generate_gemini_image/test_generate_gemini_image.py
python 12_Tasks/create_notebooklm_notebook/test_create_notebooklm_notebook.py
python 12_Tasks/upload_notebooklm_sources/test_upload_notebooklm_sources.py
python 12_Tasks/run_notebooklm_prompt_loop/test_run_notebooklm_prompt_loop.py
```
Expected: every one prints its `All ... self-checks passed.` line and exits 0.

- [ ] **Step 2: Confirm CoreRouter auto-discovers all 7 new Tasks**

```bash
python -c "
import sys
sys.path.insert(0, '00_System')
from core_router import CoreRouter
manifest = CoreRouter().get_visible_apps()
ids = {e['tool_id'] for e in manifest['06_Tasks']}
expected = {
    'ask_claude', 'ask_chatgpt', 'ask_gemini', 'generate_gemini_image',
    'create_notebooklm_notebook', 'upload_notebooklm_sources', 'run_notebooklm_prompt_loop',
}
missing = expected - ids
assert not missing, f'missing from Tasks manifest: {missing}'
print('All 7 new Tasks discovered by CoreRouter.get_visible_apps()')
"
```
Run this from the repo root (`C:\Cortex`).
Expected: `All 7 new Tasks discovered by CoreRouter.get_visible_apps()`

- [ ] **Step 3: Manual UI check (not automatable — note for the user)**

Start the dev server (however it's normally run, e.g. `uvicorn server:app --reload` from `00_System/`) and open the Tasks tab plus the Workflow Builder palette in a browser. Confirm the 7 new Tasks appear in the Tasks tab with the correct AI-model icon, and that the existing "Claude/ChatGPT/Gemini Processor" and "NotebookLM: ..." Workflow Builder nodes are unchanged. This step has real side effects (starts a server) — leave it to whoever reviews the finished work rather than running it unattended.

- [ ] **Step 4: No commit needed**

This task is verification-only; if Steps 1-2 fail, fix the specific failing task above and re-run before proceeding — don't accumulate a separate fixup commit here.
