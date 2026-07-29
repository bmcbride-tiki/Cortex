# =============================================================================
# theme_exporter.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Holds a fixed set of dark-mode and light-mode color values (a "ShadCN
#   UI"-style design token palette) meant for a future n8n-style visual
#   canvas. Purely a data file -- two dictionaries of color values and one
#   lookup function, no logic beyond picking dark vs. light.
#
# WHAT IT INTERACTS WITH
#   - Nothing yet. This was built as part of an early visual-canvas
#     exploration; the app's actual running Workflow Builder page
#     (`templates/workflow-builder.html`) uses its own, separate, already-
#     established CSS-variable theme system (see that file's `--color-*`
#     variables), not this one. Nothing in the codebase currently imports
#     `ShadCNThemePalette`.
#
# KEY FUNCTIONALITY NOTES
#   - `get_theme(mode)` is the only real function -- returns `DARK_THEME` or
#     `LIGHT_THEME` based on the `mode` string, defaulting to dark.
#   - Kept in case a future visual-canvas rebuild wants a ready-made ShadCN-
#     style palette to start from; not currently wired into any page.
# =============================================================================

from typing import Dict, Any

class ShadCNThemePalette:
    """ShadCN UI Zinc Theme Variables & n8n Canvas Styling Attributes."""

    DARK_THEME = {
        "mode": "dark",
        "css_vars": {
            "--background": "240 10% 3.9%",
            "--foreground": "0 0% 98%",
            "--card": "240 10% 6%",
            "--card-foreground": "0 0% 98%",
            "--popover": "240 10% 6%",
            "--popover-foreground": "0 0% 98%",
            "--primary": "217.2 91.2% 59.8%",
            "--primary-foreground": "222.2 47.4% 11.2%",
            "--secondary": "240 3.7% 15.9%",
            "--secondary-foreground": "0 0% 98%",
            "--muted": "240 3.7% 15.9%",
            "--muted-foreground": "240 5% 64.9%",
            "--accent": "240 3.7% 15.9%",
            "--accent-foreground": "0 0% 98%",
            "--destructive": "0 62.8% 30.6%",
            "--destructive-foreground": "0 0% 98%",
            "--border": "240 3.7% 15.9%",
            "--input": "240 3.7% 15.9%",
            "--ring": "224.3 76.3% 48%"
        },
        "canvas": {
            "bg_color": "#09090B",
            "grid_dots": "#27272A",
            "node_card_bg": "#18181B",
            "node_card_border": "#27272A",
            "node_header_bg": "#202023",
            "text_title": "#FAFAFA",
            "text_subtitle": "#A1A1AA",
            "status_success": "#22C55E",
            "status_failed": "#EF4444",
            "status_running": "#3B82F6",
            "status_greyed_out": "#52525B",
            "greyed_out_opacity": 0.35
        }
    }

    LIGHT_THEME = {
        "mode": "light",
        "css_vars": {
            "--background": "0 0% 100%",
            "--foreground": "240 10% 3.9%",
            "--card": "0 0% 100%",
            "--card-foreground": "240 10% 3.9%",
            "--popover": "0 0% 100%",
            "--popover-foreground": "240 10% 3.9%",
            "--primary": "221.2 83.2% 53.3%",
            "--primary-foreground": "210 40% 98%",
            "--secondary": "240 4.8% 95.9%",
            "--secondary-foreground": "240 5.9% 10%",
            "--muted": "240 4.8% 95.9%",
            "--muted-foreground": "240 3.8% 46.1%",
            "--border": "240 5.9% 90%",
            "--ring": "221.2 83.2% 53.3%"
        },
        "canvas": {
            "bg_color": "#F8FAFC",
            "grid_dots": "#E2E8F0",
            "node_card_bg": "#FFFFFF",
            "node_card_border": "#E2E8F0",
            "node_header_bg": "#F1F5F9",
            "text_title": "#0F172A",
            "text_subtitle": "#64748B",
            "status_success": "#16A34A",
            "status_failed": "#DC2626",
            "status_running": "#2563EB",
            "status_greyed_out": "#94A3B8",
            "greyed_out_opacity": 0.45
        }
    }

    @classmethod
    def get_theme(cls, mode: str = "dark") -> Dict[str, Any]:
        return cls.DARK_THEME if mode.lower() == "dark" else cls.LIGHT_THEME
