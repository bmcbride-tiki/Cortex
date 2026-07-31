# =============================================================================
# predict.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A Task: mirrors Power Automate's "Predict" action (run a row of input
#   data through a TRAINED ML model -- an AI Builder model, or a custom Azure
#   ML endpoint). That is a fundamentally different thing from prompting an
#   LLM, which is all every other Task in this project's AI capability set
#   does. Cortex has no trained-model infrastructure, and none is being built
#   here -- this is an honest, always-mock stub (unlike every Gemini-backed
#   Task alongside it, it does NOT become real when GEMINI_MOCK_MODE=0,
#   because there is no real backend for it to call), matching the same
#   "honest limitation" pattern generate_pptx_from_word_with_copilot.py's
#   mock-only Copilot presentation generation already uses for a capability
#   with no real API behind it.
# =============================================================================

import sys
import json


class Predict:
    """Always-mock stub for running input data through a trained ML model --
    no real trained-model backend exists in Cortex to call. Kept clearly
    labeled rather than silently faked as a real prediction."""

    def run(self, model: str, input_dataset: str) -> dict:
        if not model:
            return {"success": False, "response": "model is required."}
        if not input_dataset:
            return {"success": False, "response": "input_dataset is required."}
        return {
            "success": True,
            "response": {
                "model": model,
                "prediction": "[MOCK] no trained model backend exists yet",
                "confidence": None,
            },
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "response": 'Expected one JSON payload arg: {"model": "...", "input_dataset": "..."}'}))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        result = Predict().run(model=params.get("model", ""), input_dataset=params.get("input_dataset", ""))
    except Exception as e:
        result = {"success": False, "response": f"predict error: {e}"}

    print(json.dumps(result))
    if not result.get("success"):
        sys.exit(1)
