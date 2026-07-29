---
tool_id: 'md_editor'
title: 'Obsidian-Lite Editor (Standalone Desktop App)'
classification: '00_System_Core/protocol'
data_policy: 'internal'
execution_engine: 'desktop_gui'
tags: [type/module, domain/system-core, tier/interactive, function/markdown-editor, scope/desktop-tool]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# md-editor

> **Status:** Active, standalone. **Not the same system as Cortex's own in-browser markdown editor** (`server.py`'s `GET/POST /api/md-editor/read|save`, see [[server]]) -- this is a separate PyQt6 desktop window, launched independently (`python md_editor.py [path]`), not embedded in or called by the web app.

## Purpose

A lightweight desktop Markdown editor/viewer styled after Obsidian's dark theme: a raw-text "Code View" and a rendered "Human View" you can flip between with one button, for quickly reading or editing a vault `.md` note outside the browser.

## Processing Logic

* `init_ui()` -- builds the window: an Open/Save/toggle toolbar plus a `QStackedWidget` holding both views (swapping views doesn't resize/shift the window).
* `apply_ui_theme()` / `get_markdown_css()` -- two separate style sheets: one for the window chrome (buttons, borders), one injected into the rendered HTML body (headings, code blocks, tables, the metadata-block box).
* `load_routed_file(target_path)` -- strips an `mde:` prefix if present, then loads the target file's raw text into Code View; if the file doesn't exist yet, pre-fills a blank note template (including an empty `---` metadata block) instead of erroring.
* `toggle_view()` -- when switching to Human View: pulls the `--- ... ---` frontmatter block off the top of the raw text (if present), renders it as a distinct styled box with any `tags:`/`tag:` line turned into individual clickable `#tag` links, then converts the remaining body from Markdown to HTML via the `markdown` library (`fenced_code`, `tables` extensions).
* `handle_tag_clicked(url)` -- intercepts clicks on those `tag:/...` links and prints the tag to the console; does not navigate or filter anything itself (a fuller integration could react to this print statement).

## Output

Reads/writes plain `.md`/`.txt` files directly on disk via standard file dialogs (`open_file()`, `save_file()`). No network calls, no database, no dependency on [[server]] being running.

## Notes for AI reuse

If this tool's `mde:` link handling and Cortex's own `/api/md-editor/*` routes (see [[server]]) are ever meant to be the same feature, that unification hasn't happened yet -- they currently read/write files independently and don't share state, a cache, or a lock. Treat them as two separate markdown-editing surfaces until/unless that's deliberately merged.
