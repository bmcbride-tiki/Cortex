# AI Capability Tasks — Design

## Goal

Add the remaining Power Automate "AI Builder"-style capabilities (Summarize Text, Sentiment Analysis, Language Detection, Text Translation, Key Phrase Extraction, Entity Extraction, Category Classification, Form/Invoice Processing, Business Card & ID Reader, Object Detection & OCR, Image Description, Predict) as new Cortex Tasks, using Power Automate's action names/behavior only as a naming reference, not an architecture to clone.

"Create Text with GPT" already exists in spirit (`ask_gemini`/`ask_claude`/`ask_chatgpt`/`ask_copilot` — instructions + input text, already real today).

## Why this is a small, low-risk slice (unlike M365/Google)

`gemini_bridge.py`'s `ask_gemini()` is **already real** — it's a browser-session bridge (Playwright captures your signed-in Gemini cookies once; every call after that goes straight to Google over `gemini_webapi`), not an API-key stub. `GEMINI_MOCK_MODE=0` makes it real today, with nothing new to provision. The installed `gemini_webapi==2.0.0`'s `generate_content(prompt, files=[...])` already accepts image/document file paths — confirmed by inspecting the installed package's signature — so multimodal actions (OCR, business card reading, form processing, image description) need no new dependency either.

Every action here is a **Task** (`12_Tasks/<name>/<name>.py`), not a `Function` node — meaning no `workflow_engine.py` dispatch branch and no `FUNCTION_FIELD_SCHEMAS` frontend entry is needed at all. `CoreRouter` auto-discovers any folder under `12_Tasks/` with a matching filename; the Workflow Builder's existing generic Task/Process config panel (arg-schema-driven or plain args box) already handles it. This mirrors the existing `ask_gemini`/`ask_claude` Task convention exactly: a `class X: def run(self, ...) -> dict` wrapping a `14_Adapters/gemini_bridge` call, called **in-process** (no subprocess — `CoreRouter` subprocess-launches the *Task script itself*, which then imports the adapter directly), a paired `test_<name>.py`, and a `main()` CLI entry point reading one JSON payload arg.

## `gemini_bridge.py` change: accept optional file paths

`ask_gemini(prompt: str, use_search: bool = False)` gains one new optional parameter, backward compatible (default preserves every existing call site unchanged):

```python
def ask_gemini(prompt: str, use_search: bool = False, files: Optional[List[str]] = None) -> str:
    if MOCK_MODE:
        mode = "search-grounded " if use_search else ""
        file_note = f" [with {len(files)} attached file(s)]" if files else ""
        return f"[MOCK {mode}Gemini response{file_note}] {prompt[:300]}"
    psid, psidts = _get_session_cookies()
    return asyncio.run(_ask_async(psid, psidts, prompt, deep_research=use_search, files=files))
```

`_ask_async` gains the same `files` passthrough to `client.generate_content(prompt, files=files)`. Passing both `files` and `use_search=True` (Deep Research) raises `ValueError` in `ask_gemini()` itself — a deliberate Cortex-side restriction (Deep Research is a multi-step research pass over a topic, not a single-turn multimodal question, so combining the two isn't a case any of the new Tasks below need), not a claim about what the underlying `gemini_webapi` library does or doesn't accept.

## The twelve new Tasks

All follow the exact `ask_gemini.py` shape (`class X: def run(...) -> dict`, `main()` CLI entry, paired test). Each crafts a fixed instruction template around the user's real input and calls `_ask_gemini(prompt, files=...)`. Where the original Power Automate action returns structured data (key phrases, entities, form fields), the prompt explicitly asks Gemini to reply as JSON, so the result composes directly with the existing `Parse JSON`/array-op Function nodes from the flow-control slice — a deliberate, real synergy, not a coincidence.

| Task folder | Params | Prompt shape |
|---|---|---|
| `summarize_text` | `text_content` | "Summarize the following text concisely, capturing the key points:\n\n{text_content}" |
| `sentiment_analysis` | `text`, `language` (optional hint) | "Analyze the sentiment of the following text{lang}. Reply with exactly one word (Positive/Negative/Neutral) followed by a one-sentence explanation.\n\nText:\n{text}" |
| `language_detection` | `text` | "Identify the language of the following text. Reply with just the language name.\n\nText:\n{text}" |
| `text_translation` | `text`, `target_language`, `source_language` (optional) | "Translate the following text to {target_language}{source_note}. Reply with only the translated text.\n\nText:\n{text}" |
| `key_phrase_extraction` | `text`, `language` (optional hint) | "Extract the main key phrases/topics from the following text{lang}. Reply as a JSON array of strings only.\n\nText:\n{text}" |
| `entity_extraction` | `text` | "Extract named entities (people, organizations, locations, dates, etc.) from the following text. Reply as a JSON array of objects with 'text' and 'type' fields, only.\n\nText:\n{text}" |
| `category_classification` | `text`, `categories` (comma-separated list, replaces the original spec's opaque "Model" param — there is no trained classifier here, just an instruction) | "Classify the following text into exactly one of these categories: {categories}. Reply with just the category name.\n\nText:\n{text}" |
| `form_invoice_processing` | `file_path` | "Extract every field and its value from this form/invoice/receipt as a JSON object." + `files=[file_path]` |
| `business_card_id_reader` | `file_path` | "Extract contact/identification information (name, title, company, phone, email, address, ID number if present) from this image as a JSON object." + `files=[file_path]` |
| `object_detection_ocr` | `file_path` | "Identify visible objects and extract any visible text (OCR) from this image. Reply as JSON: {\"objects\": [...], \"text\": \"...\"}." + `files=[file_path]` |
| `image_description` | `file_path` | "Describe this image in detailed, natural language." + `files=[file_path]` |
| `predict` | `model`, `input_dataset` | **Mock-only, honestly labeled** — see below |

### `predict` is an honest stub, not a real capability

Power Automate's `Predict` runs a row of input data through a **trained ML model** (an AI Builder model, or a custom Azure ML endpoint) — a fundamentally different thing from prompting an LLM. Cortex has no trained-model infrastructure and none is being built here. `predict` returns a clearly labeled mock structure (`{"model": model, "prediction": "[MOCK] no trained model backend exists yet", "confidence": None}`) always, regardless of `GEMINI_MOCK_MODE`, with a docstring explaining why — the same "honest limitation" pattern `generate_pptx_from_word`'s Copilot mock already uses for a capability with no real API to call.

## File-based actions and the vault containment rule

`form_invoice_processing`/`business_card_id_reader`/`object_detection_ocr`/`image_description` take a `file_path` param — a real local path the user (or an upstream workflow node) already produced, not a browser upload. No new containment-checking is needed beyond what already exists: these Tasks pass the path straight to `gemini_webapi`, which reads the file itself; a nonexistent path fails with a clear `FileNotFoundError`-derived message before ever reaching Gemini (checked in the Task, not left to surface as an opaque Gemini API error).

## Registry & icons (`server.py`)

Each new `tool_id` gets a `TOOL_MODELS` entry (`"gemini"`, matching `ask_gemini`/`generate_gemini_image`) and a `TOOL_FA_ICON_MAP` entry (verified against the vendored FA6 CSS the same way every icon in the prior two slices was, not guessed). No `FUNCTIONS_REGISTRY` entry — these are Tasks, auto-discovered by `CoreRouter`, not `Function` nodes.

## Testing

One `test_<name>.py` per Task (repo convention: co-located, plain `assert`, run directly), covering: the happy path with `GEMINI_MOCK_MODE` mocked/defaulted, a missing-required-param error, and — for the four file-based actions — a missing-file error. Plus one addition to `gemini_bridge.py`'s own test coverage (there is none today — a `test_gemini_bridge.py` is added) covering `files` passthrough in mock mode and the Deep Research + files `ValueError`.

## Explicitly out of scope

- **Any change to `workflow_engine.py` or `FUNCTION_FIELD_SCHEMAS`** — these are Tasks, not Function nodes; the existing generic Task config panel and `CoreRouter` auto-discovery already cover them.
- **A real trained-model backend for `Predict`** — stays an honest mock indefinitely, per Cortex's mock-mode principle for capabilities with no real API to call.
- **Azure Cognitive Services / Google Cloud NLP as alternate backends** — everything routes through the existing Gemini bridge; no new provider, no new credentials, no new dependency.
