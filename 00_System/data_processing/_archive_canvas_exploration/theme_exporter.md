---
tool_id: 'theme_exporter'
title: 'ShadCN Theme Palette'
classification: '00_System_Core/data_processing'
data_policy: 'internal'
execution_engine: 'pure_code'
tags: [type/module, domain/system-core, domain/data-processing, tier/zero-input, function/theming, scope/workflow-builder]
copyright: '2025 Brian McBride at Tiki-1 Studio'
---

# theme-exporter

> **Status:** Dead/unused. No `__main__` block. **Nothing in the codebase currently imports `ShadCNThemePalette`.**

## Purpose

Holds a fixed set of dark-mode and light-mode color values (a "ShadCN UI"-style design token palette), built during an early exploration of an n8n-style visual canvas.

## Processing Logic

### `ShadCNThemePalette.get_theme(mode="dark") -> Dict`

Returns the `DARK_THEME` or `LIGHT_THEME` dict based on `mode`, defaulting to dark. That's the entire logic in this file.

## Output

A dict of CSS custom-property values and canvas colors -- currently only ever read by `sandbox_smoke_test.py`'s smoke test, never by a real page.

## Notes for AI reuse

⚠ **Tech-debt finding from this documentation pass:** the app's actual running Workflow Builder page (`templates/workflow-builder.html`) uses its own, separate, already-established CSS-variable theme system (`--color-surface`, `--color-primary`, etc., defined in `templates/static/src/input.css`) -- a deliberate choice made when building the license-gating/icon feature, specifically to avoid two competing design-token systems in one app. This file was kept in case a future visual-canvas rebuild wants a ready-made ShadCN-style starting point, but it is not wired into anything today. Either delete it, or clearly mark it "reference only, not live" if kept.
