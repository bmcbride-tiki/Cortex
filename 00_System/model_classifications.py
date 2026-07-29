# =============================================================================
# model_classifications.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   Single source of truth for which AI model backends this project talks to
#   are approved for which information-security classification level, per
#   the Government of Alberta AI Academy classification guide. Used by
#   server.py to annotate the Workflow Builder's node registry, and by
#   workflow-builder.html (via that same registry response) to compute a
#   workflow's live classification ceiling from the models its nodes use.
#
# KEY FUNCTIONALITY NOTES
#   - Levels are ordered least -> most sensitive. A tool cleared for a
#     higher level is trusted for every level below it too (e.g. Copilot,
#     cleared to Protected B, can also be used for Protected A and Public
#     data).
#   - "Most restrictive model wins": a workflow's overall classification
#     ceiling is the LOWEST level among every AI model actually used in
#     it, since the weakest-cleared tool in the chain caps what the whole
#     workflow can safely process -- see classification_ceiling() below.
#   - Claude is not yet in the official classification list this was built
#     from. It defaults to the most conservative level ("public") until
#     someone officially classifies it -- update MODEL_CLASSIFICATIONS below
#     the moment that happens.
# =============================================================================

from typing import Dict, Iterable, List, Optional

CLASSIFICATION_LEVELS: List[str] = ["public", "protected_a", "protected_b", "protected_c"]

CLASSIFICATION_LABELS: Dict[str, str] = {
    "public": "Public",
    "protected_a": "Protected A",
    "protected_b": "Protected B",
    "protected_c": "Protected C",
}

# Model key -> classification level. Source: Government of Alberta AI Academy
# classification guide (Copilot Chat/M365 Copilot = Protected B; Gemini Pro/
# NotebookLM = Protected A; ChatGPT = Public, "not used for protected
# information"). Claude is not in that list -- defaulted to "public" (see note above).
MODEL_CLASSIFICATIONS: Dict[str, str] = {
    "copilot": "protected_b",
    "gemini": "protected_a",
    "notebooklm": "protected_a",
    "chatgpt": "public",
    "claude": "public",
}


def classification_ceiling(model_keys: Iterable[str]) -> Optional[str]:
    """Most-restrictive-model-wins: the lowest classification level among the
    given model keys, or None if no known model keys were given."""
    levels_used = [MODEL_CLASSIFICATIONS[key] for key in model_keys if key in MODEL_CLASSIFICATIONS]
    if not levels_used:
        return None
    return min(levels_used, key=CLASSIFICATION_LEVELS.index)
