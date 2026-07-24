# Function Inventory, Task Migration, Model Classification & Config-Panel Audit — Design Spec

**Date:** 2026-07-22
**Status:** Approved by user, implementing directly across phases

## Background

Follow-up to the NotebookLM adapter and human-review-checkpoint work. Four
related directives from the user:

1. Inventory every "function"-kind node currently in the Workflow Builder.
2. Anything standalone-capable moves into a real `13_Functions` folder;
   anything meaningful only inside a graph (or already backed by a real
   Adapter) stays a built-in engine function.
3. Give each migrated function real folders/files: `.py`, `.md`, tests.
4. Full project-wide audit: every node type (Skill/Process/Task/Function/
   Adapter) must show its actual configurable settings in the Node
   Configuration panel — no silent "No config UI defined" gaps.

Plus a new requirement surfaced mid-design: AI-passthrough functions become
model-specific (Gemini/Copilot/Claude/ChatGPT/NotebookLM, each its own
node), two new mock adapters are needed (Claude, ChatGPT), and the Workflow
Builder gains a model-toggle + live classification-ceiling panel reflecting
the Government of Alberta's information security classification scheme.

## 1. Inventory & classification (directive 1+2)

22 built-in `"function"`-kind nodes existed before this pass (see prior
turn's full list). Classified as:

**Graph-only — stays a built-in function (no standalone form makes sense):**
`builtin_review_gate`, `function_logic_gate`, `function_concatenate`

**Already standalone via an existing Adapter — stays a built-in function
wrapper, but becomes model-specific (see section 3):**
`builtin_ai_processor`, `builtin_formatter`, `function_google_search`,
`function_image_generate`, `function_gemini_ask`,
`function_copilot_image_generate`, `function_copilot_agent_ask`,
`function_copilot_list_agents`, `function_notebooklm_create`,
`function_notebooklm_upload_sources`, `function_notebooklm_prompt_loop`

**Genuinely standalone-capable, no existing home — moved into `13_Functions`
(directive 2+3):** `function_split`, `function_json_parse`,
`function_export_json`, `function_export_markdown`, `function_export_word`,
`function_export_pdf`, `function_import_json`, `function_import_word`,
`function_import_pdf`, `function_web_scrape`, `builtin_template_generator`

Each becomes its own `13_Functions/<name>/` folder: `.py` (real logic,
extracted from `workflow_engine.py`'s existing private methods),
`.md` (documented per the existing Task/Function doc convention), and an
assert-based `test_<name>.py`. Once moved, `workflow_engine.py`'s
`_execute_function_node` ladder drops the corresponding `tool_id` branch
entirely (dispatch now goes through the generic `09_Functions` path added
for `human_review_checkpoint`) — no dead code left behind.

## 2. New adapters: Claude, ChatGPT (mock-mode)

`14_Adapters/claude_bridge/claude_bridge.py` and
`14_Adapters/chatgpt_bridge/chatgpt_bridge.py`, both following
`notebooklm_bridge.py`'s exact shape: `MOCK_MODE` env-toggle (default on),
one `ask(prompt)` action, clean "not configured yet" failure when
`MOCK_MODE` is off. No real credentials wired up (per user decision) --
these are structurally ready for a real Anthropic/OpenAI SDK call later,
purely inside the action function.

## 3. Model-specific AI-passthrough nodes

New built-in functions: `function_claude_ask`, `function_chatgpt_ask`
(mirroring `function_gemini_ask`'s shape: `instructions` + upstream text ->
response). Existing AI-passthrough functions are unchanged in behavior but
each now carries a `"model"` tag (see section 4) so the classification
system can reason about them. `builtin_ai_processor`/`builtin_formatter`
(currently hardcoded to Copilot) are tagged `model: "copilot"` --
functionally unchanged, just now classifiable.

## 4. Information security classification system

Authoritative source (Government of Alberta AI Academy classification
guide, as provided):

| Level | Meaning |
|---|---|
| 🟢 Public | No injury if compromised |
| 🟡 Protected A | Could cause injury |
| 🟠 Protected B | Could cause serious injury |
| 🔴 Protected C | Could cause extremely grave injury |

Tool -> level mapping (higher clearance covers all lower levels too):

| Model key | Level | Source tools |
|---|---|---|
| `copilot` | `protected_b` | Copilot Chat, M365 Copilot |
| `gemini` | `protected_a` | Google Gemini Pro |
| `notebooklm` | `protected_a` | Google NotebookLM |
| `chatgpt` | `public` | ChatGPT ("not used for protected information") |
| `claude` | `public` | **Not in the official list yet** -- defaults to the most conservative level (`public`) until officially classified. This default must be easy to find and update (`MODEL_CLASSIFICATIONS` dict, one line) once Claude is formally classified. |

New module `00_System/model_classifications.py`:

```python
CLASSIFICATION_LEVELS = ["public", "protected_a", "protected_b", "protected_c"]  # least -> most sensitive
CLASSIFICATION_LABELS = {"public": "Public", "protected_a": "Protected A", "protected_b": "Protected B", "protected_c": "Protected C"}
MODEL_CLASSIFICATIONS = {"copilot": "protected_b", "gemini": "protected_a", "notebooklm": "protected_a", "chatgpt": "public", "claude": "public"}

def classification_ceiling(model_keys):
    """Most-restrictive-model-wins: the lowest level among the given models, or None if models_used is empty."""
    levels_used = [MODEL_CLASSIFICATIONS[m] for m in model_keys if m in MODEL_CLASSIFICATIONS]
    if not levels_used:
        return None
    return min(levels_used, key=CLASSIFICATION_LEVELS.index)
```

`/api/workflow-builder/node-registry` gains a `model` field on every
AI-backed entry (Adapters: `copilot_bridge`->`copilot`,
`gemini_bridge`->`gemini`, `notebooklm_bridge`->`notebooklm`,
`claude_bridge`->`claude`, `chatgpt_bridge`->`chatgpt`; the model-specific
built-in Functions get the matching key; everything else `model: null`),
plus a top-level `model_classifications` object mirroring the Python dict
above, so the frontend needs no separate fetch.

## 5. Workflow Builder UI: model toggle + classification panel

New panel in `workflow-builder.html`, placed between the canvas and the Run
Log (the existing `<div id="wfb-canvas">...` block and the `Run Log`
`<div class="... h-40 ...">` block):

* One toggle per known model (`copilot` default **on**; `gemini`, `claude`,
  `chatgpt`, `notebooklm` default **off** -- conservative default, matching
  the org's primary-approved-tool-first posture).
* Toggling a model off hides every palette entry whose `model` matches it
  (additional filter layered on top of the existing search/kind filter).
* A live classification badge (color-coded per the table above) computed
  from the `model` field of every node **currently placed on the canvas**
  (not the toggle state) via `classification_ceiling()`'s JS equivalent --
  "most restrictive model wins." Shows "No AI model in use" when no
  AI-backed node is on the canvas. Recomputed on every canvas
  add/remove/load.

## 6. Config-panel audit (directive 4, full project-wide scope)

1. **Immediate bugfix:** `function_copilot_image_generate`,
   `function_copilot_agent_ask`, `function_copilot_list_agents` are missing
   from `FUNCTION_FIELD_SCHEMAS` entirely (currently show "No config UI
   defined"). Add their schemas.
2. **Every newly-migrated `13_Functions` entry** gets a real config panel --
   since these are `category: "09_Functions"` (dispatched like Task/Process/
   Adapter via generic CLI args), they follow the same path every other
   argful Task takes today: either a `FIELD_PARTIAL_TOOL_IDS` field-partial
   (for richer inputs) or, at minimum, the existing generic Args panel is
   confirmed sufficient and documented per-function in its `.md`.
3. **Full audit of Tasks/Processes/Adapters/Skills:** every existing entry
   without a `FIELD_PARTIAL_TOOL_IDS` field-partial currently falls back to
   the generic freeform "Args" textarea (one raw string per line, manually
   token-substituted). Audit each one's actual required inputs; add a
   dedicated field-partial wherever the generic Args box is insufficient or
   confusing (e.g. an adapter needing a structured JSON payload with several
   named fields is a poor fit for hand-typed freeform args).

## Explicitly Out of Scope

* Real Claude/ChatGPT API credentials (mock-mode only, per user decision).
* A Protected C-classified tool (none exist in the source list yet).
* Enforcing the classification ceiling (blocking a run, refusing to save,
  etc.) -- this pass only *displays* it; enforcement is a future decision.
