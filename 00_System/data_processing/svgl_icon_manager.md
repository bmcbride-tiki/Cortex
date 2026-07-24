---
tool_id: 'svgl_icon_manager'
title: 'SVGL Icon Manager'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/icon-resolution, scope/workflow-builder, connects/canvas-schema, connects/server]
---

# svgl-icon-manager

> **Status:** Active. No `__main__` block. Imported by [[canvas_schema]] and by `server.py`'s icon lookup for the Workflow Builder palette/canvas and Workflow Map.

## Purpose

Resolves a brand name (like `"m365"` or `"openai"`) to the web address of its real logo, hosted by SVGL (https://svgl.app), a free public library of app/company logos -- what puts a real Microsoft Outlook icon next to an Outlook building block instead of a generic placeholder. Can also download and cache a logo's SVG file locally.

## Processing Logic

### `SvglIconManager.get_icon_url(brand_key) -> str`

No network call -- pure URL-string construction. Checks `SVGL_FALLBACK_MAP` first for a known, verified brand slug; otherwise builds a best-guess URL directly from the brand name (`https://svgl.app/library/<name>.svg`), which may or may not actually exist on SVGL's site. Never raises.

### `SvglIconManager.fetch_and_cache_svg(brand_key) -> str`

The one method that actually downloads (via `httpx`). Returns the cached local copy if one already exists under `00_System/data_processing/svg_cache/`; otherwise fetches from `get_icon_url()`'s address and caches it. On any failure, falls back to a small generated placeholder SVG (a colored square with the brand's first two letters) rather than returning nothing.

## Output

A URL string (`get_icon_url`) or raw SVG markup (`fetch_and_cache_svg`); cached `.svg` files under `svg_cache/`.

## Notes for AI reuse

`server.py` maintains its own, larger, per-*tool_id* icon map (`TOOL_SVGL_MAP`/`TOOL_FA_ICON_MAP`) built by hand against the real SVGL API for every Microsoft/Google/AI product Cortex actually has a building block for -- that map, not this file's generic brand-key fallback, is what the live Workflow Builder palette and Workflow Map actually use for their icons. This file's `get_icon_url`/`fetch_and_cache_svg` are the lower-level, more generic primitives `canvas_schema.py`'s standalone graph model builds on.
